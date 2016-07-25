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

from freepy.lib.application import *
from threading import Thread
from twisted.internet import reactor

import json
import logging
import os
import signal
import sys

from freepy import settings

class Bootstrap(object):
  def __init__(self, *args, **kwargs):
    self.__logger__ = logging.getLogger('lib.server.Bootstrap')
    if 'settings' in kwargs:
      settings.update(kwargs.get('settings'))
    else:
      settings.update(__import__('config'))
      settings.update({'application_prefix': 'applications'})
    self.__metafile__ = kwargs.get('metafile', None)

  def __create_router__(self, n_threads):
    router = MessageRouter(n_threads = n_threads)
    router.start()
    return router

  def __create_server__(self, meta, router):
    return Server(meta = meta, router = router)

  def __load_meta__(self):
    def load_meta_file(metafile):
      if not os.path.exists(metafile):
        self.__logger__.warning('The application %s is missing a metafile.' % \
                                item)
        return
      with open(metafile, 'r') as input:
        try:
          return json.loads(input.read())
        except Exception as e:
          self.__logger__.warning('There was an error reading the ' + \
                                  'metafile for %s.' % item)
          self.__logger__.exception(e)
          return

    meta = []

    if self.__metafile__:
      metafile = os.path.join('.', self.__metafile__)
      meta.append(load_meta_file(metafile))
    else:
      cwd = os.path.dirname(os.path.realpath(__file__))
      cwd = os.path.dirname(cwd)
      apps = os.path.join(cwd, '../applications')

      for item in os.listdir(apps):
        path = os.path.join(apps, item)
        if not os.path.isdir(path):
          continue
        metafile = os.path.join(path, 'metafile.json')
        meta.append(load_meta_file(metafile))

    return meta

  def start(self, wait_for_signal=True):
    """
    Start the freepy server
    :param wait_for_signal: Block this thread and wait for interrupt signal?
    :return:
    """
    logging.basicConfig(
      filename = settings.logging.get('filename'),
      format = settings.logging.get('format'),
      level = settings.logging.get('level')
    )
    meta = self.__load_meta__()
    router = self.__create_router__(
      n_threads = settings.concurrency.get('threads').get('pool_size')
    )
    server = self.__create_server__(meta, router)
    server.tell(BootstrapCompleteEvent())
    # Register interrupt signal handler.
    def signal_handler(signal, frame):
      self.__logger__.critical('FreePy is now shutting down!!!')
      server.tell(ShutdownEvent())
    signal.signal(signal.SIGINT, signal_handler)
    if not wait_for_signal:
      return server
    signal.pause()

class Server(Actor):
  def __init__(self, *args, **kwargs):
    super(Server, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('lib.server.Server')
    self.__observers__ = {}
    self.__reactor__ = Thread(target = reactor.run, args = (False,))
    self.__router__ = kwargs.get('router')
    self.__applications__ = ActorRegistry(
      init_msg = ServerInfoEvent(self),
      destroy_msg = ServerDestroyEvent(),
      router = self.__router__
    )
    self.__services__ = ActorRegistry(
      init_msg = ServerInitEvent(self, kwargs.get('meta')),
      destroy_msg = ServerDestroyEvent(),
      router = self.__router__
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
      recipient.tell(message)

  def __register__(self, message):
    self.__applications__.register(
      message.fqn(),
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
    target = message.target()
    if self.__services__.exists(target):
      recipient = self.__services__.get(target)
    elif self.__applications__.exists(target):
      recipient = self.__applications__.get(target)
    if recipient is not None:
      recipient.tell(message.message())

  def __stop__(self):
    self.__applications__.shutdown()
    self.__services__.shutdown()
    self.__router__.stop()
    reactor.stop()

  def __unwatch__(self, message):
    fqn = self.__fqn__(message.message())
    observer = message.observer()
    if self.__observers__.has_key(fqn):
      recipients = self.__observers__.get(fqn)
      for idx in xrange(len(recipients)):
        if observer.urn() == recipients[idx].urn():
          del recipients[idx]

  def __watch__(self, message):
    fqn = self.__fqn__(message.message())
    observer = message.observer()
    if not self.__observers__.has_key(fqn):
      self.__observers__.update({ fqn: [observer] })
    else:
      self.__observers__.get(fqn).append(observer)

  def receive(self, message):
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
    elif isinstance(message, ShutdownEvent):
      self.__stop__()

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
  def __init__(self, observer, message):
    self.__message__ = message
    self.__observer__ = observer

  def message(self):
    return self.__message__

  def observer(self):
    return self.__observer__

class UnwatchMessagesCommand(object):
  def __init__(self, observer, message):
    self.__message__ = message
    self.__observer__ = observer

  def message(self):
    return self.__message__

  def observer(self):
    return self.__observer__

class ShutdownEvent(object):
  def __init__(self, *args, **kwargs):
    super(ShutdownEvent, self).__init__(*args, **kwargs)