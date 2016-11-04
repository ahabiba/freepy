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

from uuid import uuid4

from freepy.lib.actors.actor_processor import ActorProcessor
from freepy.lib.actors.actor_scheduler import ActorScheduler
from freepy.lib.actors.actor_scheduler_manager import ActorSchedulerManager
from freepy.lib.actors.messages.poison_pill import PoisonPill

class Actor(object):
  '''
  An actor is the most basic unit of computation in an actor framework.
  '''

  def __init__(self, runner, *args, **kwargs):
    self._mailbox = list()
    if isinstance(runner, ActorScheduler):
      self._scheduler = runner
    elif isinstance(runner, ActorSchedulerManager):
      self._scheduler = runner.next_scheduler()
    self._urn = uuid4()

    super(Actor, self).__init__()
    # Schedule ourself for execution.
    proc = ActorProcessor(self, self._mailbox, self._scheduler, self._urn, waiter=self._scheduler._waiter)
    proc.start()

  @property
  def scheduler(self):
    return self._scheduler

  @property
  def urn(self):
    return self._urn


  def receive(self, message):
    '''
    This method processes incoming messages.
    '''

    raise NotImplementedError()

  def stop(self):
    self.tell(PoisonPill())

  def tell(self, message):
    self._mailbox.append(message)
    if not self._scheduler._waiter.isSet():
      self._scheduler._waiter.set()
