# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# Thomas Quintana <quintana.thomas@gmail.com>

from freepy.lib.actors.actor import Actor
from freepy.lib.actors.utils import object_fqn
from freepy.lib.server import RouteMessageCommand, ServerDestroyEvent, ServerInitEvent
from llist import dllist
from threading import Thread

import logging
import time

class ReceiveTimeoutCommand(object):
  def __init__(self, sender, timeout, recurring = False):
    self._sender = sender
    self._timeout = timeout
    self._recurring = recurring

  def sender(self):
    return self._sender

  def timeout(self):
    return self._timeout

  def recurring(self):
    return self._recurring

class StopTimeoutCommand(object):
  def __init__(self, sender):
    self._sender = sender

  def sender(self):
    return self._sender

class ClockEvent(object):
  pass

class TimeoutEvent(object):
  pass

class MonotonicClock(Thread):
  def __init__(self, actor, interval, *args, **kwargs):
    super(MonotonicClock, self).__init__(group = None)
    self._actor = actor
    self._interval = interval
    self._running = True
    # Singleton instance of ClockEvent.
    self._event = ClockEvent()

  def run(self):
    while self._running:
      time.sleep(self._interval)
      if self._running:
        self._actor.tell(self._event)
      else:
        break

  def stop(self):
    self._running = False

