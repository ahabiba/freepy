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

class UnwatchEventCommand(object):
  def __init__(self, *args, **kwargs):
    self.__name__ = kwargs.get('name', None)
    self.__pattern__ = kwargs.get('pattern', None)
    self.__value__ = kwargs.get('value', None)
    if not self.__name__ or self.__pattern__ and self.__value__:
      raise ValueError('Please specify a name and a pattern or a value but not both.')

  def get_name(self):
    return self.__name__

  def get_pattern(self):
    return self.__pattern__

  def get_value(self):
    return self.__value__

class WatchEventCommand(UnwatchEventCommand):
  def __init__(self, *args, **kwargs):
    super(WatchEventCommand, self).__init__(*args, **kwargs)
    self.__observer__ = args[0]

  def get_observer(self):
    return self.__observer__