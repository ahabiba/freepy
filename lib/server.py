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
from lib.esl import *
from lib.fsm import *
from lib.services import *
from lib.switchlet import *
from pykka import ActorRegistry, ThreadingActor
from twisted.internet import endpoints, reactor
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Request, Site

import conf.settings
import json
import logging
import os
import re
import sys
import tarfile
import zipfile

class LockDispatcherCommand(object):
  def __init__(self, owner):
    self.__owner__ = owner

  def get_owner(self):
    return self.__owner__

class KillDispatcherCommand(object):
  pass

class QueryDispatcherCommand(object):
  def __init__(self, observer):
    self.__observer__ = observer

  def get_observer(self):
    return self.__observer__

class QueryDispatcherResponse(object):
  def __init__(self, events):
    self.__events__ = events

  def get_events(self):
    return self.__events__

class UnlockDispatcherCommand(object):
  pass

class UpdateDispatcherCommand(object):
  def __init__(self, client = None, registry = None, events = None,
               mappings = None, rules = None):
    self.__client__ = client
    self.__registry__ = registry
    self.__events__ = events
    self.__mappings__ = mappings
    self.__rules__ = rules

  def get_client(self):
    return self.__client__

  def get_registry(self):
    return self.__registry__

  def get_events(self):
    return self.__events__

  def get_mappings(self):
    return self.__mappings__

  def get_rules(self):
    return self.__rules__

class ApplicationLoader(object):
  def __init__(self, registry, events, rules):
    self.__logger__ = logging.getLogger('lib.server.applicationloader')
    cwd = os.path.dirname(os.path.realpath(__file__))
    cwd = os.path.dirname(cwd)
    self.__apps__ = os.path.join(cwd, 'applications')
    self.__events__ = events
    self.__registry__ = registry
    self.__rules__ = rules
    self.__bootstrap__()

  def __bootstrap__(self):
    self.__registry__.register('lib.server.Bootstrapper', singleton = True)
    self.__rules__.append({
      'header_name': 'Content-Type',
      'header_value': 'auth/request',
      'singleton': True,
      'target': 'lib.server.Bootstrapper'
    })

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
    singleton = meta.get('singleton')
    if singleton is not None and type(singleton) is not bool:
      return False
    if meta.has_key('urls'):
      for url in meta.get('urls'):
        if type(url) is not str and \
           type(url) is not unicode:
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

