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

from uuid import uuid4

from actor_processor import ActorProcessor
from messages.poison_pill import PoisonPill

class Actor(object):
  '''
  An actor is the most basic unit of computation in an actor framework.
  '''

  def __init__(self, scheduler, *args, **kwargs):
    super(Actor, self).__init__()
    self._mailbox = list()
    self._scheduler = scheduler
    self._urn = uuid4()
    # Schedule ourself for execution.
    proc = ActorProcessor(self, self._mailbox, self._scheduler, self._urn)
    proc.start()

  @property
  def scheduler(self):
    return self._scheduler

  @property
  def urn(self):
    return self._urn


  def receive(self, message):
    '''
    This method processes incoming messages.
    '''

    raise NotImplementedError()

  def stop(self):
    self.tell(PoisonPill())

  def tell(self, message):
    self._mailbox.append(message)
