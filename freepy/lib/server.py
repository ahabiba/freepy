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
import config
import sys

from freepy import settings

class Bootstrap(object):
  def __init__(self, *args, **kwargs):
    self._logger = logging.getLogger('lib.server.Bootstrap')
    if 'settings' in kwargs:
      settings.update(kwargs.get('settings'))
    else:
      settings.update(__import__('config'))
      settings.update({'application_prefix': 'applications'})
    self._metafile = kwargs.get('metafile', None)

  def _configure_logging(self):
    if getattr(config, 'logging_configured', False):
      return

    logging.basicConfig(
      filename=settings.logging.get('filename'),
      format=settings.logging.get('format'),
      level=settings.logging.get('level')
    )

  def _create_router(self, n_threads):
    router = MessageRouter(n_threads = n_threads)
    router.start()
    return router

  def _create_server(self, meta, router):
    return Server(meta = meta, router = router)

  def _load_meta(self):
    def load_meta_file(metafile):
      if not os.path.exists(metafile):
        self._logger.warning('The application %s is missing a metafile.' % \
                             item)
        return
      with open(metafile, 'r') as input:
        try:
          return json.loads(input.read())
        except Exception as e:
          self._logger.warning('There was an error reading the ' + \
                                  'metafile for %s.' % item)
          self._logger.exception(e)
          return

    meta = []

    if self._metafile:
      metafile = os.path.join('.', self._metafile)
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
    self._configure_logging()
    meta = self._load_meta()
    router = self._create_router(
      n_threads = settings.concurrency.get('threads').get('pool_size')
    )
    server = self._create_server(meta, router)
    server.tell(BootstrapCompleteEvent())
    # Register interrupt signal handler.
    def signal_handler(signal, frame):
      self._logger.critical('FreePy is now shutting down!!!')
      server.tell(ShutdownEvent())
    signal.signal(signal.SIGINT, signal_handler)
    if not wait_for_signal:
      return server
    signal.pause()

class Server(Actor):
  def __init__(self, *args, **kwargs):
    super(Server, self).__init__(*args, **kwargs)
    self._logger = logging.getLogger('lib.server.Server')
    self._observers = {}
    self._reactor = Thread(target = reactor.run, args = (False,))
    self._router = kwargs.get('router')
    self._applications = ActorRegistry(
      init_msg = ServerInfoEvent(self),
      destroy_msg = ServerDestroyEvent(),
      router = self._router
    )
    self._services = ActorRegistry(
      init_msg = ServerInitEvent(self, kwargs.get('meta')),
      destroy_msg = ServerDestroyEvent(),
      router = self._router
    )

  def _fqn(self, obj):
    if type(obj) == type:
      module = obj.__module__
      klass = obj.__name__
    else:
      module = obj.__class__.__module__
      klass = obj.__class__.__name__
    return '%s.%s' % (module, klass)

  def _broadcast(self, fqn, message):
    recipients = self._observers.get(fqn)
    for recipient in recipients:
      recipient.tell(message)

  def _register(self, message):
    self._applications.register(
      message.fqn(),
      message.singleton()
    )

  def _start_services(self):
    for service in settings.services:
      try:
        target = service.get('target')
        self._services.register(target, singleton = True)
        messages = service.get('messages')
        if messages is not None and len(messages) > 0:
          observer = self._services.get(target)
          for message in messages:
            if not self._observers.has_key(message):
              self._observers.update({message: [observer]})
            else:
              self._observers.get(message).append(observer)
        if service.has_key('name'):
          self._logger.info('Loaded %s' % service.get('name'))
      except Exception as e:
        name = service.get('name')
        if name is not None:
          self._logger.error('There was an error loading %s' % name)
        self._logger.exception(e)
    self._reactor.start()

  def _unicast(self, message):
    recipient = None
    target = message.target()
    if self._services.exists(target):
      recipient = self._services.get(target)
    elif self._applications.exists(target):
      recipient = self._applications.get(target)
    if recipient is not None:
      recipient.tell(message.message())

  def _stop(self):
    self._applications.shutdown()
    self._services.shutdown()
    self._router.stop()
    reactor.stop()

  def _unwatch(self, message):
    fqn = self._fqn(message.message())
    observer = message.observer()
    if self._observers.has_key(fqn):
      recipients = self._observers.get(fqn)
      for idx in xrange(len(recipients)):
        if observer.urn() == recipients[idx].urn():
          del recipients[idx]

  def _watch(self, message):
    fqn = self._fqn(message.message())
    observer = message.observer()
    if not self._observers.has_key(fqn):
      self._observers.update({fqn: [observer]})
    else:
      self._observers.get(fqn).append(observer)

  def receive(self, message):
    fqn = self._fqn(message)
    if isinstance(message, RouteMessageCommand):
      self._unicast(message)
    elif self._observers.has_key(fqn):
      self._broadcast(fqn, message)
    elif isinstance(message, WatchMessagesCommand):
      self._watch(message)
    elif isinstance(message, UnwatchMessagesCommand):
      self._unwatch(message)
    elif isinstance(message, RegisterActorCommand):
      self._register(message)
    elif isinstance(message, BootstrapCompleteEvent):
      self._start_services()
    elif isinstance(message, ShutdownEvent):
      self._stop()

  @property
  def router(self):
    return self._router

class BootstrapCompleteEvent(object):
  def __init__(self, *args, **kwargs):
    super(BootstrapCompleteEvent, self).__init__(*args, **kwargs)

class RegisterActorCommand(object):
  def __init__(self, fqn, singleton = False):
    self._fqn = fqn
    self._singleton = singleton

  def fqn(self):
    return self._fqn

  def singleton(self):
    return self._singleton

class RouteMessageCommand(object):
  def __init__(self, message, target):
    self._message = message
    self._target = target

  def message(self):
    return self._message

  def target(self):
    return self._target

class ServerInfoEvent(object):
  def __init__(self, server):
    self._server = server

  def server(self):
    return self._server

class ServerInitEvent(object):
  def __init__(self, server, meta):
    self._server = server
    self._meta = meta

  def meta(self):
    return self._meta

  def server(self):
    return self._server

class ServerDestroyEvent(object):
  def __init__(self, *args, **kwargs):
    super(ServerDestroyEvent, self).__init__(*args, **kwargs)

class WatchMessagesCommand(object):
  def __init__(self, observer, message):
    self._message = message
    self._observer = observer

  def message(self):
    return self._message

  def observer(self):
    return self._observer

class UnwatchMessagesCommand(object):
  def __init__(self, observer, message):
    self._message = message
    self._observer = observer

  def message(self):
    return self._message

  def observer(self):
    return self._observer

class ShutdownEvent(object):
  def __init__(self, *args, **kwargs):
    super(ShutdownEvent, self).__init__(*args, **kwargs)