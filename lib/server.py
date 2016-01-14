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

from pykka import ActorDeadError, ThreadingActor
from threading import Thread
from twisted.internet import reactor

import settings
import json
import logging
import os
import pykka
import signal
import sys

class ActorRegistry(object):
  def __init__(self, create_msg = None, destroy_msg = None):
    self.__create_msg__ = create_msg
    self.__destroy_msg__ = destroy_msg
    self.__klasses__ = dict()
    self.__singletons__ = dict()

  def __klass__(self, path):
    module = sys.modules.get(path)
    if not module:
      offset = path.rfind('.')
      prefix = path[:offset]
      klass = path[offset + 1:]
      module = __import__(prefix, globals(), locals(), [klass], -1)
      return getattr(module, klass)

  def exists(self, path, singleton = False):
    return self.__klasses__.has_key(path) or \
           self.__singletons__.has_key(path)

  def get(self, path):
    if self.__klasses__.has_key(path):
      klass = self.__klasses__.get(path)
      actor = klass.start()
      if self.__create_msg__ is not None:
        try:
          actor.tell({ 'body': self.__create_msg__ })
        except ActorDeadError as e:
          pass
      return actor
    elif self.__singletons__.has_key(path):
      return self.__singletons__.get(path)
    else:
      return None

  def register(self, path, singleton = False):
    klass = self.__klass__(path)
    if not singleton:
      self.__klasses__.update({ path: klass })
    else:
      actor = klass.start()
      if self.__create_msg__ is not None:
        try:
          actor.tell({ 'body': self.__create_msg__ })
        except ActorDeadError as e:
          pass
      self.__singletons__.update({ path: actor })

  def shutdown(self):
    paths = self.__singletons__.keys()
    for path in paths:
      self.unregister(path)

  def unregister(self, path):
    if self.__klasses__.has_key(path):
      del self.__klasses__[path]
    elif self.__singletons__.has_key(path):
      actor = self.__singletons__.get(path)
      if actor.is_alive():
        if self.__destroy_msg__ is not None:
          try:
            actor.tell({ 'body': self.__destroy_msg__ })
          except ActorDeadError as e:
            pass
        actor.stop()
      del self.__singletons__[path]

class Bootstrap(object):
  def __init__(self, *args, **kwargs):
    self.__logger__ = logging.getLogger('lib.server.Bootstrap')
    self.__cwd__ = os.path.dirname(os.path.realpath(__file__))
    self.__cwd__ = os.path.dirname(self.__cwd__)

  def __create_server__(self, meta):
    return Server.start(meta = meta)

  def __load_meta__(self):
    apps = os.path.join(self.__cwd__, 'applications')
    meta = []
    for item in os.listdir(apps):
      path = os.path.join(apps, item)
      if not os.path.isdir(path):
        continue
      metafile = os.path.join(path, 'metafile.json')
      if not os.path.exists(metafile):
        self.__logger__.warning('The application %s is missing a metafile.' % \
                                item)
        continue
      with open(metafile, 'r') as input:
        try:
          meta.append(json.loads(input.read()))
        except Exception as e:
          self.__logger__.warning('There was an error reading the ' + \
                                  'metafile for %s.' % item)
          self.__logger__.exception(e)
          continue
    return meta

  def start(self):
    logging.basicConfig(
      filename = settings.logging.get('filename'),
      format = settings.logging.get('format'),
      level = settings.logging.get('level')
    )
    meta = self.__load_meta__()
    server = self.__create_server__(meta)
    server.tell({
      'body': BootstrapCompleteEvent()
    })
    # Register interrupt signal handler.
    def signal_handler(signal, frame):
      self.__logger__.critical('FreePy is now shutting down!!!')
      pykka.registry.ActorRegistry.stop_all()
    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()