class Bootstrapper(FiniteStateMachine, Switchlet):
  initial_state = 'idle'

  transitions = [
    ('idle', 'authenticating'),
    ('authenticating', 'failed'),
    ('authenticating', 'querying'),
    ('querying', 'initializing'),
    ('initializing', 'failed'),
    ('initializing', 'done')
  ]

  def __init__(self, *args, **kwargs):
    super(Bootstrapper, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('lib.server.bootstrapper')
    self.__password__ = conf.settings.freeswitch.get('password')
    self.__queue__ = []

  @Action(state = 'authenticating')
  def __authenticate__(self, message):
    command = LockDispatcherCommand(self.actor_ref)
    self.__dispatcher__.tell({ 'body': command })
    command = AuthCommand(self.actor_ref, password = self.__password__)
    self.__dispatcher__.tell({ 'body': command })

  @Action(state = 'done')
  def __finish__(self, message):
    command = UnlockDispatcherCommand()
    self.__dispatcher__.tell({ 'body': command })
    for item in self.__queue__:
      self.__dispatcher__.tell({ 'body': item })
    self.__queue__ = []

  @Action(state = 'initializing')
  def __initialize__(self, message):
    unsorted = set(message.get_events())
    events = ['BACKGROUND_JOB']
    for event in unsorted:
      if event is not 'CUSTOM' and event.find('::') == -1:
        events.append(event)
    if 'CUSTOM' in unsorted:
      events.append('CUSTOM')
    for event in unsorted:
      if event.find('::') > -1:
        events.append(event)
    command = EventsCommand(self.actor_ref, events = events)
    self.__dispatcher__.tell({ 'body': command })

  @Action(state = 'querying')
  def __query__(self, message):
    command = QueryDispatcherCommand(self.actor_ref)
    self.__dispatcher__.tell({ 'body': command })

  def __update__(self, message):
    self.__dispatcher__ = message.get_dispatcher()

  def on_receive(self, message):
    message = message.get('body')
    if isinstance(message, InitializeSwitchletEvent):
      self.__update__(message)
    elif isinstance(message, Event):
      content_type = message.get_header('Content-Type')
      if content_type == 'auth/request':
        self.transition(to = 'authenticating', event = message)
      elif content_type == 'command/reply':
        reply = message.get_header('Reply-Text')
        if reply == '+OK accepted':
          self.transition(to = 'querying', event = message)
        elif reply == '-ERR invalid':
          self.transition(to = 'failed', event = message)
        elif reply == '+OK event listener enabled plain':
          self.transition(to = 'done')
        elif reply == '-ERR no keywords supplied':
          self.transition(to = 'failed', event = message)
    elif isinstance(message, QueryDispatcherResponse):
      self.transition(to = 'initializing', event = message)
    else:
      self.__queue__.append(message)

class Dispatcher(ThreadingActor):
  def __init__(self, *args, **kwargs):
    super(Dispatcher, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('lib.server.dispatcher')
    self.__locked__ = False
    self.__observers__ = dict()
    self.__transactions__ = dict()

  def __dispatch_command__(self, message):
    if getattr(message, 'get_job_uuid', None) is not None:
      uuid = message.get_job_uuid()
      sender = message.get_sender()
      self.__transactions__.update({ uuid: sender })
    self.__client__.send(message)

  def __dispatch_event__(self, message):
    if self.__locked__:
      self.__owner__.tell({ 'body': message })
      return
    content_type = message.get_header('Content-Type')
    if content_type == 'command/reply':
      uuid = message.get_header('Job-UUID')
      recipient = self.__transactions__.get(uuid)
      if recipient is not None:
        del self.__transactions__[uuid]
        if recipient.is_alive():
          recipient.tell({ 'body': message })
          return
    elif content_type == 'text/event-plain':
      uuid = message.get_header('Job-UUID')
      if uuid is not None:
        recipient = self.__observers__.get(uuid)
        if recipient:
          if recipient.is_alive():
            recipient.tell({ 'body': message })
          else:
            del self.__observers__[uuid]
          return
    for rule in self.__rules__:
      target = rule.get('target')
      name = rule.get('header_name')
      header = message.get_header(name)
      if header is None:
        continue
      value = rule.get('header_value')
      if value is not None and header == value:
        self.__registry__.get(target).tell({ 'body': message })
        return
      pattern = rule.get('header_pattern')
      if pattern is not None and re.match(pattern, header) is not None:
        self.__registry__.get(target).tell({ 'body': message })
        return
    if message.get_body() is not None:
      self.__logger__.warning('No route defined for:\n%s\n%s' % \
                              (message.get_headers(), message.get_body()))
    else:
      self.__logger__.warning('No route defined for:\n%s' % \
                              message.get_headers())

  def __dispatch_http_request__(self, message):
    for rule in self.__rules__:
      target = rule.get('target')
      urls = rule.get('urls')
      if urls is None:
        continue
      for url in urls:
        result = re.match(url, message.path)
        if result is not None:
          self.__registry__.get(target).tell({
            'body': message
          })
          return
    message.setResponseCode(404)
    message.write('Not Found')
    message.finish()

  def __dispatch_service_request__(self, message):
    name = message.__class__.__name__
    target = self.__mappings__.get(name)
    if target is not None:
      service = self.__registry__.get(target)
      service.tell({ 'body': message })

  def __lock__(self, message):
    self.__locked__ = True
    self.__owner__ = message.get_owner()

  def __query__(self, message):
    response = QueryDispatcherResponse(self.__events__)
    message.get_observer().tell({ 'body': response })

  def __register_job_observer__(self, message):
    observer = message.get_observer()
    uuid = message.get_job_uuid()
    if observer is not None and uuid is not None:
      self.__observers__.update({ uuid: observer })

  def __stop__(self, message):
    self.__registry__.shutdown()
    self.stop()

  def __unlock__(self, message):
    self.__locked__ = False
    self.__owner__ = None

  def __unregister_job_observer__(self, message):
    uuid = message.get_job_uuid()
    if self.__observers__.has_key(uuid):
      del self.__observers__[uuid]

  def __update__(self, message):
    if message.get_client() is not None:
      self.__client__ = message.get_client()
    if message.get_registry() is not None:
      self.__registry__ = message.get_registry()
    if message.get_events() is not None:
      self.__events__ = message.get_events()
    if message.get_mappings() is not None:
      self.__mappings__ = message.get_mappings()
    if message.get_rules() is not None:
      self.__rules__ = message.get_rules()

  def on_receive(self, message):
    message = message.get('body')
    if message is None:
      return
    if isinstance(message, Event):
      self.__dispatch_event__(message)
    elif isinstance(message, Command):
      self.__dispatch_command__(message)
    elif isinstance(message, Request):
      self.__dispatch_http_request__(message)
    elif isinstance(message, ServiceRequest):
      self.__dispatch_service_request__(message)
    elif isinstance(message, RegisterJobObserverCommand):
      self.__register_job_observer__(message)
    elif isinstance(message, UnregisterJobObserverCommand):
      self.__unregister_job_observer__(message)
    elif isinstance(message, QueryDispatcherCommand):
      self.__query__(message)
    elif isinstance(message, LockDispatcherCommand):
      self.__lock__(message)
    elif isinstance(message, UnlockDispatcherCommand):
      self.__unlock__(message)
    elif isinstance(message, UpdateDispatcherCommand):
      self.__update__(message)
    elif isinstance(message, KillDispatcherCommand):
      self.__stop__(message)

class EventSocketProxy(IEventSocketClientObserver):
  def __init__(self, dispatcher):
    self.__dispatcher__ = dispatcher

  def on_event(self, event):
    self.__dispatcher__.tell({ 'body': event })

  def start(self, client):
    event = UpdateDispatcherCommand(client = client)
    self.__dispatcher__.tell({ 'body': event })

  def stop(self):
    self.__dispatcher__.tell({ 'body': KillDispatcherCommand() })

class HttpProxy(Resource):
  isLeaf = True

  def __init__(self, dispatcher):
    self.__dispatcher__ = dispatcher

  def render(self, request):
    self.__dispatcher__.tell({ 'body': request })
    return NOT_DONE_YET

class ServiceLoader(object):
  def __init__(self, config, registry, mappings):
    self.__logger__ = logging.getLogger('lib.server.serviceloader')
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
    self.__logger__ = logging.getLogger('lib.server.freepyserver')

  def start(self):
    # Initialize application wide logging.
    logging.basicConfig(
      filename = conf.settings.logging.get('filename'),
      format = conf.settings.logging.get('format'),
      level = conf.settings.logging.get('level')
    )
    # Initialize the event socket dispatcher.
    dispatcher = Dispatcher().start()
    registry = ApplicationRegistry(
      create_msg = InitializeSwitchletEvent(dispatcher),
      destroy_msg = KillSwitchletEvent()
    )
    events, mappings, rules = [], {}, []
    loader = ServiceLoader(conf.settings.services, registry, mappings)
    loader.load()
    loader = ApplicationLoader(registry, events, rules)
    loader.load()
    command = UpdateDispatcherCommand(registry = registry,
                                      events = events,
                                      mappings = mappings,
                                      rules = rules)
    dispatcher.tell({ 'body': command })
    # Create message proxies.
    esl_proxy = EventSocketProxy(dispatcher)
    http_proxy = HttpProxy(dispatcher)
    # Connect to the FreeSWITCH Host.
    reactor.connectTCP(
      conf.settings.freeswitch.get('address'),
      conf.settings.freeswitch.get('port'),
      EventSocketClientFactory(esl_proxy)
    )
    # Listen for HTTP requests.
    reactor.listenTCP(
      conf.settings.http.get('port'),
      Site(http_proxy)
    )
    # Start the reactor.
    reactor.run()

  def stop(self):
    ActorRegistry.stop_all()
  