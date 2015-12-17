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

from lib.commands import *
from lib.core import *
from lib.esl import *
from lib.fsm import *
from lib.services import *
from pykka import ActorRegistry, ThreadingActor
from twisted.internet import reactor

import conf.settings
import json
import logging
import os
import re
import sys
import tarfile
import zipfile

class InitializeDispatcherEvent(object):
  def __init__(self, registry, events, mappings, rules):
    self.__registry__ = registry
    self.__events__ = events
    self.__mappings__ = mappings
    self.__rules__ = rules

  def get_registry(self):
    return self.__registry__

  def get_events(self):
    return self.__events__

  def get_mappings(self):
    return self.__mappings__

  def get_rules(self):
    return self.__rules__

class KillDispatcherEvent(object):
  pass

class DispatcherProxy(IEventSocketClientObserver):
  def __init__(self, registry, dispatcher, events, mappings, rules):
    self.__registry__ = registry
    self.__dispatcher__ = dispatcher
    self.__events__ = events
    self.__mappings__ = mappings
    self.__rules__ = rules

  def on_event(self, event):
    self.__dispatcher__.tell({'body': event})

  def start(self, client):
    event = InitializeDispatcherEvent(
      self.__registry__,
      self.__events__,
      self.__mappings__,
      self.__rules__
    )
    self.__dispatcher__.tell({'body': event})

  def stop(self):
    event = KillDispatcherEvent()
    self.__dispatcher__.tell({'body': event})

