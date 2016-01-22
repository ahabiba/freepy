from twisted.internet.defer import succeed
from twisted.internet.protocol import Protocol
from twisted.web.client import ResponseDone, ResponseFailed
from twisted.internet.error import ConnectionDone, ConnectionLost
from twisted.web.http import PotentialDataLoss
from twisted.web.iweb import IBodyProducer
from zope.interface import implements
import wave

class MediaConsumer(Protocol):
  def __init__(self, finished, path, length):
    self.finished = finished
    self.remaining = length
    self.path = path        
    self.file = open(path, 'wb')

  def dataReceived(self, bytes_left):
    if self.remaining:
      self.file.write(bytes_left)
      self.remaining -= len(bytes_left)

  def connectionLost(self, reason):
    self.file.close()    
    #if reason.check(ResponseDone) is not None:
    if ((reason.check(ResponseFailed) and any(exn.check(ConnectionDone, ConnectionLost) for exn in reason.value.reasons)) or reason.check(ResponseDone, PotentialDataLoss)):
      self.finished.callback(None)
    else:
      error = RuntimeError('There was an error downloading %s - %s' % (self.path, reason))
      self.finished.errback(error)

class StringProducer(object):
  implements(IBodyProducer)

  def __init__(self, body):
    self.body = body
    self.length = len(body)

  def startProducing(self, consumer):
    consumer.write(self.body)
    return succeed(None)

  def pauseProducing(self):
    pass

  def stopProducing(self):
    pass


