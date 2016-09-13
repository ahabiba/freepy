from freepy.lib.application import Actor
from freepy.services.smtp import SmtpReceiveEvent

import logging
import time

class HelloSmtpWorld(Actor):
  def __init__(self, *args, **kwargs):
    super(HelloSmtpWorld, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('services.smtp.SmtpDispatcher')

  def receive(self, message):
    if isinstance(message, SmtpReceiveEvent):
      event = message
      self.__logger__.debug(message.received())
      self.__logger__.debug(message.headers())
      self.__logger__.debug(message.body())
