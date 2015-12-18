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

from lib.esl import Event
from lib.switchlet import *
from twisted.web.server import Request

import logging

class Monitor(Switchlet):
  def __init__(self, *args, **kwargs):
    super(Monitor, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('examples.heartbeat.monitor')
    self.__output__ = 'Waiting for heartbeat'

  def __http__(self, message):
    message.setResponseCode(200)
    message.write(self.__output__ + '\n')
    message.finish()

  def __print__(self, message):
    output = 'Got a heartbeat @ %s ' % \
             message.get_header('FreeSWITCH-IPv4')
    output += 'Sessions: %s ' % message.get_header('Session-Count')
    output += 'Max Sessions: %s ' % message.get_header('Max-Sessions')
    output += 'CPU Usage: %.2f' % (100 - float(message.get_header('Idle-CPU')))
    self.__logger__.info(output)
    self.__output__ = output

  def __update__(self, message):
    self.__dispatcher__ = message.get_dispatcher()
    command = RegisterUrlObserverCommand(self.actor_ref, '/heartbeat')
    self.__dispatcher__.tell({ 'body': command })

  def on_receive(self, message):
    message = message.get('body')
    if isinstance(message, InitializeSwitchletEvent):
      self.__update__(message)
    elif isinstance(message, Event):
      self.__print__(message)
    elif isinstance(message, Request):
      self.__http__(message)
