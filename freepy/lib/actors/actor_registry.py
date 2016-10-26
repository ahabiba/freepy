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

import logging

import class_loader

from freepy import settings

from freepy.lib.actors.actor import Actor
from freepy.lib.actors.errors import CLASS_REGISTRATION_CONFLICT, \
                                     INSTANCE_REGISTRATION_CONFLICT, \
                                     INVALID_ACTOR_CLASS
from freepy.lib.actors.utils import class_fqn, object_fqn

class ActorRegistry(object):
  def __init__(self, scheduler):
    super(ActorRegistry, self).__init__()
    self._logger = logging.getLogger(object_fqn(self))
    self._classes = dict()
    self._singletons = dict()
    self._scheduler = scheduler

  def _load_actor(self, klass):
    fqn = class_fqn(klass)
    if not issubclass(klass, Actor):
      raise ValueError(INVALID_ACTOR_CLASS % (fqn))
    self._logger.info("Starting actor %s" % fqn)
    actor = klass(self._scheduler)
    self._logger.info("Started actor %s" % fqn)
    return actor

  def _load_class(self, fqn):
    if 'freepy' not in fqn and len(settings.application_prefix):
      fqn = '{}.{}'.format(settings.application_prefix, fqn)
    return class_loader.safe_import(fqn, force_load=True)

  def get_instance(self, fqn, init_message=None):
    if self.has_class(fqn):
      actor = self._load_actor(self._classes.get(fqn))
      if init_message is not None:
        actor.tell(init_message)
      return actor
    elif self.has_instance(fqn):
      return self._singletons.get(fqn)

  def has(self, fqn):
    return self.has_class(fqn) or self.has_instance(fqn)

  def has_class(self, fqn):
    return self._classes.has_key(fqn)

  def has_instance(self, fqn):
    return self._singletons.has_key(fqn)

  def register_class(self, fqn):
    if self.has_instance(fqn):
      raise ValueError(CLASS_REGISTRATION_CONFLICT % (fqn))
    if self.has_class(fqn):
      del self._classes[fqn]
    self._classes.update({fqn: self._load_class(fqn)})

  def register_singleton(self, fqn, init_message=None):
    if self.has_class(fqn):
      raise ValueError(INSTANCE_REGISTRATION_CONFLICT % (fqn))
    if self.has_instance(fqn):
      del self._singletons[fqn]
    actor = self._load_actor(self._load_class(fqn))
    if init_message is not None:
      actor.tell(init_message)
    self._singletons.update({fqn: actor})
