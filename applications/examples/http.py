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

from freepy.lib.actors.actor import Actor
from freepy.services.http import HttpRequestEvent

class HelloWorld(Actor):
  def __init__(self, *args, **kwargs):
    super(HelloWorld, self).__init__(*args, **kwargs)

  def receive(self, message):
    if isinstance(message, HttpRequestEvent):
      request = message.request()
      if request.method == 'GET':
        request.setResponseCode(200)
        request.write('Hello World!')
        request.finish()
        self.stop()
