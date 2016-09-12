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

from freepy.lib.application import Actor
from freepy.lib.server import RegisterActorCommand, RouteMessageCommand, \
                       ServerDestroyEvent, ServerInitEvent
from twisted.internet import protocol, reactor, defer
from twisted.web.resource import Resource
from twisted.web.server import Request, Site

from twisted.mail import smtp
from zope.interface import implements
import os
from email.Header import Header

import logging
from freepy import settings


class SmtpDispatcher(Actor):
  empty_qs = dict()

  def __init__(self, *args, **kwargs):
    super(SmtpDispatcher, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('services.smtp.SmtpDispatcher')

  def _dispatch(self, message):
    event = message
    self.__server__.tell(RouteMessageCommand(event, target))
    return

  def _initialize(self, message):
    # something needs to happen here, but I don't know what.
    # will figure it out later

    #self.__server__ = message.server()
    self._start()

  def _start(self):
    reactor.listenTCP(settings.smtp.get('port'), SmtpFactory())

  def receive(self, message):
    if isinstance(message, SmtpReceiveEvent):
      self._dispatch(message)
    elif isinstance(message, ServerInitEvent):
      self._initialize(message)

class SmtpMessage(object):
  implements(smtp.IMessage)

  def __init__(self, event):
    self._event = event
    self.lines = []

  def lineReceived(self, line):
    self.lines.append(line)

  def eomReceived(self):
    self.lines.append('') # add a trailing newline
    messageData = '\n'.join(self.lines)
    self._event.set_content(messageData)
    return defer.succeed(None)

  def connectionLost(self):
    del(self.lines)

class SmtpMessageDelivery(object):
  implements(smtp.IMessageDelivery)

  def __init__(self, event):
    self._event = event

  def receivedHeader(self, helo, origin, recipients):
    myHostname, clientIP = helo
    headerValue = "by {} from {} with SMTP ; {}".format(myHostname, clientIP, smtp.rfc822date( ))
    return "Received: {}".format(Header(headerValue))

  def validateTo(self, user):
    # whitelist here. if not on whitelist,
    # raise smtp.SMTPBadRcpt(user)
    return lambda: SmtpMessage(self._event)

  def validateFrom(self, helo, originAddress):
    # whitelist here. if not on whitelist,
    # raise smtp.SMTPBadSender
    return originAddress

class SmtpFactory(protocol.ServerFactory):
  def __init__(self, dispatcher):
    self.__logger__ = logging.getLogger('services.smtp.SmtpDispatcher')
    self.__dispatcher__ = dispatcher

  def buildProtocol(self, addr):
    event = SmtpReceiveEvent()
    delivery = SmtpMessageDelivery(event)
    smtpProtocol = smtp.SMTP(delivery)
    smtpProtocol.factory = self
    self.__dispatcher__.tell(event)

    return smtpProtocol

class SmtpReceiveEvent(object):
  def __init__(self):
    self._content = None
    self._ready = False

  def register_callback():
    # idea: if not ready,
    # register a callback to be called with content on ready
    pass

  def set_content(content):
    self._content = content
    self.set_ready()

  def get_content():
    return self._content

  def set_ready():
    self._ready = True

  def get_ready():
    return self._ready
