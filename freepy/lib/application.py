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


from Queue import Queue
from threading import Lock, Thread
from uuid import uuid4

import multiprocessing
import logging
import sys

from freepy import settings

class Actor(object):
  def __init__(self, *args, **kwargs):
    super(Actor, self).__init__()
    self._router = kwargs.get('router')
    self.__urn__ = uuid4().get_urn()
    lock = Lock()
    self.lock = lock.acquire
    self.unlock = lock.release

  def receive(self, message):
    pass

  def tell(self, message):
    self._router.send((self, message))

  def urn(self):
    return self.__urn__

class ActorRegistry(object):
  def __init__(self, init_msg=None, destroy_msg=None, router=None, **kwargs):
    super(ActorRegistry, self).__init__()
    self._logger = logging.getLogger('lib.application.ActorRegistry')
    self._actors = dict()
    self._classes = dict()
    self._destroy_msg = destroy_msg
    self._init_msg = init_msg
    self._router = router

  def exists(self, fqn):
    return self._classes.has_key(fqn) or self._actors.has_key(fqn)

  def get(self, fqn):
    actor = None
    if self._classes.has_key(fqn):
      klass = self._classes.get(fqn)
      try:
        actor = klass(router = self._router)
        if self._logger.isEnabledFor(logging.DEBUG):
          self._logger.info('Started %s' % fqn)
        if not self._init_msg == None:
          actor.tell(self._init_msg)
      except Exception as e:
        self._logger.exception(e)
    elif self._actors.has_key(fqn):
      actor = self._actors.get(fqn)
    return actor

  def klass(self, fqn):
    if 'freepy' not in fqn and len(settings.application_prefix):
      fqn = '%s.%s' % (settings.application_prefix, fqn)
    delimiter = fqn.rfind('.')
    root = fqn[:delimiter]
    name = fqn[delimiter + 1:]
    module = sys.modules.get(root)
    try:
      if module == None:
        module = __import__(root, globals(), locals(), [name], -1)
    except Exception as e:
      self._logger.exception(e)
    return getattr(module, name)


  def register(self, fqn, singleton = False):
    if self._classes.has_key(fqn):
      del self._classes[fqn]
    elif self._actors.has_key(fqn):
      del self._actors[fqn]
    klass = self.klass(fqn)
    if not singleton:
      self._classes.update({fqn: klass})
    else:
      try:
        actor = klass(router = self._router)
        if self._logger.isEnabledFor(logging.DEBUG):
          self._logger.info('Started %s' % fqn)
        self._actors.update({fqn: actor})
        if not self._init_msg == None:
          try:
            actor.tell(self._init_msg)
          except Exception as e:
            self._logger.exception(e)
      except Exception as e:
        self._logger.exception(e)

  def shutdown(self):
    for actor in self._actors.values():
      actor.tell(self._destroy_msg)

class MessageRouter(object):
  def __init__(self, *args, **kwargs):
    super(MessageRouter, self).__init__()
    self._logger = logging.getLogger('lib.application.MessageRouter')
    self._queue = Queue()

  def send(self, message):
    self._queue.put(message)

  def start(self, n_threads = None):
    if n_threads == None:
      n_threads = multiprocessing.cpu_count()
    self.pool = []
    for _ in xrange(n_threads):
      worker = MessageRouterWorker(self._logger, self._queue)
      worker.start()
      self.pool.append(worker)

  def stop(self):
    for _ in xrange(len(self.pool)):
      self._queue.put((None, None))
    self.worker = None

class MessageRouterWorker(Thread):
  def __init__(self, *args, **kwargs):
    super(MessageRouterWorker, self).__init__()
    self._logger = args[0]
    self._queue = args[1]

  def run(self):
    while True:
      recipient, message = self._queue.get(True)
      if recipient == None and message == None:
        break
      recipient.lock()
      try:
        recipient.receive(message)
      except Exception as e:
        if self._logger.isEnabledFor(logging.DEBUG):
          self._logger.exception(e)
      finally:
        recipient.unlock()
