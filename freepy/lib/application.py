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
    self.__router__ = kwargs.get('router')
    self.__uuid__ = uuid4().get_urn()
    lock = Lock()
    self.lock = lock.acquire
    self.unlock = lock.release

  def receive(self, message):
    pass

  def tell(self, message):
    self.__router__.send((self, message))

  def uuid(self):
    return self.__uuid__

class ActorRegistry(object):
  def __init__(self, *args, **kwargs):
    super(ActorRegistry, self).__init__()
    self.__logger__ = logging.getLogger('lib.application.ActorRegistry')
    self.__classes__ = dict()
    self.__message__ = kwargs.get('message')
    self.__objects__ = dict()
    self.__router__ = kwargs.get('router')

  def exists(self, fqn):
    return self.__classes__.has_key(fqn) or self.__objects__.has_key(fqn)

  def get(self, fqn):
    actor = None
    if self.__classes__.has_key(fqn):
      klass = self.__classes__.get(fqn)
      actor = klass(router = self.__router__)
      if self.__logger__.isEnabledFor(logging.DEBUG):
        self.__logger__.info('Started %s' % fqn)
      if not self.__message__ == None:
        try:
          actor.tell(self.__message__)
        except Exception as e:
          self.__logger__.exception(e)
    elif self.__objects__.has_key(fqn):
      actor = self.__objects__.get(fqn)
    return actor

  def klass(self, fqn):
    if 'freepy' not in fqn:
      fqn = '%s.%s' % (settings.application_prefix, fqn)
    delimiter = fqn.rfind('.')
    root = fqn[:delimiter]
    name = fqn[delimiter + 1:]
    module = sys.modules.get(root)
    try:
      if not module == None:
        module = reload(module)
      else:
        module = __import__(root, globals(), locals(), [name], -1)
    except Exception as e:
      self.__logger__.exception(e)
    return getattr(module, name)


  def register(self, fqn, singleton = False):
    if self.__classes__.has_key(fqn):
      del self.__classes__[fqn]
    elif self.__objects__.has_key(fqn):
      del self.__objects__[fqn]
    klass = self.klass(fqn)
    if not singleton:
      self.__classes__.update({fqn: klass})
    else:
      actor = klass(router = self.__router__)
      if self.__logger__.isEnabledFor(logging.DEBUG):
        self.__logger__.info('Started %s' % fqn)
      self.__objects__.update({fqn: actor})
      if not self.__message__ == None:
        try:
          actor.tell(self.__message__)
        except Exception as e:
          self.__logger__.exception(e)

  def shutdown(self):
    self.__router__.stop()

class MessageRouter(object):
  def __init__(self, *args, **kwargs):
    super(MessageRouter, self).__init__()
    self.__logger__ = logging.getLogger('lib.application.MessageRouter')
    self.__queue__ = Queue()

  def send(self, message):
    self.__queue__.put(message)

  def start(self, n_threads = None):
    if n_threads == None:
      n_threads = multiprocessing.cpu_count()
    self.pool = []
    for _ in xrange(n_threads):
      worker = MessageRouterWorker(self.__logger__, self.__queue__)
      worker.start()
      self.pool.append(worker)

  def stop(self):
    for _ in xrange(len(self.pool)):
      self.__queue__.put((None, None))
    self.worker = None

class MessageRouterWorker(Thread):
  def __init__(self, *args, **kwargs):
    super(MessageRouterWorker, self).__init__()
    self.__logger__ = args[0]
    self.__queue__ = args[1]

  def run(self):
    while True:
      recipient, message = self.__queue__.get(True)
      if recipient == None and message == None:
        break
      try:
        recipient.lock()
        recipient.receive(message)
        recipient.unlock()
      except Exception as e:
        if self.__logger__.isEnabledFor(logging.DEBUG):
          self.__logger__.exception(e)
