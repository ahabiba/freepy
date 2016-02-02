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
from lib.server import RegisterActorCommand, RouteMessageCommand, \
                       ServerDestroyEvent, ServerInitEvent
from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Request, Site

import logging
import re
import settings

class HttpDispatcher(ThreadingActor):
  def __init__(self, *args, **kwargs):
    super(HttpDispatcher, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('services.http.HttpDispatcher')

  def __dispatch__(self, message):
    for rule in self.__rules__:
      target = rule.get('target')
      urls = rule.get('urls')
      for url in urls:
        result = re.match(url, message.path)
        if result is not None:
          event = HttpRequestEvent(result.groups(),
                                   result.groupdict(),
                                   message)
          self.__server__.tell({
            'body': RouteMessageCommand(event, target)
          })
          return
    self.__dispatch_not_found__(message)

  def __dispatch_not_found__(self, message):
    message.setResponseCode(404)
    if settings.http.has_key('pages'):
      if settings.http.get('pages').has_key('404'):
        page = settings.http.get('pages').get('404')
        with open(page, 'r') as error:
          message.write(error.read())
      else:
        message.write('Not Found')
    else:
      message.write('Not Found')
    message.finish()

  def __initialize__(self, message):
    self.__server__ = message.server()
    self.__rules__ = []
    for item in message.meta():
      if item.has_key('http'):
        http = item.get('http')
        rules = http.get('rules')
        if rules is not None and len(rules) > 0:
          try:
            for rule in rules:
              urls = rule.get('urls')
              if urls is not None and len(urls) > 0:
                self.__rules__.append(rule)
                singleton = rule.get('singleton')
                target = rule.get('target')
                self.__server__.tell({
                  'body': RegisterActorCommand(target, singleton)
                })
                self.__logger__.info('Registered %s' % target)
          except Exception as e:
            name = item.get('name')
            if name is not None:
              self.__logger__.error('There was an error loading %s' % name)
            self.__logger__.exception(e)
    self.__start__()

  def __start__(self):
    proxy = HttpProxy(self.actor_ref)
    reactor.listenTCP(
      settings.http.get('port'),
      Site(proxy)
    )

  def on_receive(self, message):
    message = message.get('body')
    if isinstance(message, Request):
      self.__dispatch__(message)
    elif isinstance(message, ServerInitEvent):
      self.__initialize__(message)

class HttpProxy(Resource):
  isLeaf = True

  def __init__(self, dispatcher):
    self.__logger__ = logging.getLogger('services.http.HttpDispatcher')
    self.__dispatcher__ = dispatcher

  def render(self, request):
    if self.__logger__.isEnabledFor(logging.DEBUG):
      message = 'Incoming HTTP Request\n'
      message += 'uri: %s%s\n' % (request.uri, request.path)
      message += 'method: %s\n' % request.method
      if len(request.args) > 0:
        message += 'args:\n'
        for key, value in request.args.iteritems():
          message += '  %s: %s\n' % (key, value)
      message += 'headers:\n'
      for header in request.requestHeaders.getAllRawHeaders():
        message += '  %s: %s\n' % (header[0], header[1])
      message += '\n'
      self.__logger__.debug(message)
    self.__dispatcher__.tell({ 'body': request })
    return NOT_DONE_YET

class HttpRequestEvent(object):
  def __init__(self, params, params_dict, request):
    self.__params__ = params
    self.__params_dict__ = params_dict
    self.__request__ = request

  def params(self):
    return self.__params__

  def params_dict(self):
    return self.__params_dict__

  def request(self):
    return self.__request__