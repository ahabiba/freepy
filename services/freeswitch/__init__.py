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
from lib.application import Actor
from lib.fsm import *
from lib.server import RegisterActorCommand, RouteMessageCommand, \
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
import settings
import urllib

class EventSocketBootstrapper(FiniteStateMachine, Actor):
  initial_state = 'idle'

  transitions = [
    ('idle', 'authenticating'),
    ('authenticating', 'failed'),
    ('authenticating', 'bootstrapping'),
    ('bootstrapping', 'failed'),
    ('bootstrapping', 'done')
  ]

  def __init__(self, *args, **kwargs):
    super(EventSocketBootstrapper, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger(
      'services.freeswitch.EventSocketBootstrapper'
    )
    self.__dispatcher__ = kwargs.get('dispatcher')
    self.__events__ = kwargs.get('events')
    self.__password__ = settings.freeswitch.get('password')

  @Action(state = 'authenticating')
  def __authenticate__(self):
    self.__dispatcher__.tell(EventSocketLockCommand(self))
    self.__dispatcher__.tell(AuthCommand(self, password = self.__password__))

  @Action(state = 'bootstrapping')
  def __bootstrap__(self):
    unsorted = self.__events__
    sorted = ['BACKGROUND_JOB']
    for event in unsorted:
      if not event == 'CUSTOM' and event.find('::') == -1:
        sorted.append(event)
    if 'CUSTOM' in unsorted:
      sorted.append('CUSTOM')
    for event in unsorted:
      if event.find('::') > -1:
        sorted.append(event)
    self.__dispatcher__.tell(EventsCommand(self, events = sorted))

  @Action(state = 'done')
  def __finish__(self):
    self.__dispatcher__.tell(EventSocketUnlockCommand())

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
    self.__logger__ = logging.getLogger(
      'services.freeswitch.EventSocketClient'
    )
    self.__buffer__ = None
    self.__host__ = None
    self.__observer__ = observer
    self.__peer__ = None

  def __parse__(self):
    # Make sure we have enough data to process the event.
    buffer_contents = self.__buffer__.getvalue()
    if len(buffer_contents) == 0 or not buffer_contents.find('\n\n'):
      return None
    else:
      # Parse the event for processing.
      self.__buffer__.seek(0)
      body = None
      headers = self.__parse_headers__()
      length = headers.get('Content-Length')
      if length:
        length = int(length)
        # Remove the Content-Length header.
        del headers['Content-Length']
        # Make sure we have enough data to process the body.
        offset = self.__buffer__.tell()
        self.__buffer__.seek(0, SEEK_END)
        end = self.__buffer__.tell()
        remaining = end - offset
        # Handle the event body.
        if length <= remaining:
          self.__buffer__.seek(offset)
          type = headers.get('Content-Type')
          if type and type == 'text/event-plain':
            headers.update(self.__parse_headers__())
            length = headers.get('Content-Length')
            if length:
              length = int(length)
              del headers['Content-Length']
              body = self.__buffer__.read(length)
          else:
            body = self.__buffer__.read(length)
        else:
          return None
      # Reclaim resources.
      offset = self.__buffer__.tell()
      self.__buffer__.seek(0, SEEK_END)
      end = self.__buffer__.tell()
      remaining = end - offset
      if remaining == 0:
        self.__buffer__.seek(0)
        self.__buffer__.truncate(0)
      else:
        self.__buffer__.seek(offset)
        data = self.__buffer__.read(remaining)
        self.__buffer__.seek(0)
        self.__buffer__.write(data)
        self.__buffer__.truncate(remaining)
      return EventSocketEvent(headers, body)

  def __parse_headers__(self):
    headers = dict()
    while True:
      line = self.__parse_line__()
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

  def __parse_line__(self, stride = 64):
    line = list()
    while True:
      chunk = self.__buffer__.read(stride)
      end = chunk.find('\n')
      if end == -1:
        line.append(chunk)
      else:
        line.append(chunk[:end])
        offset = self.__buffer__.tell()
        left_over = len(chunk[end + 1:])
        self.__buffer__.seek(offset - left_over)
        break
      if len(chunk) < stride:
        break
    return ''.join(line)

  def connectionLost(self, reason):
    message = 'A connection to the FreeSWITCH instance '
    message += 'located @ %s:%i has been lost due to the ' % \
               (self.__peer__.host, self.__peer__.port)
    message += 'following reason.\n%s' % reason
    self.__logger__.critical(message)
    if self.__buffer__:
      self.__buffer__.close()
    self.__buffer__ = None
    self.__host__ = None
    self.__peer__ = None

  def connectionMade(self):
    self.__buffer__ = StringIO()
    self.__host__ = self.transport.getHost()
    self.__peer__ = self.transport.getPeer()
    self.__observer__.start(self)

  def dataReceived(self, data):
    if self.__logger__.isEnabledFor(logging.DEBUG):
      message = 'Message From %s:%i\n%s' % \
                (self.__peer__.host, self.__peer__.port, data)
      self.__logger__.debug(message)
    self.__buffer__.write(data)
    while True:
      event = self.__parse__()
      if event:
        self.__observer__.consume(event)
      else:
        break

  def send(self, command):
    serialized_command = str(command)
    if self.__logger__.isEnabledFor(logging.DEBUG):
      message = 'The following message will be sent to %s:%i.\n%s' % \
                (self.__peer__.host, self.__peer__.port, serialized_command)
      self.__logger__.debug(message)
    self.transport.write(serialized_command)

class EventSocketClientFactory(ReconnectingClientFactory):
  def __init__(self, observer):
    self.__logger__ = logging.getLogger(
      'services.freeswitch.EventSocketClientFactory'
    )
    self.__observer__ = observer

  def buildProtocol(self, addr):
    self.__logger__.info('Connected to the FreeSWITCH instance ' +
                         'located @ %s:%i.' % (addr.host, addr.port))
    self.resetDelay()
    return EventSocketClient(self.__observer__)

class EventSocketDispatcher(Actor):
  def __init__(self, *args, **kwargs):
    super(EventSocketDispatcher, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger(
      'services.freeswitch.EventSocketDispatcher'
    )
    self.__observers__ = {}
    self.__owner__ = None
    self.__transactions__ = {}
    self.__watches__ = []

  def __dispatch_auth__(self, message):
    bootstrapper = EventSocketBootstrapper(
      dispatcher = self,
      events = self.__events__,
      router = self.__router__
    )
    bootstrapper.tell(message)

  def __dispatch_command__(self, message):
    observer = message.sender()
    if isinstance(message, BackgroundCommand):
      uuid = message.job_uuid()
      self.__observers__.update({ uuid: observer })
      self.__transactions__.update({ uuid: observer })
    self.__client__.send(message)

  def __dispatch_event__(self, message):
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

  def __initialize__(self, message):
    if isinstance(message, EventSocketProxyInitEvent):
      self.__client__ = message.client()
    else:
      self.__events__ = []
      self.__rules__ = []
      self.__server__ = message.server()
      for item in message.meta():
        if item.has_key('freeswitch'):
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
      self.__start__()

  def __lock__(self, message):
    self.__owner__ = message.owner()

  def __start__(self):
    proxy = EventSocketProxy(self)
    reactor.connectTCP(
      settings.freeswitch.get('address'),
      settings.freeswitch.get('port'),
      EventSocketClientFactory(proxy)
    )

  def __unlock__(self, message):
    self.__owner__ = None

  def __unwatch__(self, message):
    for idx in xrange(len(self.__watches__)):
      watch = self.__watches__[idx]
      if message.observer().urn() == \
         watch.observer().urn():
        if message.header_name() == watch.header_name() and \
           message.header_pattern() == watch.header_pattern() and \
           message.header_value() == watch.header_value():
          del self.__watches__[idx]

  def __watch__(self, message):
    self.__watches__.append(message)

  def receive(self, message):
    if isinstance(message, EventSocketCommand):
      self.__dispatch_command__(message)
    elif isinstance(message, EventSocketEvent):
      content_type = message.headers().get('Content-Type')
      if content_type == 'auth/request':
        self.__dispatch_auth__(message)
      else:
        self.__dispatch_event__(message)
    elif isinstance(message, EventSocketWatchCommand):
      self.__watch__(message)
    elif isinstance(message, EventSocketUnwatchCommand):
      self.__unwatch__(message)
    elif isinstance(message, EventSocketLockCommand):
      self.__lock__(message)
    elif isinstance(message, EventSocketUnlockCommand):
      self.__unlock__(message)
    elif isinstance(message, EventSocketProxyInitEvent):
      self.__initialize__(message)
    elif isinstance(message, ServerInitEvent):
      self.__initialize__(message)

class EventSocketProxy(object):
  def __init__(self, dispatcher):
    self.__dispatcher__ = dispatcher

  def consume(self, event):
    self.__dispatcher__.tell(event)

  def start(self, client):
    self.__dispatcher__.tell(EventSocketProxyInitEvent(client))

class EventSocketEvent(object):
  def __init__(self, headers, body = None):
    self.__body__ = body
    self.__headers__ = headers

  def body(self):
    return self.__body__

  def headers(self):
    return self.__headers__

class EventSocketQueryRequest(object):
  def __init__(self, observer):
    self.__observer__ = observer

  def observer(self):
    return self.__observer__

class EventSocketQueryResponse(object):
  def __init__(self, events):
    self.__events__ = events

  def events(self):
    return self.__events__

class EventSocketProxyInitEvent(object):
  def __init__(self, client):
    self.__client__ = client

  def client(self):
    return self.__client__

class EventSocketLockCommand(object):
  def __init__(self, owner):
    self.__owner__ = owner

  def owner(self):
    return self.__owner__

class EventSocketUnlockCommand(object):
  def __init__(self, *args, **kwargs):
    super(EventSocketUnlockCommand, self).__init__(*args, **kwargs)

class EventSocketWatchCommand(object):
  def __init__(self, observer, header_name,
               header_pattern = None,
               header_value = None):
    self.__header_name__ = header_name
    self.__header_pattern__ = header_pattern
    self.__header_value__ = header_value
    self.__observer__ = observer

  def header_name(self):
    return self.__header_name__

  def header_pattern(self):
    return self.__header_pattern__

  def header_value(self):
    return self.__header_value__

  def observer(self):
    return self.__observer__

class EventSocketUnwatchCommand(EventSocketWatchCommand):
  def __init__(self, observer, header_name,
               header_pattern = None,
               header_value = None):
    super(EventSocketUnwatchCommand, self).__init__(
      observer, header_name, header_pattern, header_value
    )