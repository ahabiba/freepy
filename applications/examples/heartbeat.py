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

from lib.server import ServerInfoEvent
from pykka import ThreadingActor
from services.http import HttpRequestEvent
from services.freeswitch import EventSocketEvent

import json
import logging

class Monitor(ThreadingActor):
  def __init__(self, *args, **kwargs):
    super(Monitor, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('examples.heartbeat.Monitor')
    self.__info__ = []

  def on_receive(self, message):
    message = message.get('body')
    if isinstance(message, EventSocketEvent):
      self.__info__ = [message.headers()]
    elif isinstance(message, HttpRequestEvent):
      request = message.request()
      if request.method == 'GET':
        request.setResponseCode(200)
        request.write(json.dumps(self.__info__,
                                 indent = 2,
                                 sort_keys = True))
        request.finish()