class Server(ThreadingActor):
  def __init__(self, *args, **kwargs):
    super(Server, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('lib.server.Server')
    self.__applications__ = ActorRegistry(
      create_msg = ServerInfoEvent(self.actor_ref),
      destroy_msg = ServerDestroyEvent()
    )
    self.__meta__ = kwargs.get('meta')
    self.__observers__ = {}
    self.__reactor__ = Thread(target = reactor.run, args = (False,))
    self.__services__ = ActorRegistry(
      create_msg = ServerInitEvent(self.actor_ref, self.__meta__),
      destroy_msg = ServerDestroyEvent()
    )

  def __fqn__(self, obj):
    if type(obj) == type:
      module = obj.__module__
      klass = obj.__name__
    else:
      module = obj.__class__.__module__
      klass = obj.__class__.__name__
    return '%s.%s' % (module, klass)

  def __broadcast__(self, fqn, message):
    recipients = self.__observers__.get(fqn)
    for recipient in recipients:
      try:
        recipient.tell({ 'body': message })
      except ActorDeadError as e:
        pass

  def __register__(self, message):
    self.__applications__.register(
      'applications.%s' % message.fqn(),
      message.singleton()
    )

  def __start_services__(self):
    for service in settings.services:
      try:
        target = service.get('target')
        self.__services__.register(target, singleton = True)
        messages = service.get('messages')
        if messages is not None and len(messages) > 0:
          observer = self.__services__.get(target)
          for message in messages:
            if not self.__observers__.has_key(message):
              self.__observers__.update({ message: [observer] })
            else:
              self.__observers__.get(message).append(observer)
        if service.has_key('name'):
          self.__logger__.info('Loaded %s' % service.get('name'))
      except Exception as e:
        name = service.get('name')
        if name is not None:
          self.__logger__.error('There was an error loading %s' % name)
        self.__logger__.exception(e)
    self.__reactor__.start()

  def __unicast__(self, message):
    recipient = None
    target = 'applications.%s' % message.target()
    if self.__services__.exists(target):
      recipient = self.__services__.get(target)
    elif self.__applications__.exists(target):
      recipient = self.__applications__.get(target)
    if recipient is not None:
      try:
        recipient.tell({ 'body': message.message() })
      except ActorDeadError as e:
        pass

  def __unwatch__(self, message):
    fqn = self.__fqn__(message.message())
    observer = message.observer()
    if self.__observers__.has_key(fqn):
      recipients = self.__observers__.get(fqn)
      for idx in xrange(len(recipients)):
        if observer.actor_urn == recipients[idx].actor_urn:
          del recipients[idx]

  def __watch__(self, message):
    fqn = self.__fqn__(message.message())
    observer = message.observer()
    if not self.__observers__.has_key(fqn):
      self.__observers__.update({ fqn: [observer] })
    else:
      self.__observers__.get(fqn).append(observer)

  def on_receive(self, message):
    message = message.get('body')
    fqn = self.__fqn__(message)
    if isinstance(message, RouteMessageCommand):
      self.__unicast__(message)
    elif self.__observers__.has_key(fqn):
      self.__broadcast__(fqn, message)
    elif isinstance(message, WatchMessagesCommand):
      self.__watch__(message)
    elif isinstance(message, UnwatchMessagesCommand):
      self.__unwatch__(message)
    elif isinstance(message, RegisterActorCommand):
      self.__register__(message)
    elif isinstance(message, BootstrapCompleteEvent):
      self.__start_services__()

  def on_stop(self):
    self.__applications__.shutdown()
    self.__services__.shutdown()
    reactor.stop()

class BootstrapCompleteEvent(object):
  def __init__(self, *args, **kwargs):
    super(BootstrapCompleteEvent, self).__init__(*args, **kwargs)

class RegisterActorCommand(object):
  def __init__(self, fqn, singleton = False):
    self.__fqn__ = fqn
    self.__singleton__ = singleton

  def fqn(self):
    return self.__fqn__

  def singleton(self):
    return self.__singleton__

class RouteMessageCommand(object):
  def __init__(self, message, target):
    self.__message__ = message
    self.__target__ = target

  def message(self):
    return self.__message__

  def target(self):
    return self.__target__

class ServerInfoEvent(object):
  def __init__(self, server):
    self.__server__ = server

  def server(self):
    return self.__server__

class ServerInitEvent(object):
  def __init__(self, server, meta):
    self.__server__ = server
    self.__meta__ = meta

  def meta(self):
    return self.__meta__

  def server(self):
    return self.__server__

class ServerDestroyEvent(object):
  def __init__(self, *args, **kwargs):
    super(ServerDestroyEvent, self).__init__(*args, **kwargs)

class WatchMessagesCommand(object):
  def __init__(self, message, observer):
    self.__message__ = message
    self.__observer__ = observer

  def message(self):
    return self.__message__

  def observer(self):
    return self.__observer__

class UnwatchMessagesCommand(object):
  def __init__(self, message, observer):
    self.__message__ = message
    self.__observer__ = observer

  def message(self):
    return self.__message__

  def observer(self):
    return self.__observer__