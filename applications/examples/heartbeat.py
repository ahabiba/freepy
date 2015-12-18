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

from lib.core import *
from lib.esl import Event

import logging

class Monitor(Switchlet):
  def __init__(self, *args, **kwargs):
    super(Monitor, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('examples.heartbeat.monitor')

  def __print__(self, message):
    output = 'Got a heartbeat @ %s ' % \
             message.get_header('FreeSWITCH-IPv4')
    output += 'Sessions: %s ' % message.get_header('Session-Count')
    output += 'Max Sessions: %s ' % message.get_header('Max-Sessions')
    output += 'CPU Usage: %.2f' % (100 - float(message.get_header('Idle-CPU')))
    self.__logger__.info(output)

  def __update__(self, message):
    self.__dispatcher__ = message.get_dispatcher()

  def on_receive(self, message):
    message = message.get('body')
    if isinstance(message, InitializeSwitchletEvent):
      self.__update__(message)
    if isinstance(message, Event):
      self.__print__(message)