class Dispatcher(FiniteStateMachine, ThreadingActor):
  initial_state = 'not ready'

  transitions = [
    ('not ready', 'authenticating'),
    ('authenticating', 'failed authentication'),
    ('authenticating', 'initializing'),
    ('initializing', 'failed initialization'),
    ('initializing', 'dispatching'),
    ('dispatching', 'dispatching'),
    ('dispatching', 'done')
  ]

  def __init__(self, *args, **kwargs):
    super(Dispatcher, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('freepy.lib.server.dispatcher')
    self.__observers__ = dict()
    self.__transactions__ = dict()
    self.__watches__ = list()

  @Action(state = 'authenticating')
  def __authenticate__(self, message):
    password = freeswitch_host.get('password')
    auth_command = AuthCommand(password)
    self.__client__.send(auth_command)

  @Action(state = 'done')
  def __cleanup__(self, message):
    self.__apps__.shutdown()
    self.stop()

  @Action(state = 'dispatching')
  def __dispatch__(self, message):
    if message:
      if isinstance(message, BackgroundCommand):
        self.__dispatch_command__(message)
      elif isinstance(message, ServiceRequest):
        self.__dispatch_service_request__(message)
      elif isinstance(message, RegisterJobObserverCommand):
        observer = message.get_observer()
        uuid = message.get_job_uuid()
        if observer and uuid:
          self.__observers__.update({uuid: observer})
      elif isinstance(message, UnregisterJobObserverCommand):
        uuid = message.get_job_uuid()
        if self.__observers__.has_key(uuid):
          del self.__observers__[uuid]
      else:
        headers = message.get_headers()
        content_type = headers.get('Content-Type')
        if content_type == 'command/reply':
          uuid = headers.get('Job-UUID')
          if uuid:
            self.__dispatch_response__(uuid, message)
        elif content_type == 'text/event-plain':
          uuid = headers.get('Job-UUID')
          if uuid:
            self.__dispatch_observer_event__(uuid, message)
          else:
            self.__dispatch_incoming__(message)

  def __dispatch_command__(self, message):
    # Make sure we can route the response to the right actor.
    uuid = message.get_job_uuid()
    sender = message.get_sender()
    self.__transactions__.update({uuid: sender})
    # Send the command.
    self.__client__.send(message)

  def __dispatch_incoming__(self, message):
    if not self.__dispatch_incoming_using_dispatch_rules__(message) and \
       not self.__dispatch_incoming_using_watches__(message):
      self.__logger__.info('No route was defined for the following message.\n \
      %s\n%s', str(message.get_headers()), str(message.get_body()))

  def __dispatch_incoming_using_dispatch_rules__(self, message):
    headers = message.get_headers()
    # Dispatch based on the pre-defined dispatch rules.
    for rule in dispatch_rules:
      target = rule.get('target')
      name = rule.get('header_name')
      header = headers.get(name)
      if not header:
        continue
      value = rule.get('header_value')
      if value and header == value:
        self.__apps__.get_instance(target).tell({'content': message})
        return True
      pattern = rule.get('header_pattern')
      if pattern:
        match = re.search(pattern, header)
        if match:
          self.__apps__.get_intance(target).tell({'content': message})
          return True
    return False

  def __dispatch_incoming_using_watches__(self, message):
    headers = message.get_headers()
    # Dispatch based on runtime watches defined by switchlets.
    result = None
    for watch in self.__watches__:
      name = watch.get_name()
      header = headers.get(name)
      if not header:
        continue
      value = watch.get_value()
      if value and header == value:
        result = watch
      pattern = watch.get_pattern()
      if pattern:
        match = re.search(pattern, header)
        if match:
          result = watch
    if result:
      observer = result.get_observer()
      if observer.is_alive():
        observer.tell({'content': message})
        return True
      else:
        self.__watches__.remove(result)
    return False

  def __dispatch_observer_event__(self, uuid, message):
    recipient = self.__observers__.get(uuid)
    if recipient:
      if recipient.is_alive():
        recipient.tell({'content': message})
      else:
        del self.__observers__[uuid]

  def __dispatch_response__(self, uuid, message):
    recipient = self.__transactions__.get(uuid)
    if recipient:
      del self.__transactions__[uuid]
      if recipient.is_alive():
        recipient.tell({'content': message})

  def __dispatch_service_request__(self, message):
    name = message.__class__.__name__
    target = self.__events__.get(name)
    if target:
      service = self.__apps__.get_instance(target)
      service.tell({ 'content': message })

  @Action(state = 'initializing')
  def __initialize__(self, message):
    if 'BACKGROUND_JOB' not in dispatch_events:
      # The BACKGROUND_JOB events must be added at the front of the
      # list in case the list ends with CUSTOM events.
      dispatch_events.insert(0, 'BACKGROUND_JOB')
    events_command = EventsCommand(dispatch_events)
    self.__client__.send(events_command)

  def __on_auth__(self, message):
    if self.state() == 'not ready':
      self.transition(to = 'authenticating', event = message)

  def __on_command__(self, message):
    if self.state() == 'dispatching':
      self.transition(to = 'dispatching', event = message)

  def __on_command_reply__(self, message):
    reply = message.get_header('Reply-Text')
    if self.state() == 'authenticating':
      if reply == '+OK accepted':
        self.transition(to = 'initializing', event = message)
      elif reply == '-ERR invalid':
        self.transition(to = 'failed authentication', event = message)
    if self.state() == 'initializing':
      if reply == '+OK event listener enabled plain':
        self.transition(to = 'dispatching')
      elif reply == '-ERR no keywords supplied':
        self.transition(to = 'failed initialization', event = message)
    if self.state() == 'dispatching':
      self.transition(to = 'dispatching', event = message)

  def __on_event__(self, message):
    if self.state() == 'dispatching':
      self.transition(to = 'dispatching', event = message)

  def __on_init__(self, message):
    self.__apps__ = message.get_apps()
    self.__client__ = message.get_client()
    self.__events__ = message.get_events()

  def __on_kill__(self, message):
    if self.state() == 'dispatching':
      self.transition(to = 'done', event = message)

  def __on_observer__(self, message):
    if self.state() == 'dispatching':
      self.transition(to = 'dispatching', event = message)

  def __on_service_request__(self, message):
    if self.state() == 'dispatching':
      self.transition(to = 'dispatching', event = message)

  # Watches are not handled as a state change because singleton switchlets
  # may add watches during initialization at which point the dispatcher's
  # FSM is still not ready.
  def __on_watch__(self, message):
    if isinstance(message, WatchEventCommand):
      self.__watches__.append(message)
    elif isinstance(message, UnwatchEventCommand):
      name = message.get_name()
      value = message.get_value()
      if not value:
        value = message.get_pattern()
      match = None
      for watch in self.__watches__:
        if name == watch.get_name() and value == watch.get_value() or \
           value == watch.get_pattern:
          match = watch
      if match:
        self.__watches__.remove(match)

  def on_failure(self, exception_type, exception_value, traceback):
    self.__logger__.error(exception_value)

  def on_receive(self, message):
    # This is necessary because all Pykka messages
    # must be of type dict.
    message = message.get('content')
    if not message:
      return
    # Handle the message.
    if isinstance(message, Event):
      content_type = message.get_header('Content-Type')
      if content_type == 'auth/request':
        self.__on_auth__(message)
      elif content_type == 'command/reply':
        self.__on_command_reply__(message)
      elif content_type == 'text/event-plain':
        self.__on_event__(message)
    elif isinstance(message, BackgroundCommand):
      self.__on_command__(message)
    elif isinstance(message, ServiceRequest):
      self.__on_service_request__(message)
    elif isinstance(message, RegisterJobObserverCommand):
      self.__on_observer__(message)
    elif isinstance(message, UnregisterJobObserverCommand):
      self.__on_observer__(message)
    elif isinstance(message, InitializeDispatcherEvent):
      self.__on_init__(message)
    elif isinstance(message, KillDispatcherEvent):
      self.__on_kill__(message)
    elif isinstance(message, UnwatchEventCommand):
      self.__on_watch__(message)
    elif isinstance(message, WatchEventCommand):
      self.__on_watch__(message)

class ApplicationLoader(object):
  def __init__(self, registry, events, rules):
    self.__logger__ = logging.getLogger('freepy.lib.server.applicationloader')
    cwd = os.path.dirname(os.path.realpath(__file__))
    cwd = os.path.dirname(cwd)
    self.__apps__ = os.path.join(cwd, 'applications')
    self.__events__ = events
    self.__registry__ = registry
    self.__rules__ = rules

  def __is_valid__(self, meta):
    if not meta.has_key('events') or \
       not meta.has_key('rules'):
      return False
    if type(meta.get('events')) is not list or \
       type(meta.get('rules')) is not list:
      return False
    for event in meta.get('events'):
      if type(event) is not str and \
         type(event) is not unicode:
        return False
    for rule in meta.get('rules'):
      if type(rule) is not dict:
        return False
      header = rule.get('header_name')
      target = rule.get('target')
      if header is None or target is None:
        return False
      value = rule.get('header_value')
      pattern = rule.get('header_pattern')
      if value is not None and pattern is not None or \
         value is None and pattern is None:
        return False
    return True

  def load(self):
    root = os.listdir(self.__apps__)
    for item in root:
      path = os.path.join(self.__apps__, item)
      if not os.path.isdir(path):
        continue
      metafile = os.path.join(path, 'metafile.json')
      if not os.path.exists(metafile):
        self.__logger__.warning('The application %s is missing a metafile.' % \
                                item)
        continue
      with open(metafile, 'r') as input:
        try:
          meta = json.loads(input.read())
        except Exception as e:
          self.__logger__.warning('There was an error reading the ' + \
                                  'metafile for %s.' % item)
          self.__logger__.exception(e)
          continue
      if not self.__is_valid__(meta):
        self.__logger__.warning('The metafile for %s is invalid.' % item)
        continue
      for event in meta.get('events'):
        self.__events__.append(event)
      for rule in meta.get('rules'):
        rule.update({ 'target': 'applications.%s' % rule.get('target') })
        if not rule.get('singleton', False):
          self.__registry__.register(rule.get('target'))
        else:
          self.__registry__.register(rule.get('target'), singleton = True)
        self.__rules__.append(rule)
      if meta.has_key('name'):
        self.__logger__.info('Loaded %s' % meta.get('name'))

class ApplicationRegistry(object):
  def __init__(self, create_msg = None, destroy_msg = None):
    self.__singletons__ = dict()
    self.__klasses__ = dict()
    self.__create_msg__ = create_msg
    self.__destroy_msg__ = destroy_msg

  def __klass__(self, path):
    module = sys.modules.get(path)
    if not module:
      offset = path.rfind('.')
      prefix = path[:offset]
      klass = path[offset + 1:]
      module = __import__(prefix, globals(), locals(), [klass], -1)
      return getattr(module, klass)

  def exists(self, path, singleton = False):
    if not singleton:
      return self.__klasses__.has_key(path)
    else:
      return self.__singletons__.has_key(path)

  def get(self, path):
    if self.__klasses__.has_key(path):
      klass = self.__klasses__.get(path)
      switchlet = klass().start()
      switchlet.tell({ 'body': self.__create_msg__ })
      return switchlet
    elif self.__singletons__.has_key(path):
      return self.__singletons__.get(path)
    else:
      return None

  def register(self, path, singleton = False):
    klass = self.__klass__(path)
    if not singleton:
      self.__klasses__.update({ path: klass })
    else:
      switchlet = klass().start()
      switchlet.tell({ 'body': self.__create_msg__ })
      self.__singletons__.update({ path: switchlet })

  def shutdown(self):
    paths = self.__singletons__.keys()
    for path in paths:
      self.unregister(path)

  def unregister(self, path):
    if self.__klasses__.has_key(path):
      del self.__klasses__[path]
    elif self.__singletons__.has_key(path):
      switchlet = self.__singletons__.get(path)
      if switchlet.is_alive():
        switchlet.tell({ 'body': self.__destroy_msg__ })
        switchlet.stop()
      del self.__singletons__[path]

class ApplicationWatchdog(object):
  def __init__(self, *args, **kwargs):
    pass

class ServiceLoader(object):
  def __init__(self, config, registry, mappings):
    self.__logger__ = logging.getLogger('freepy.lib.server.serviceloader')
    self.__config__ = config
    self.__mappings__ = mappings
    self.__registry__ = registry

  def __is_valid__(self, config):
    if type(config) is not list:
      return False
    for service in config:
      if not service.has_key('events'):
        return False
      events = service.get('events')
      if type(events) is not list:
        return False
      for event in events:
        if type(event) is not str and \
           type(event) is not unicode:
          return False
      if not service.has_key('target'):
        return False
    return True

  def load(self):
    if not self.__is_valid__(self.__config__):
      self.__logger__.warning('The services configuration is invalid.')
      return
    for service in self.__config__:
      self.__registry__.register(service.get('target'), singleton = True)
      for event in service.get('events'):
        self.__mappings__.update({ event: service.get('target') })
      if service.has_key('name'):
        self.__logger__.info('Loaded %s' % service.get('name'))

class FreepyServer(object):
  def __init__(self, *args, **kwargs):
    self.__logger__ = logging.getLogger('freepy.lib.server.freepyserver')

  def start(self):
    # Initialize application wide logging.
    logging.basicConfig(
      filename = conf.settings.logging_filename,
      format = conf.settings.logging_format,
      level = conf.settings.logging_level
    )
    # Create a dispatcher thread.
    dispatcher = Dispatcher().start()
    registry = ApplicationRegistry(
      create_msg = InitializeSwitchletEvent(dispatcher),
      destroy_msg = KillSwitchletEvent()
    )
    events, mappings, rules = [], {}, []
    ServiceLoader(conf.settings.services, registry, mappings).load()
    ApplicationLoader(registry, events, rules).load()
    # Create the proxy between the event socket client and the dispatcher.
    proxy = DispatcherProxy(registry, dispatcher, events, mappings, rules)
    ## Create an event socket client factory and start the reactor.
    #address = freeswitch_host.get('address')
    #port = freeswitch_host.get('port')
    #factory = EventSocketClientFactory(dispatcher_proxy)
    #reactor.connectTCP(address, port, factory)
    #reactor.run()

  def stop(self):
    ActorRegistry.stop_all()
  