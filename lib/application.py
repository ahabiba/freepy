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
from threading import Thread

import logging
import sys

class ActorRegistry(object):
  def __init__(self, *args, **kwargs):
    super(ActorRegistry, self).__init__()
    self.logger = logging.getLogger('lib.application.ActorRegistry')
    self.classes = dict()
    self.message = kwargs.get('message')
    self.objects = dict()
    self.router = MessageRouter()
    self.router.start()

  def exists(self, fqdn):
    return self.classes.has_key(fqdn) or self.objects.has_key(fqdn)

  def get(self, fqdn):
    actor = None
    if self.classes.has_key(fqdn):
      klass = self.classes.get(fqdn)
      actor = klass(router = self.router)
      if self.logger.isEnabledFor(logging.DEBUG):
        self.logger.warning('Started %s' % fqdn)
      if not self.message == None:
        try:
          actor.tell(self.message)
        except Exception as e:
          self.logger.exception(e)
    elif self.objects.has_key(fqdn):
      actor = self.objects.get(fqdn)
    return actor

  def klass(self, fqdn):
    delimiter = fqdn.rfind('.')
    root = fqdn[:delimiter]
    name = fqdn[delimiter + 1:]
    module = sys.modules.get(root)
    try:
      if not module == None:
        module = reload(module)
      else:
        module = __import__(root, globals(), locals(), [name], -1)
    except Exception as e:
      self.logger.exception(e)
    return getattr(module, name)

  def register(self, fqdn, singleton = False):
    if self.classes.has_key(fqdn):
      del self.classes[fqdn]
    elif self.objects.has_key(fqdn):
      del self.objects[fqdn]
    klass = self.klass(fqdn)
    if not singleton:
      self.classes.update({fqdn: klass})
    else:
      actor = klass(router = self.router)
      if self.logger.isEnabledFor(logging.DEBUG):
        self.logger.warning('Started %s' % fqdn)
      self.objects.update({fqdn: actor})
      if not self.message == None:
        try:
          actor.tell(self.message)
        except Exception as e:
          self.logger.exception(e)

  def shutdown(self):
    self.router.stop()

class Actor(object):
  def __init__(self, *args, **kwargs):
    super(Actor, self).__init__()
    self.router = kwargs.get('router')

  def receive(self, message):
    pass

  def tell(self, message):
    self.router.send((self, message))

class MessageRouter(object):
  def __init__(self, *args, **kwargs):
    super(MessageRouter, self).__init__()
    self.logger = logging.getLogger('lib.application.MessageRouter')
    self.queue = Queue()

  def send(self, message):
    self.queue.put(message)

  def start(self):
    self.worker = MessageRouterWorker(self.queue)
    self.worker.start()

  def stop(self):
    self.queue.put((None, None))
    self.worker = None

class MessageRouterWorker(Thread):
  def __init__(self, *args, **kwargs):
    super(MessageRouterWorker, self).__init__()
    self.logger = logging.getLogger('lib.application.MessageRouterWorker')
    self.queue = args[0]

  def run(self):
    while True:
      recipient, message = self.queue.get(True)
      if recipient == None and message == None:
        break
      try:
        recipient.receive(message)
      except Exception as e:
        if self.logger.isEnabledFor(logging.DEBUG):
          self.logger.exception(e)