class TimerService(Actor):
  '''
  The timer service uses the timing wheel algorithm borrowing from the
  approach used in the Linux kernel. Please refer to the email thread
  by Ingo Molnar @ https://lkml.org/lkml/2005/10/19/46.
  '''
  TICK_SIZE  = 0.1             # Tick every 100 milliseconds.

  def __init__(self, *args, **kwargs):
    super(TimerService, self).__init__(*args, **kwargs)
    # Initialize the timing wheels. The finest possible
    self._logger = logging.getLogger(object_fqn(self))
    # granularity is 100ms.
    self._timer_vector1 = self._create_vector(256)
    self._timer_vector2 = self._create_vector(256)
    self._timer_vector3 = self._create_vector(256)
    self._timer_vector4 = self._create_vector(256)
    # Initialize the timer vector indices.
    self._timer_vector2_index  = 0
    self._timer_vector3_index  = 0
    self._timer_vector4_index  = 0
    # Initialize the tick counter.
    self._current_tick = 0
    # Initialize the actor lookup table for O(1) timer removal.
    self._actor_lookup_table = dict()
    # Singleton instance of the timeout event.
    self._timeout = TimeoutEvent()
    # Monotonic clock.
    self._clock = None

  def _cascade_vector(self, vector, elapsed):
    '''
    Cascades all the timers inside a vector to a lower bucket.

    Arguments: vector  - The vector to cascade.
               elapsed - The amount of time elapsed in milliseconds.
    '''
    for index in range(1, len(vector)):
      bucket = vector[index]
      previous_bucket = vector[index - 1]
      while len(bucket) > 0:
        timer = bucket.popleft()
        expires = timer.expires() - elapsed
        timer.expires(expires)
        node = previous_bucket.append(timer)
        self._update_lookup_table(previous_bucket, node)

  def _cascade_vector_2(self):
    '''
    Cascades timers from vector 2 into vector 1.
    '''
    tick = self._current_tick
    timers = self._timer_vector2[0]
    for timer in timers:
      expires = timer.expires() - 25600
      timer.expires(expires)
      self._vector1_insert(timer)
    timers.clear()
    self._cascade_vector(self._timer_vector2, 25600)
    index = self._timer_vector2_index
    index = (index + 1) % 256
    self._timer_vector2_index = index
    if self._timer_vector2_index == 0:
      self._cascade_vector_3()

  def _cascade_vector_3(self):
    '''
    Cascades timers from vector 3 into vector 2.
    '''
    tick = self._current_tick
    timers = self._timer_vector3[0]
    for timer in timers:
      expires = timer.expires() - 6553600
      timer.expires(expires)
      self._vector2_insert(timer)
    timers.clear()
    self._cascade_vector(self._timer_vector3, 6553600)
    index = self._timer_vector3_index
    index = (index + 1) % 256
    self._timer_vector3_index = index
    if self._timer_vector3_index == 0:
      self._cascade_vector_4()

  def _cascade_vector_4(self):
    '''
    Cascades timers from vector 4 into vector 3.
    '''
    tick = self._current_tick
    timers = self._timer_vector4[0]
    for timer in timers:
      expires = timer.expires() - 1677721600
      timer.expires(expires)
      self._vector3_insert(timer)
    timers.clear()
    self._cascade_vector(self._timer_vector4, 1677721600)
    index = self._timer_vector4_index
    index = (index + 1) % 256
    self._timer_vector4_index = index

  def _create_vector(self, size):
    '''
    Creates a new vector and initializes it to a specified size.

    Arguments: size - The size of the vector.
    '''
    vector = list()
    for counter in range(size):
      vector.append(dllist())
    return vector

  def _round(self, timeout):
    '''
    Rounds a timeout to the nearest multiple of the tick size.

    Arguments: timeout - The timeout to be rounded.
    '''
    if timeout < 100:
      return 100
    remainder = timeout % 100
    if remainder == 0:
      return timeout
    elif remainder <= 49:
      return  timeout - remainder
    else:
      return timeout + 100 - remainder

  def _schedule(self, timer):
    '''
    Schedules a timer for expiration.

    Arguments: timer - The timer to be shceduled.
    '''
    tick = self._current_tick
    timeout = timer.timeout()
    expires = (tick % 256) * 100 + self._round(timeout)
    timer.expires(expires)
    if expires <= 25600:
      self._vector1_insert(timer)
    elif expires <= 6553600:
      self._vector2_insert(timer)
    elif expires <= 1677721600:
      self._vector3_insert(timer)
    elif expires <= 429496729600:
      self._vector4_insert(timer)

  def _tick(self):
    '''
    Excutes one clock tick.
    '''
    tick = self._current_tick
    timers = self._timer_vector1[tick % 256]
    recurring = list()
    while len(timers) > 0:
      timer = timers.popleft()
      timer.observer().tell(self._timeout)
      if timer.recurring():
        recurring.append(timer)
      else:
        lookup_table = self._actor_lookup_table
        urn = timer.observer().urn()
        location = lookup_table.get(urn)
        if location:
          del lookup_table[urn]
    for timer in recurring:
      self._schedule(timer)
    self._current_tick = tick + 1
    if self._current_tick % 256 == 0:
      self._cascade_vector_2()

  def _unschedule(self, command):
    '''
    Unschedules a timer that has previously been scheduled for expiration.

    Arguments: command - The StopTimeoutCommand.
    '''
    urn = command.sender().urn()
    location = self._actor_lookup_table.get(urn)
    if location:
      del self._actor_lookup_table[urn]
      vector = location.get('vector')
      node = location.get('node')
      vector.remove(node)

  def _update_lookup_table(self, vector, node):
    '''
    Updates a lookup table used for O(1) timer removal.
    '''
    urn = node.value.observer().urn()
    location = {
      'vector': vector,
      'node': node
    }
    self._actor_lookup_table.update({urn: location})

  def _vector1_insert(self, timer):
    '''
    Inserts a timer into vector 1.

    Arguments: timer - The timer to be inserted.
    '''
    vector = self._timer_vector1
    bucket = timer.expires() / 100 - 1
    node = vector[bucket].append(timer)
    self._update_lookup_table(vector[bucket], node)

  def _vector2_insert(self, timer):
    '''
    Inserts a timer into vector 2.

    Arguments: timer - The timer to be inserted.
    '''
    vector = self._timer_vector2
    bucket = timer.expires() / 25600 - 1
    node = vector[bucket].append(timer)
    self._update_lookup_table(vector[bucket], node)

  def _vector3_insert(self, timer):
    '''
    Inserts a timer into vector 3.

    Arguments: timer - The timer to be inserted.
    '''
    vector = self._timer_vector3
    bucket = timer.expires() / 6553600 - 1
    node = vector[bucket].append(timer)
    self._update_lookup_table(vector[bucket], node)

  def _vector4_insert(self, timer):
    '''
    Inserts a timer into vector 4.

    Arguments: timer - The timer to be inserted.
    '''
    vector = self._timer_vector4
    bucket = timer.expires() / 1677721600 - 1
    node = vector[bucket].append(timer)
    self._update_lookup_table(vector[bucket], node)

  def receive(self, message):
    '''
    Handles incoming messages.

    Arguments: message - The message to be processed.
    '''
    if isinstance(message, ClockEvent):
      self._tick()
    elif isinstance(message, ReceiveTimeoutCommand):
      urn = message.sender().urn()
      if not self._actor_lookup_table.has_key(urn):
        timeout = message.timeout()
        observer = message.sender()
        recurring = message.recurring()
        self._schedule(TimerService.Timer(observer, timeout, recurring))
      else:
        self._logger.warning('Actor %s is requesting too many simultaneous timers.'
                             % urn)
    elif isinstance(message, StopTimeoutCommand):
      self._unschedule(message)
    elif isinstance(message, ServerInitEvent):
      self._start()
    elif isinstance(message, ServerDestroyEvent):
      self._stop()

  def _start(self):
    '''
    Initialized the TimerService.
    '''
    self._clock = MonotonicClock(self, TimerService.TICK_SIZE)
    self._clock.start()

  def _stop(self):
    '''
    Cleans up after TimerService.
    '''
    self._clock.stop()

  class Timer(object):
    def __init__(self, observer, timeout, recurring = False):
      self._observer = observer
      self._recurring = recurring
      self._timeout = timeout
      self._expires = 0

    def expires(self, *args):
      if len(args) == 0:
        return self._expires
      else:
        self._expires = args[0]

    def observer(self):
      return self._observer

    def timeout(self):
      return self._timeout

    def recurring(self):
      return self._recurring
