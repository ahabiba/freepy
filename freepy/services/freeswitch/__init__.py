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

from commands import *
from freepy.lib.actors.actor import Actor
from freepy.lib.actors.utils import object_fqn
from freepy.lib.fsm import *
from freepy.lib.server import RegisterActorCommand, RouteMessageCommand, \
                       ServerDestroyEvent, ServerInitEvent

from os import SEEK_END
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ReconnectingClientFactory

# Import the proper StringIO implementation.
try:
  from cStringIO import StringIO
except:
  from StringIO import StringIO

import logging
import re
from freepy import settings
import urllib

class EventSocketBootstrapper(Actor, FiniteStateMachine):
  transitions = [
    ('idle', 'authenticating'),
    ('authenticating', 'failed'),
    ('authenticating', 'bootstrapping'),
    ('bootstrapping', 'failed'),
    ('bootstrapping', 'done')
  ]

  def __init__(self, *args, **kwargs):
    super(EventSocketBootstrapper, self).__init__(*args, **kwargs)
    self._logger = logging.getLogger(object_fqn(self))
    self._dispatcher = kwargs.get('dispatcher')
    self._events = kwargs.get('events')
    self._password = settings.freeswitch.get('password')

  @Action(state = 'authenticating')
  def _authenticate(self):
    self._dispatcher.tell(EventSocketLockCommand(self))
    self._dispatcher.tell(AuthCommand(self, self._password))

  @Action(state = 'bootstrapping')
  def _bootstrap(self):
    unsorted = self._events
    sorted = ['BACKGROUND_JOB']
    for event in unsorted:
      if not event == 'CUSTOM' and event.find('::') == -1:
        sorted.append(event)
    if 'CUSTOM' in unsorted:
      sorted.append('CUSTOM')
    for event in unsorted:
      if event.find('::') > -1:
        sorted.append(event)
    self._dispatcher.tell(EventsCommand(self, events = sorted))

  @Action(state = 'done')
  def _finish(self):
    self._dispatcher.tell(EventSocketUnlockCommand())

  def receive(self, message):
    if isinstance(message, EventSocketEvent):
      content_type = message.headers().get('Content-Type')
      if content_type == 'auth/request':
        self.transition(to = 'authenticating')
      elif content_type == 'command/reply':
        reply = message.headers().get('Reply-Text')
        if reply == '+OK accepted':
          self.transition(to = 'bootstrapping')
        elif reply == '-ERR invalid':
          self.transition(to = 'failed')
        elif reply == '+OK event listener enabled plain':
          self.transition(to = 'done')
        elif reply == '-ERR no keywords supplied':
          self.transition(to = 'failed')

class EventSocketClient(Protocol):
  def __init__(self, observer):
    self._logger = logging.getLogger(object_fqn(self))
    self._buffer = None
    self._host = None
    self._observer = observer
    self._peer = None

  def _parse(self):
    # Make sure we have enough data to process the event.
    buffer_contents = self._buffer.getvalue()
    if len(buffer_contents) == 0 or not buffer_contents.find('\n\n'):
      return None
    else:
      # Parse the event for processing.
      self._buffer.seek(0)
      body = None
      headers = self._parse_headers()
      length = headers.get('Content-Length')
      if length:
        length = int(length)
        # Remove the Content-Length header.
        del headers['Content-Length']
        # Make sure we have enough data to process the body.
        offset = self._buffer.tell()
        self._buffer.seek(0, SEEK_END)
        end = self._buffer.tell()
        remaining = end - offset
        # Handle the event body.
        if length <= remaining:
          self._buffer.seek(offset)
          type = headers.get('Content-Type')
          if type and type == 'text/event-plain':
            headers.update(self._parse_headers())
            length = headers.get('Content-Length')
            if length:
              length = int(length)
              del headers['Content-Length']
              body = self._buffer.read(length)
          else:
            body = self._buffer.read(length)
        else:
          return None
      # Reclaim resources.
      offset = self._buffer.tell()
      self._buffer.seek(0, SEEK_END)
      end = self._buffer.tell()
      remaining = end - offset
      if remaining == 0:
        self._buffer.seek(0)
        self._buffer.truncate(0)
      else:
        self._buffer.seek(offset)
        data = self._buffer.read(remaining)
        self._buffer.seek(0)
        self._buffer.write(data)
        self._buffer.truncate(remaining)
      return EventSocketEvent(headers, body)

  def _parse_headers(self):
    headers = dict()
    while True:
      line = self._parse_line()
      if line == '':
        break
      else:
        tokens = line.split(':', 1)
        name = tokens[0].strip()
        if len(tokens) == 2:
          value = tokens[1].strip()
          if value and not len(value) == 0:
            value = urllib.unquote(value)
          headers.update({name: value})
        else:
          headers.update({name: None})
    return headers

  def _parse_line(self, stride = 64):
    line = list()
    while True:
      chunk = self._buffer.read(stride)
      end = chunk.find('\n')
      if end == -1:
        line.append(chunk)
      else:
        line.append(chunk[:end])
        offset = self._buffer.tell()
        left_over = len(chunk[end + 1:])
        self._buffer.seek(offset - left_over)
        break
      if len(chunk) < stride:
        break
    return ''.join(line)

  def connectionLost(self, reason):
    message = 'A connection to the FreeSWITCH instance '
    message += 'located @ %s:%i has been lost due to the ' % \
               (self._peer.host, self._peer.port)
    message += 'following reason.\n%s' % reason
    self._logger.critical(message)
    if self._buffer:
      self._buffer.close()
    self._buffer = None
    self._host = None
    self._peer = None

  def connectionMade(self):
    self._buffer = StringIO()
    self._host = self.transport.getHost()
    self._peer = self.transport.getPeer()
    self._observer.start(self)

  def dataReceived(self, data):
    message = 'Message From %s:%i\n%s' % \
              (self._peer.host, self._peer.port, data)
    self._logger.debug(message)

    self._buffer.write(data)
    while True:
      event = self._parse()
      if event:
        self._observer.consume(event)
      else:
        break

  def send(self, command):
    serialized_command = str(command)
    message = 'The following message will be sent to %s:%i.\n%s' % \
              (self._peer.host, self._peer.port, serialized_command)
    self._logger.debug(message)
    self.transport.write(serialized_command)

