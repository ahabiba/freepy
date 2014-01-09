from lib.commands import *
from lib.events import *
from lib.fsm import *
from lib.server import *
from pykka import ThreadingActor

import logging
import urllib

# Used ONLY by monitor to transition itself into the 'expecting heartbeat' state
# once it has had a chance to initialize.
class StartMonitorCommand(object):
  pass

class Monitor(FiniteStateMachine, ThreadingActor):
  initial_state = 'not ready'

  transitions = [
    ('not ready', 'ready'),
    ('ready', 'expecting heartbeat'),
    ('expecting heartbeat', 'expecting status response'),
    ('expecting status response', 'expecting status event'),
    ('expecting status event', 'processing status event'),
    ('processing status event', 'expecting heartbeat')
  ]

  def __init__(self, *args, **kwargs):
    super(Monitor, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('heartbeat.monitor')
    self.__dispatcher__ = None

  @Action(state = 'ready')
  def initialize(self, message):
    self.__dispatcher__ = message.get_dispatcher()
    command = StartMonitorCommand()
    self.actor_ref.tell({'content': command})

  @Action(state = 'expecting status response')
  def handle_heartbeat(self, message):
    # Ask FreeSWITCH for a status.
    status_command = StatusCommand(self.actor_ref)
    # Always register to receive events for specific Job-UUIDs first.
    uuid = status_command.get_job_uuid()
    register_command = RegisterJobObserverEvent(self.actor_ref, uuid)
    self.__dispatcher__.tell({'content': register_command})
    self.__logger__.info('Registered to receive events with Job-UUID: %s' % uuid)
    # Send the status command.
    self.__dispatcher__.tell({'content': status_command})

  @Action(state = 'processing status event')
  def handle_status_event(self, message):
    self.__logger__.info(message.get_body())
    uuid = message.get_header('Job-UUID')
    command = UnregisterJobObserverEvent(uuid)
    self.__dispatcher__.tell({'content': command})
    self.__logger__.info('Unregistered to receive events with Job-UUID: %s' % uuid)
    command = StartMonitorCommand()
    self.actor_ref.tell({'content': command})

  def on_receive(self, message):
    # Necessary because all pykka messages must be dicts.
    message = message.get('content')
    if isinstance(message, InitializeSwitchletEvent):
      self.transition(to = 'ready', event = message)
    if isinstance(message, StartMonitorCommand):
      self.transition(to = 'expecting heartbeat')
    elif isinstance(message, Event):
      content_type = message.get_header('Content-Type')
      if content_type == 'command/reply':
        self.transition(to = 'expecting status event', event = message)
      elif content_type == 'text/event-plain':
        name = message.get_header('Event-Name')
        if name == 'HEARTBEAT':
          self.transition(to = 'expecting status response', event = message)
        elif name == 'BACKGROUND_JOB':
          self.transition(to = 'processing status event', event = message)
