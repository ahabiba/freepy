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

from pykka import ThreadingActor

class InitializeSwitchletEvent(object):
  def __init__(self, dispatcher):
    self.__dispatcher__ = dispatcher

  def get_dispatcher(self):
    return self.__dispatcher__

class KillSwitchletEvent(object):
  pass

class RegisterJobObserverCommand(object):
  def __init__(self, observer, uuid):
    self.__observer__ = observer
    self.__job_uuid__ = uuid

  def get_job_uuid(self):
    return self.__job_uuid__

  def get_observer(self):
    return self.__observer__

class Switchlet(ThreadingActor):
  def __init__(self, *args, **kwargs):
    super(Switchlet, self).__init__(*args, **kwargs)

class UnregisterJobObserverCommand(object):
  def __init__(self, uuid):
    self.__job_uuid__ = uuid

  def get_job_uuid(self):
    return self.__job_uuid__