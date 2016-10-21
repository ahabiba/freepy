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

import json
import logging
import os
import signal

from threading import Thread

from twisted.internet import reactor

import config
from freepy import settings
from freepy.lib.actors.actor import Actor
from freepy.lib.actors.actor_registry import ActorRegistry
from freepy.lib.actors.actor_scheduler import ActorScheduler
from freepy.lib.actors.messages.poison_pill import PoisonPill
from freepy.lib.actors.utils import class_fqn, object_fqn

class Bootstrap(object):
  def __init__(self, *args, **kwargs):
    self._logger = logging.getLogger(object_fqn(self))
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

  def _load_meta(self):
    def load_meta_file(metafile):
      if not os.path.exists(metafile):
        self._logger.warning('The application %s is missing a metafile.' % \
                             item)
        return
      with open(metafile, 'r') as source:
        try:
          return json.loads(source.read())
        except Exception as e:
          self._logger.warning('There was an error reading the metafile ' \
                               'for %s.' % item)
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
    # Start the actor system scheduler.
    scheduler = ActorScheduler(10, 50) # <--- TODO:args should be configurable.
    # Register interrupt signal handler.
    def signal_handler(signal, frame):
      scheduler.shutdown()
      while True:
        if not scheduler.is_running:
          break  
      reactor.stop()
    signal.signal(signal.SIGINT, signal_handler)
    # Start the scheduler thread.
    scheduler_thread = Thread(target=scheduler.start)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    # Start the Twisted reactor thread.
    reactor_thread = Thread(target=reactor.run, args=(False,))
    reactor_thread.daemon = True
    reactor_thread.start()
    # Start the freepy server.
    meta = self._load_meta()
    server = Server(meta, scheduler)
    if not wait_for_signal:
      return server
    signal.pause()

class Server(Actor):
  def __init__(self, meta, scheduler):
    self._logger = logging.getLogger(object_fqn(self))
    self._applications = ActorRegistry(scheduler)
    self._services = ActorRegistry(scheduler)
    self._meta = meta
    self._observers = dict()
    self._scheduler = scheduler
    super(Server, self).__init__(scheduler)

  def _fqn(self, o):
    if type(o) == type:
      return class_fqn(o)
    else:
      return object_fqn(o)

  def _broadcast(self, fqn, message):
    recipients = self._observers.get(fqn)
    for recipient in recipients:
      recipient.tell(message)

  def _register(self, message):
    fqn = message.fqn()
    singleton = message.singleton()
    if fqn is not None:
      if singleton:
        self._applications.register_singleton(fqn, ServerInfoEvent(self))
      else:
        self._applications.register_class(fqn)

  def _unicast(self, message):
    recipient = None
    target = message.target()
    if self._services.has(target):
      recipient = self._services.get_instance(target)
    elif self._applications.has(target):
      recipient = self._applications.get_instance(
        target, ServerInfoEvent(self)
      )
    if recipient is not None:
      recipient.tell(message.message())

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

  def on_start(self):
    services = settings.services
    # Register the services as singleton actors.
    init_event = ServerInitEvent(self, self._meta)
    for service in services:
      target = service.get('target')
      self._services.register_singleton(target)
      self._services.get_instance(target).tell(init_event)
    # Register the messages recognized by each service.
    for service in services:
      messages = service.get('messages')
      if messages and len(messages) > 0:
        observer = self._services.get_instance(service.get('target'))
        for message in messages:
          if not self._observers.has_key(message):
            self._observers.update({message: [observer]})
          else:
            self._observers.get(message).append(observer)

  def on_stop(self):
    self._logger.critical("FreePy is now shutting down!!!")

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

class RegisterActorCommand(object):
  def __init__(self, fqn, singleton=False):
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