class EventSocketClientFactory(ReconnectingClientFactory):
  def __init__(self, observer):
    self.__logger__ = logging.getLogger(object_fqn(self))
    self.__observer__ = observer

  def buildProtocol(self, addr):
    self.__logger__.info('Connected to the FreeSWITCH instance ' +
                         'located @ %s:%i.' % (addr.host, addr.port))
    self.resetDelay()
    return EventSocketClient(self.__observer__)

class EventSocketDispatcher(Actor):
  def __init__(self, *args, **kwargs):
    super(EventSocketDispatcher, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger(object_fqn(self))
    self.__observers__ = {}
    self.__owner__ = None
    self.__transactions__ = {}
    self.__watches__ = []

  def _dispatch_auth(self, message):
    bootstrapper = EventSocketBootstrapper(self._scheduler,
      dispatcher = self,
      events = self.__events__
    )
    bootstrapper.tell(message)

  def _dispatch_command(self, message):
    observer = message.sender()
    if isinstance(message, BackgroundCommand):
      uuid = message.job_uuid()
      self.__observers__.update({ uuid: observer })
      self.__transactions__.update({ uuid: observer })
    self.__client__.send(message)

  def _dispatch_event(self, message):
    # Handle locked dispatcher events.
    if self.__owner__ is not None:
      self.__owner__.tell(message)
    content_type = message.headers().get('Content-Type')
    if content_type == 'command/reply':
      # Dispatch command responses.
      uuid = message.headers().get('Job-UUID')
      observer = self.__transactions__.get(uuid)
      if observer is not None:
        observer.tell(message)
      if self.__transactions__.has_key(uuid):
        del self.__transactions__[uuid]
      return
    if content_type == 'text/event-plain':
      event_name = message.headers().get('Event-Name')
      if event_name == 'BACKGROUND_JOB':
        # Dispatch background job responses.
        uuid = message.headers().get('Job-UUID')
        observer = self.__observers__.get(uuid)
        if observer is not None:
          observer.tell(message)
        if self.__observers__.has_key(uuid):
          del self.__observers__[uuid]
      # Dispatch incoming events using routing rules.
      for rule in self.__rules__:
        target = rule.get('target')
        header_name = rule.get('header_name')
        header_value = message.headers().get(header_name)
        if header_value is None:
          continue  
        target_pattern = rule.get('header_pattern')
        if target_pattern is not None:
          match = re.match(target_pattern, header_value)
          if match is not None:
            self.__server__.tell(RouteMessageCommand(message, target))
        target_value = rule.get('header_value')
        if target_value is not None and header_value == target_value:
          self.__server__.tell(RouteMessageCommand(message, target))
      # Dispatch incoming events using watches.
      for watch in self.__watches__:
        observer = watch.observer()
        header_name = watch.header_name()
        header_value = message.headers().get(header_name)
        if header_value is None:
          continue
        target_pattern = watch.header_pattern()
        if target_pattern is not None:
          match = re.match(target_pattern, header_value)
          if match is not None:
            observer.tell(message)
        target_value = watch.header_value()
        if target_value is not None and header_value == target_value:
          observer.tell(message)

  def _initialize(self, message):
    if isinstance(message, EventSocketProxyInitEvent):
      self.__client__ = message.client()
    else:
      self.__events__ = []
      self.__rules__ = []
      self.__server__ = message.server()
      for item in message.meta():
        if item and item.has_key('freeswitch'):
          freeswitch = item.get('freeswitch')
          events = freeswitch.get('events')
          if events is not None and len(events) > 0:
            self.__events__.extend(events)
          rules = freeswitch.get('rules')
          if rules is not None and len(rules) > 0:
            try:
              for rule in rules:
                header = rule.get('header_name')
                value = rule.get('header_value')
                pattern = rule.get('header_pattern')
                if header is not None and value is not None or \
                   pattern is not None:
                  self.__rules__.append(rule)
                  singleton = rule.get('singleton')
                  target = rule.get('target')
                  self.__server__.tell(RegisterActorCommand(target, singleton))
                  self.__logger__.info('Registered %s' % target)
            except Exception as e:
              name = item.get('name')
              if name is not None:
                self.__logger__.error('There was an error loading %s' % name)
              self.__logger__.exception(e)
      self.__events__ = set(self.__events__)
      self._start()

  def _lock(self, message):
    self.__owner__ = message.owner()

  def _start(self):
    proxy = EventSocketProxy(self)
    reactor.connectTCP(
      settings.freeswitch.get('address'),
      settings.freeswitch.get('port'),
      EventSocketClientFactory(proxy)
    )

  def _unlock(self, message):
    self.__owner__ = None

  def _unwatch(self, message):
    for idx in xrange(len(self.__watches__)):
      watch = self.__watches__[idx]
      if message.observer().urn == \
         watch.observer().urn:
        if message.header_name() == watch.header_name() and \
           message.header_pattern() == watch.header_pattern() and \
           message.header_value() == watch.header_value():
          del self.__watches__[idx]
          break

  def _watch(self, message):
    self.__watches__.append(message)

  def receive(self, message):
    if isinstance(message, EventSocketCommand):
      self._dispatch_command(message)
    elif isinstance(message, EventSocketEvent):
      content_type = message.headers().get('Content-Type')
      if content_type == 'auth/request':
        self._dispatch_auth(message)
      else:
        self._dispatch_event(message)
    elif isinstance(message, EventSocketWatchCommand):
      self._watch(message)
    elif isinstance(message, EventSocketUnwatchCommand):
      self._unwatch(message)
    elif isinstance(message, EventSocketLockCommand):
      self._lock(message)
    elif isinstance(message, EventSocketUnlockCommand):
      self._unlock(message)
    elif isinstance(message, EventSocketProxyInitEvent):
      self._initialize(message)
    elif isinstance(message, ServerInitEvent):
      self._initialize(message)

class EventSocketProxy(object):
  def __init__(self, dispatcher):
    self._dispatcher = dispatcher

  def consume(self, event):
    self._dispatcher.tell(event)

  def start(self, client):
    self._dispatcher.tell(EventSocketProxyInitEvent(client))

class EventSocketEvent(object):
  def __init__(self, headers, body = None):
    self._body = body
    self._headers = headers

  def body(self):
    return self._body

  def headers(self):
    return self._headers

class EventSocketQueryRequest(object):
  def __init__(self, observer):
    self._observer = observer

  def observer(self):
    return self._observer

class EventSocketQueryResponse(object):
  def __init__(self, events):
    self._events = events

  def events(self):
    return self._events

class EventSocketProxyInitEvent(object):
  def __init__(self, client):
    self._client = client

  def client(self):
    return self._client

class EventSocketLockCommand(object):
  def __init__(self, owner):
    self._owner = owner

  def owner(self):
    return self._owner

class EventSocketUnlockCommand(object):
  def __init__(self, *args, **kwargs):
    super(EventSocketUnlockCommand, self).__init__(*args, **kwargs)

class BaseEventSocketWatchCommand(object):
  def __init__(self, observer, header_name,
               header_pattern = None,
               header_value = None):
    self._header_name = header_name
    self._header_pattern = header_pattern
    self._header_value = header_value
    self._observer = observer

  def header_name(self):
    return self._header_name

  def header_pattern(self):
    return self._header_pattern

  def header_value(self):
    return self._header_value

  def observer(self):
    return self._observer

class EventSocketWatchCommand(BaseEventSocketWatchCommand):
  def __init__(self, *args, **kwargs):
    super(EventSocketWatchCommand, self).__init__(*args, **kwargs)

class EventSocketUnwatchCommand(BaseEventSocketWatchCommand):
  def __init__(self, *args, **kwargs):
    super(EventSocketUnwatchCommand, self).__init__(*args, **kwargs)
