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

# Cristian Groza <frontc18@gmail.com>

from uuid import uuid4

# Import the proper StringIO implementation.
try:
  from cStringIO import StringIO
except:
  from StringIO import StringIO


class EventSocketCommand(object):
  def __init__(self, sender):
    self._sender = sender

  def sender(self):
    return self._sender


class BackgroundCommand(EventSocketCommand):
  def __init__(self, sender):
    super(BackgroundCommand, self).__init__(sender)
    self._job_uuid = uuid4().get_urn().split(':', 2)[2]

  def job_uuid(self):
    return self._job_uuid

class UUIDCommand(BackgroundCommand):
  def __init__(self, sender, uuid, **kwargs):
    super(UUIDCommand, self).__init__(sender)
    self._uuid = uuid
    if not self._uuid:
      raise ValueError('The value of uuid must be a valid UUID.')

  def uuid(self):
    return self._uuid

class AuthCommand(EventSocketCommand):
  def __init__(self, sender, password):
    super(AuthCommand, self).__init__(sender)
    self.__password__ = password

  def __str__(self):
    return 'auth %s\n\n' % (self.__password__)

class ACLCheckCommand(BackgroundCommand):
  '''
  The ACLCheckCommand compares an ip to an ACL list.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             ip - Internet Protocol address.
             list_name - ACL list name.
  '''
  def __init__(self, sender, **kwargs):
    super(ACLCheckCommand, self).__init__(sender)
    self._ip = kwargs.get('ip')
    self._list_name = kwargs.get('list_name')
    
    if not self._ip :
      raise ValueError('The ip value %s is invalid' % self._ip)
    if not self._list_name :
      raise ValueError('The list name value %s is invalid' % self._list_name)
    
  def ip(self):
    return self._ip

  def list_name(self):
    return self._list_name

  def __str__(self):
    return 'bgapi acl %s %s\nJob-UUID: %s\n\n' % (
      self._ip, self._list_name, self._job_uuid)

class AnswerCommand(UUIDCommand):
  '''
  The AnswerCommand answers a channel.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(AnswerCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_answer %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class BreakCommand(UUIDCommand):
  '''
  Break out of media being sent to a channel. For example, if an audio file is being played to a channel, 
  issuing uuid_break will discontinue the media and the call will move on in the dialplan, script, 
  or whatever is controlling the call.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              stop_all - boolean flag.*

  *If the stop_all flag is used then all audio files/prompts/etc. that are queued up to be played to the channel 
  will be removed, whereas without the all flag only the currently playing file will be discontinued. 
  '''
  def __init__(self, *args, **kwargs):
    super(BreakCommand, self).__init__(*args, **kwargs)
    self._stop_all = kwargs.get('stop_all', False)

  def stop_all(self):
    return self._stop_all

  def __str__(self):
    if not self._stop_all:
      return 'bgapi uuid_break %s\nJob-UUID: %s\n\n' % (self._uuid,
        self._job_uuid)
    else:
      return 'bgapi uuid_break %s all\nJob-UUID: %s\n\n' % (self._uuid,
        self._job_uuid)

class BridgeCommand(UUIDCommand):
  '''
  Bridge two call legs together. Bridge needs atleast any one leg to be answered. 
  
  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              other_uuid - universal unique identifier to Bridge.
  '''
  def __init__(self, *args, **kwargs):
    super(BridgeCommand, self).__init__(*args, **kwargs)
    self._other_uuid = kwargs.get('other_uuid')
    if not self._other_uuid:
      raise ValueError('The value of other_uuid must be a valid UUID.')

  def other_uuid(self):
    return self._other_uuid

  def __str__(self):
    return 'bgapi uuid_bridge %s %s\nJob-UUID: %s\n\n' % (
      self._uuid, self._other_uuid, self._job_uuid)

class BroadcastCommand(UUIDCommand):
  '''
  Execute an arbitrary dialplan application on a specific <uuid>. 
  If a filename is specified then it is played into the channel(s).
  To execute an application use <app_name> and <app_args> syntax.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              leg - select which leg(s) to use [aleg|bleg|both].
              path - the path to the audio file to be played into the channels.*
              app_name - application name to be executed on the channel(s).*2
              app_args - arguments to the application(s) being executed on the channel(s).
  
  * Can provide path Or app_name, but not both. 
  '''
  def __init__(self, *args, **kwargs):
    super(BroadcastCommand, self).__init__(*args, **kwargs)
    self._leg = kwargs.get('leg')
    if not self._leg or not self._leg == 'aleg' and \
      not self._leg == 'bleg' and not self._leg == 'both':
      raise ValueError('The leg value %s is invalid' % self._leg)
    self._path = kwargs.get('path')
    self._app_name = kwargs.get('app_name')
    self._app_args = kwargs.get('app_args')
    if self._path and self._app_name:
      raise RuntimeError('A broadcast EventSocketCommand can specify either a path ' \
                         'or an app_name but not both.')

  def leg(self):
    return self._leg

  def path(self):
    return self._path

  def app_name(self):
    return self._app_name

  def app_args(self):
    return self._app_args

  def __str__(self):
    buffer = StringIO()
    buffer.write('bgapi uuid_broadcast %s ' % self._uuid)
    if self._path:
      buffer.write('%s' % self._path)
    else:
      buffer.write('%s' % self._app_name)
      if self._app_args:
        buffer.write('::%s' % self._app_args)
    buffer.write(' %s\nJob-UUID: %s\n\n' % (self._leg, self._job_uuid))
    try:
      return buffer.getvalue()
    finally:
      buffer.close()

class ChatCommand(UUIDCommand):
  '''
  Send a chat message. If the endpoint associated with the session 
  <uuid> has a receive_event handler, this message gets sent to that 
  session and is interpreted as an instant message. 
  
  Arguments:  sender - the freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              text - message to be sent.
  '''
  def __init__(self, *args, **kwargs):
    super(ChatCommand, self).__init__(*args, **kwargs)
    self._text = kwargs.get('text', '')

  def text(self):
    return self._text

  def __str__(self):
    return 'bgapi uuid_chat %s %s\nJob-UUID: %s\n\n' % (
      self._uuid, self._text, self._job_uuid)

class CheckUserGroupCommand(BackgroundCommand):
  '''
  Determine if a <user> is in a group. 

  Arguments: sender - the freepy actor sending this EventSocketCommand.
             'user' - username.
             'domain' - domain name.
             'group_name' - group name.
  '''  
  def __init__(self, sender, **kwargs):
    super(CheckUserGroupCommand, self).__init__(sender)
    self._user = kwargs.get('user')
    self._domain = kwargs.get('domain')
    self._group_name = kwargs.get('group_name')

  def domain(self):
    return self._domain

  def group_name(self):
    return self._group_name

  def user(self):
    return self._user

  def __str__(self):
    if not self._domain:
      return 'bgapi in_group %s %s\nJob-UUID: %s\n\n' % (
        self._user, self._group_name, self._job_uuid)
    else:
      return 'bgapi in_group %s@%s %s\nJob-UUID: %s\n\n' % (
        self._user, self._domain, self._group_name, self._job_uuid)

class DeflectCommand(UUIDCommand):
  '''
  Deflect an answered SIP call off of FreeSWITCH by sending the REFER method.
  Deflect waits for the final response from the far end to be reported. 
  It returns the sip fragment from that response as the text in the FreeSWITCH 
  response to uuid_deflect. If the far end reports the REFER was successful, 
  then FreeSWITCH will issue a bye on the channel. 
  
  Arguments:  sender - the freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              url - SIP url.
  '''
  def __init__(self, *args, **kwargs):
    super(DeflectCommand, self).__init__(*args, **kwargs)
    self._url = kwargs.get('url')

  def url(self):
    return self._url

  def __str__(self):
    return 'bgapi uuid_deflect %s %s\nJob-UUID: %s\n\n' % (
      self._uuid, self._url, self._job_uuid)

class DialedExtensionHupAllCommand(BackgroundCommand):
  '''
  Can be used to disconnect existing calls to an extension.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             clearing - clearing type. 
             extension - extension number to be disconnected.
  '''  
  def __init__(self, sender, **kwargs):
    super(DialedExtensionHupAllCommand, self).__init__(sender)
    self._clearing = kwargs.get('clearing')
    self._extension = kwargs.get('extension')

  def clearing(self):
    return self._clearing

  def extension(self):
    return self._extension

  def __str__(self):
    return 'bgapi fsctl hupall %s dialed_ext %s\nJob-UUID: %s\n\n' % (
      self._clearing, self._extension, self._job_uuid)

class DigestAuthCommand(BackgroundCommand):
  '''
  Ask FreeSWITCH to authenticate a client.
  '''

  def __init__(self, *args, **kwargs):
    super(DigestAuthCommand, self).__init__(*args, **kwargs)
    self.__realm__ = kwargs.get('realm')

  def realm(self):
    return self.__realm__

  def __str__(self):
    if self.__realm__ is not None:
      return 'bgapi respond 407 %s' % (self.__realm__)
    else:
      return 'bgapi respond 407'

class DisableMediaCommand(UUIDCommand):
  '''
  Reinvite FreeSWITCH out of the media path: 
  
  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(DisableMediaCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_media off %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class DisableVerboseEventsCommand(BackgroundCommand):
  '''
  Disable verbose events. Verbose events have every channel variable in every event 
  for a particular channel. Non-verbose events have only the pre-selected channel 
  variables in the event headers. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(DisableVerboseEventsCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl verbose_events off\nJob-UUID: %s\n\n' % self._job_uuid

class DisplayCommand(UUIDCommand):
  '''
  Updates the display on a phone if the phone supports this. This works on some SIP 
  phones right now including Polycom and Snom. This EventSocketCommand makes the phone re-negotiate 
  the codec. The SIP -> RTP Packet Size should be 0.020. If it is set to 0.030 on the SPA 
  series phones it causes a DTMF lag. When DTMF keys are pressed on the phone they are can 
  be seen on the fs_cli 4-6 seconds late. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              display - screen display.
  '''
  def __init__(self, *args, **kwargs):
    super(DisplayCommand, self).__init__(*args, **kwargs)
    self._display = kwargs.get('display')

    def display(self):
      return self._display

  def __str__(self):
    return 'bgapi uuid_display %s %s\nJob-UUID: %s\n\n' % (
      self._uuid, self._display, self._job_uuid)

class DomainExistsCommand(BackgroundCommand):
  '''
  Check if a domain exists. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             domain - domain to check.
  '''  
  def __init__(self, sender, **kwargs):
    super(DomainExistsCommand, self).__init__(sender)
    self.__domain__ = kwargs.get('domain')

  def domain(self):
    return self.__domain__

  def __str__(self):
    return 'bgapi domain_exists %s\nJob-UUID: %s\n\n' % (self.__domain__,
      self._job_uuid)

class DualTransferCommand(UUIDCommand):
  '''
  Transfer each leg of a call to different destinations. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              extension_a - target extension for aleg
              dialplan_a - target dialplan for aleg
              context_a - target context for aleg
              extension_b - target extension for bleg
              dialplan_b - target dialplan for bleg
              context_b - target context for bleg
  '''
  def __init__(self, *args, **kwargs):
    super(DualTransferCommand, self).__init__(*args, **kwargs)
    self.__extension_a__ = kwargs.get('extension_a')
    self.__extension_b__ = kwargs.get('extension_b')
    self.__dialplan_a__ = kwargs.get('dialplan_a')
    self.__dialplan_b__ = kwargs.get('dialplan_b')
    self.__context_a__ = kwargs.get('context_a')
    self.__context_b__ = kwargs.get('context_b')
    if not self.__extension_a__ and not self.__extension_b__:
      raise RuntimeError('A dual transfer EventSocketCommand requires the extension_a' \
                         'and extension_b parameters to be provided.')

  def extension_a(self):
    return self.__extension_a__

  def extension_b(self):
    return self.__extension_b__

  def dialplan_a(self):
    return self.__dialplan_a__

  def dialplan_b(self):
    return self.__dialplan_b__

  def context_a(self):
    return self.__context_a__

  def context_b(self):
    return self.__context_b__

  def __str__(self):
    buffer = StringIO()
    buffer.write(self.__extension_a__)
    if self.__dialplan_a__:
      buffer.write('/%s' % self.__dialplan_a__)
    if self.__context_a__:
      buffer.write('/%s' % self.__context_a__)
    destination_a = buffer.getvalue()
    buffer.seek(0)
    buffer.write(self.__extension_b__)
    if self.__dialplan_b__:
      buffer.write('/%s' % self.__dialplan_b__)
    if self.__context_b__:
      buffer.write('/%s' % self.__context_b__)
    destination_b = buffer.getvalue()
    buffer.close()
    return 'bgapi uuid_dual_transfer %s %s %s\nJob-UUID: %s\n\n' % (
      self._uuid, destination_a, destination_b, self._job_uuid)

class DumpCommand(UUIDCommand):
  '''
  Dumps all variable values for a session. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              format - variable values output format. Default output XML.
  '''
  def __init__(self, *args, **kwargs):
    super(DumpCommand, self).__init__(*args, **kwargs)
    self._format = kwargs.get('format', 'XML')

  def format(self):
    return self._format

  def __str__(self):
    return 'bgapi uuid_dump %s %s\nJob-UUID: %s\n\n' % (
      self._uuid, self._format, self._job_uuid)

class EarlyOkayCommand(UUIDCommand):
  '''
  Stops the process of ignoring early media, i.e. if ignore_early_media=true 
  it stops ignoring early media and responds normally. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(EarlyOkayCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_early_ok %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class EnableMediaCommand(UUIDCommand):
  '''
  Reinvite FreeSWITCH into the media path: 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(EnableMediaCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_media %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class EnableSessionHeartbeatCommand(UUIDCommand):
  '''
  Enable session Heartbeat.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              start_time - seconds in the future to start.
  '''
  def __init__(self, *args, **kwargs):
    super(EnableSessionHeartbeatCommand, self).__init__(*args, **kwargs)
    self._start_time = kwargs.get('start_time') # Seconds in the future to start

  def start_time(self):
    return self._start_time

  def __str__(self):
    if not self._start_time:
      return 'bgapi uuid_session_heartbeat %s\nJob-UUID: %s\n\n' % (
        self._uuid, self._job_uuid)
    else:
      return 'bgapi uuid_session_heartbeat %s sched %i\nJob-UUID: %s\n\n' % (
        self._uuid, self._start_time, self._job_uuid)

class EnableVerboseEventsCommand(BackgroundCommand):
  '''
  Enable verbose events. Verbose events have every channel variable in every event 
  for a particular channel. Non-verbose events have only the pre-selected channel 
  variables in the event headers. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  

  def __init__(self, sender, **kwargs):
    super(EnableVerboseEventsCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl verbose_events on\nJob-UUID: %s\n\n' % self._job_uuid

class EventsCommand(EventSocketCommand):
  def __init__(self, sender, **kwargs):
    super(EventsCommand, self).__init__(sender)
    self._events = kwargs.get('events', ['BACKGROUND_JOB'])
    self._format = kwargs.get('format', 'plain')
    if(self._format is not 'json' and \
       self._format is not 'plain' and \
       self._format is not 'xml'):
      raise ValueError('The FreeSWITCH event socket only supports the ' + \
                       'following formats: json, plain, xml')

  def __str__(self):
    return 'event %s %s\n\n' % (self._format, ' '.join(self._events))

class FileManagerCommand(UUIDCommand):
  '''
  Manage the audio being played into a channel from a sound file

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              EventSocketCommand - a parameter which controls what action should be taken*
              value - the value of the EventSocketCommand**

  * Available Commands : 
  [speed]
  [volume]
  [pause]
  [stop]
  [truncate]
  [restart]
  [seek]
  ** Unit of measurement is milliseconds
  '''
  def __init__(self, *args, **kwargs):
    super(FileManagerCommand, self).__init__(*args, **kwargs)
    self._command = kwargs.get('EventSocketCommand')
    if not self._command or not self._command == 'speed' and \
      not self._command == 'volume' and not self._command == 'pause' and \
      not self._command == 'stop' and not self._command == 'truncate' and \
      not self._command == 'restart' and not self._command == 'seek':
      raise ValueError(
        'The EventSocketCommand parameter %s is invalid.' % self._command)
    self._value = kwargs.get('value')

  def command(self):
    return self._command

  def value(self):
    return self._value

  def __str__(self):
    if self._value:
      return 'bgapi uuid_fileman %s %s:%s\nJob-UUID: %s\n\n' % (
        self._uuid, self._command, self._value, self._job_uuid)
    else:
      return 'bgapi uuid_fileman %s %s\nJob-UUID: %s\n\n' % (
        self._uuid, self._command, self._job_uuid)

class FlushDTMFCommand(UUIDCommand):
  '''
  Flush queued DTMF digits.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(FlushDTMFCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_flush_dtmf %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class GetAudioLevelCommand(UUIDCommand):
  '''
  Get the Audio Level 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(GetAudioLevelCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_audio %s start read level\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class GetBugListCommand(UUIDCommand):
  '''
  List the media bugs on channel.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(GetBugListCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_buglist %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class GetDefaultDTMFDurationCommand(BackgroundCommand):
  '''
  Gets the current value of default dtmf duration.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(GetDefaultDTMFDurationCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl default_dtmf_duration 0\nJob-UUID: %s\n\n' % self._job_uuid

class GetGlobalVariableCommand(BackgroundCommand):
  '''
  Gets the value of a global variable. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             name - the name of a global variable*

  * If the parameter is not provided then it gets all the global variables. 
  '''  
  def __init__(self, sender, **kwargs):
    super(GetGlobalVariableCommand, self).__init__(sender)
    self._name = kwargs.get('name')
    if not self._name:
      raise ValueError('The name parameter is required.')

  def name(self):
    return self._name

  def __str__(self):
    return 'bgapi global_getvar %s\nJob-UUID: %s\n\n' % (self._name,
      self._job_uuid)

class GetMaxSessionsCommand(BackgroundCommand):
  '''
  Gets the value of the Maximum Sessions. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(GetMaxSessionsCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl max_sessions\nJob-UUID: %s\n\n' % self._job_uuid

class GetMaximumDTMFDurationCommand(BackgroundCommand):
  '''
  Gets the current value of maximum dtmf duration.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(GetMaximumDTMFDurationCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl max_dtmf_duration 0\nJob-UUID: %s\n\n' % self._job_uuid

class GetMinimumDTMFDurationCommand(BackgroundCommand):
  '''
  Gets the current value of minimum dtmf duration.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(GetMinimumDTMFDurationCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl min_dtmf_duration 0\nJob-UUID: %s\n\n' % self._job_uuid

class GetSessionsPerSecondCommand(BackgroundCommand):
  '''
  Query the actual sessions-per-second. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(GetSessionsPerSecondCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl last_sps\nJob-UUID: %s\n\n' % self._job_uuid

class GetVariableCommand(UUIDCommand):
  '''
  Get a variable from a channel. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              name - the name of the variable to get from a channel
  '''
  def __init__(self, *args, **kwargs):
    super(GetVariableCommand, self).__init__(*args, **kwargs)
    self.__name__ = kwargs.get('name')
    if not self.__name__:
      raise ValueError('The name parameter is requied.')

  def name(self):
    return self.__name__

  def __str__(self):
    return 'bgapi uuid_getvar %s %s\nJob-UUID: %s\n\n' % (self._uuid,
      self.__name__, self._job_uuid)

class GetGroupCallBridgeStringCommand(BackgroundCommand):
  '''
  Returns the bridge string defined in a call group.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             group - group name
             domain - domain name
             option - valid options [+F, +A, +E] *

  * +F
      will return the group members in a serial fashion (separated by |), 
    +A 
      will return them in a parallel fashion (separated by ,) 
    +E 
      will return them in a enterprise fashion (separated by :_:). 
  '''  

  def __init__(self, sender, **kwargs):
    super(GetGroupCallBridgeStringCommand, self).__init__(sender)
    self.__group__ = kwargs.get('group')
    self.__domain__ = kwargs.get('domain')
    self.__option__ = kwargs.get('option')
    if self.__option__ and not self.__option__ == '+F' and \
      not self.__option__ == '+A' and not self.__option__ == '+E':
      raise ValueError('The option parameter %s is invalid.' % self.__option__)

  def domain(self):
    return self.__domain__

  def group(self):
    return self.__group__

  def option(self):
    return self.__option__

  def __str__(self):
    if not self.__option__:
      return 'bgapi group_call %s@%s\nJob-UUID: %s\n\n' % (self.__group__,
        self.__domain__, self._job_uuid)
    else:
      return 'bgapi group_call %s@%s%s\nJob-UUID: %s\n\n' % (self.__group__,
        self.__domain__, self.__option__, self._job_uuid)

class HoldCommand(UUIDCommand):
  '''
  Place a call on hold. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(HoldCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_hold %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class HupAllCommand(BackgroundCommand):
  '''
  Disconnect existing channels. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             cause - the reason.
             var_name - optional parameter variable name.
             var_value - optional parameter variable value. 
  '''  

  def __init__(self, sender, **kwargs):
    super(HupAllCommand, self).__init__(sender)
    self.__cause__ = kwargs.get('cause')
    self.__var_name__ = kwargs.get('var_name')
    self.__var_value__ = kwargs.get('var_value')

  def cause(self):
    return self.__cause__

  def variable_name(self):
    return self.__var_name__

  def variable_value(self):
    return self.__var_value__

  def __str__(self):
    if self.__var_name__ and self.__var_value__:
      return 'bgapi hupall %s %s %s\nJob-UUID: %s\n\n' % (self.__cause__,
        self.__var_name__, self.__var_value__, self._job_uuid)
    else:
      return 'bgapi hupall %s\nJob-UUID: %s\n\n' % (self.__cause__,
        self._job_uuid)

class KillCommand(UUIDCommand):
  '''
  Reset a specific <uuid> channel. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              cause - reason for reset.
  '''
  def __init__(self, *args, **kwargs):
    super(KillCommand, self).__init__(*args, **kwargs)
    self.__cause__ = kwargs.get('cause')

  def cause(self):
    return self.__cause__

  def __str__(self):
    if not self.__cause__:
      return 'bgapi uuid_kill %s\nJob-UUID: %s\n\n' % (self._uuid,
        self._job_uuid)
    else:
      return 'bgapi uuid_kill %s %s\nJob-UUID: %s\n\n' % (self._uuid,
        self.__cause__, self._job_uuid)

class LimitCommand(UUIDCommand):
  '''
  Apply or change limit(s) on a specified uuid. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              backend - The backend to use. 
              realm - Arbitrary name.
              resource - The resource on which to limit the number of calls. 
              max_calls - The maximum number of concurrent calls allowed to pass 
                          or a call rate in calls/sec. If not set or set to a negative 
                          value the limit application only acts as a counter.
              interval - calls per second.
              number - destination number
              dialplan - destination dialplan
              context - destination context
  '''
  def __init__(self, *args, **kwargs):
    super(LimitCommand, self).__init__(*args, **kwargs)
    self.__backend__ = kwargs.get('backend')
    self.__realm__ = kwargs.get('realm')
    self.__resource__ = kwargs.get('resource')
    self.__max_calls__ = kwargs.get('max_calls')
    self.__interval__ = kwargs.get('interval')
    self.__number__ = kwargs.get('number')
    self.__dialplan__ = kwargs.get('dialplan')
    self.__context__ = kwargs.get('context')

  def backend(self):
    return self.__backend__

  def realm(self):
    return self.__realm__

  def resource(self):
    return self.__resource__

  def max_calls(self):
    return self.__max_calls__

  def __str__(self):
    buffer = StringIO()
    buffer.write('bgapi uuid_limit %s %s %s %s' % (self._uuid,
      self.__backend__, self.__realm__, self.__resource__))
    if self.__max_calls__:
      buffer.write(' %i' % self.__max_calls__)
      if self.__interval__:
        buffer.write('/%i' % self.__interval__)
    if self.__number__:
      buffer.write(' %s' % self.__number__)
      if self.__dialplan__:
        buffer.write(' %s' % self.__dialplan__)
        if self.__context__:
          buffer.write(' %s' % self.__context__)
    buffer.write('\nJob-UUID: %s\n\n' % self._job_uuid)
    try:
      return buffer.getvalue()
    finally:
      buffer.close()

class LoadModuleCommand(BackgroundCommand):
  '''
  Load external module 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             name - module name.
  '''  
  def __init__(self, sender, **kwargs):
    super(LoadModuleCommand, self).__init__(sender)
    self.__name__ = kwargs.get('name')

  def name(self):
    return self.__name__

  def __str__(self):
    return 'bgapi load %s\nJob-UUID: %s\n\n' % (self.__name__,
      self._job_uuid)

class MaskRecordingCommand(UUIDCommand):
  '''
  Mask the audio associated with the given UUID into a file.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             uuid - universal unique identifier.
             path - The path where the recording should be stored.
  '''  

  def __init__(self, *args, **kwargs):
    super(MaskRecordingCommand, self).__init__(*args, **kwargs)
    self.__path__ = kwargs.get('path', None)
    if not self.__path__:
      raise ValueError('A valid path parameter must be specified.')

  def __str__(self):
    return 'bgapi uuid_record %s mask %s\nJob-UUID: %s\n\n' % (self._uuid, self.__path__, \
                                                               self._job_uuid)

class OriginateCommand(BackgroundCommand):
  '''
  Originate a new call. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             url - URL you are calling.
             extension - call extension.
             app_name - *
             app_args - arguments to the app specified by app_name
             options - **
  
  * These are valid application names that can be used in this context :
    park, bridge, javascript/lua/perl, playback (remove mod_native_file), and many others. 
  ** The following are options that can be passed :
      group_confirm_key
      group_confirm_file
      forked_dial
      fail_on_single_reject
      ignore_early_media
      return_ring_ready
      originate_retries
      originate_retry_sleep_ms
      origination_caller_id_name
      origination_caller_id_number
      originate_timeout
      sip_auto_answer 
  '''  

  def __init__(self, sender, **kwargs):
    super(OriginateCommand, self).__init__(sender)
    self._url = kwargs.get('url')
    self._extension = kwargs.get('extension')
    self._app_name = kwargs.get('app_name')
    self._app_args = kwargs.get('app_args', [])
    if not isinstance(self._app_args, list):
      raise TypeError('The app_args parameter must be a list type.')
    self._options = kwargs.get('options', [])
    if not isinstance(self._options, list):
      raise TypeError('The options parameter must be a list type.')
    if self._extension and self._app_name:
      raise RuntimeError('An originate EventSocketCommand can specify either an '\
                         'extension or an app_name but not both.')

  def app_name(self):
    return self._app_name

  def app_args(self):
    return self._app_args

  def extension(self):
    return self._extension

  def options(self):
    return self._options

  def url(self):
    return self._url

  def __str__(self):
    buffer = StringIO()
    buffer.write('bgapi originate ')
    if self._options:
      buffer.write('{%s}' % ','.join(self._options))
    buffer.write('%s ' % self._url)
    if self._extension:
      buffer.write('%s' % self._extension)
    else:
      if self._app_args:
        buffer.write('\'&%s(%s)\'' % (self._app_name, ' '.join(self._app_args)))
      else:
        buffer.write('&%s()' % self._app_name)
    buffer.write('\nJob-UUID: %s\n\n' % self._job_uuid)
    try:
      return buffer.getvalue()
    finally:
      buffer.close()

class ParkCommand(UUIDCommand):
  '''
  Park call 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(ParkCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_park %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class PauseCommand(UUIDCommand):
  '''
  Pause <uuid> media 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(PauseCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi pause %s on\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class PauseSessionCreationCommand(BackgroundCommand):
  '''
  inbound or outbound may optionally be specified to pause just inbound or outbound 
  session creation, both paused if nothing specified. resume has similar behavior. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             direction - inbound or outbound or None paramater value.
  '''  

  def __init__(self, sender, **kwargs):
    super(PauseSessionCreationCommand, self).__init__(sender)
    self.__direction__ = kwargs.get('direction')

  def direction(self):
    return self.__direction__

  def __str__(self):
    if not self.__direction__:
      return 'bgapi fsctl pause\nJob-UUID: %s\n\n' % self._job_uuid
    else:
      return 'bgapi fsctl pause %s\nJob-UUID: %s\n\n' % (self.__direction__,
        self._job_uuid)

class PreAnswerCommand(UUIDCommand):
  '''
  Preanswer a channel. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(PreAnswerCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_pre_answer %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class PreProcessCommand(UUIDCommand):
  '''
  Pre-process Channel 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(PreProcessCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_preprocess %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class ReceiveDTMFCommand(UUIDCommand):
  '''
  Receve DTMF digits to <uuid> set.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              digits - Use the character w for a .5 second delay and the character W for a 1 second delay.
              tone_duration - Default tone duration is 2000ms. 
  '''
  def __init__(self, *args, **kwargs):
    super(ReceiveDTMFCommand, self).__init__(*args, **kwargs)
    self.__digits__ = kwargs.get('digits')
    self.__duration__ = kwargs.get('tone_duration')

  def digits(self):
    return self.__digits__

  def tone_duration(self):
    return self.__duration__

  def __str__(self):
    if not self.__duration__:
      return 'bgapi uuid_recv_dtmf %s %s\nJob-UUID: %s\n\n' % (self._uuid,
        self.__digits__, self._job_uuid)
    else:
      return 'bgapi uuid_recv_dtmf %s %s@%s\nJob-UUID: %s\n\n' % (self._uuid,
        self.__digits__, self.__duration__, self._job_uuid)

class ReclaimMemoryCommand(BackgroundCommand):
  '''
  Reclaim Memory

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  

  def __init__(self, sender, **kwargs):
    super(ReclaimMemoryCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl reclaim_mem\nJob-UUID: %s\n\n' % self._job_uuid

class RenegotiateMediaCommand(UUIDCommand):
  '''
  API EventSocketCommand to tell a channel to send a re-invite with optional list of new codecs

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              codec - audio/video codec.
  '''
  def __init__(self, *args, **kwargs):
    super(RenegotiateMediaCommand, self).__init__(*args, **kwargs)
    self.__codec__ = kwargs.get('codec')

  def codec(self):
    return self.__codec__

  def __str__(self):
    return 'bgapi uuid_media_reneg %s =%s\nJob-UUID: %s\n\n' % (self._uuid,
      self.__codec__, self._job_uuid)

class ResumeSessionCreationCommand(BackgroundCommand):
  '''
  inbound or outbound may optionally be specified to resume just inbound or outbound session creation,
  both paused if nothing specified.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             direction - inbound or outbound or None paramater value.
  '''  

  def __init__(self, sender, **kwargs):
    super(ResumeSessionCreationCommand, self).__init__(sender)
    self.__direction__ = kwargs.get('direction')

  def direction(self):
    return self.__direction__

  def __str__(self):
    if not self.__direction__:
      return 'bgapi fsctl resume\nJob-UUID: %s\n\n' % self._job_uuid
    else:
      return 'bgapi fsctl resume %s\nJob-UUID: %s\n\n' % (self.__direction__,
        self._job_uuid)

class RingReadyCommand(UUIDCommand):
  '''
  Send a 180 Ringing to the client. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(RingReadyCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_ring_ready %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class SendDTMFCommand(UUIDCommand):
  '''
  Send DTMF digits to <uuid> set.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              digits - Use the character w for a .5 second delay and the character W for a 1 second delay.
              tone_duration - Default tone duration is 2000ms. 
  '''
  def __init__(self, *args, **kwargs):
    super(SendDTMFCommand, self).__init__(*args, **kwargs)
    self.__digits__ = kwargs.get('digits')
    self.__duration__ = kwargs.get('tone_duration')

  def digits(self):
    return self.__digits__

  def tone_duration(self):
    return self.__duration__

  def __str__(self):
    if not self.__duration__:
      return 'bgapi uuid_send_dtmf %s %s\nJob-UUID: %s\n\n' % (self._uuid,
        self.__digits__, self._job_uuid)
    else:
      return 'bgapi uuid_send_dtmf %s %s@%i\nJob-UUID: %s\n\n' % (self._uuid,
        self.__digits__, self.__duration__, self._job_uuid)

class SendInfoCommand(UUIDCommand):
  '''
  Send info to the endpoint.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(SendInfoCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_send_info %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class SendMessageCommand(BackgroundCommand):
  '''
  Send a SIP message.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             host - The host to which we will send the message.
             user - The user to which we will send the message.
             profile - The profile to use for sending the message.
             content_type - The type of content being sent.
             body - The message body.

  '''
  def __init__(self, sender, **kwargs):
    super(SendMessageCommand, self).__init__(sender)
    self.__host__ = kwargs.get('host')
    self.__user__ = kwargs.get('user')
    self.__profile__ = kwargs.get('profile')
    self.__content_type__ = kwargs.get('content_type')
    self.__body__ = kwargs.get('body')

  def __str__(self):
    return 'sendevent SEND_MESSAGE\n' \
           'profile: %s\n' \
           'content-length: %i\n' \
           'content-type: %s\n' \
           'user: %s\n' \
           'host: %s\n' \
           '\n%s\n' % (
            self.__profile__,
            len(self.__body__),
            self.__content_type__,
            self.__user__,
            self.__host__,
            self.__body__)

class SetAudioLevelCommand(UUIDCommand):
  '''
  Adjust the audio levels on a channel or mute (read/write) via a media bug.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              level - is in the range from -4 to 4, 0 being the default value. 
  '''
  def __init__(self, *args, **kwargs):
    super(SetAudioLevelCommand, self).__init__(*args, **kwargs)
    self.__audio_level__ = kwargs.get('level')
    if not self.__audio_level__ or self.__audio_level__ < -4.0 or \
      self.__audio_level__ > 4.0:
      raise ValueError('The level value %s is invalid.' % self.__audio_level__)

  def level(self):
    return self.__audio_level__

  def __str__(self):
    return 'bgapi uuid_audio %s start write level %f\nJob-UUID: %s\n\n' % (self._uuid,
      self.__audio_level__, self._job_uuid)

class SetDefaultDTMFDurationCommand(BackgroundCommand):
  '''
  Sets the default_dtmf_duration switch parameter. The number is in clock ticks (CT) where 
  CT / 8 = ms. The default_dtmf_duration specifies the DTMF duration to use on 
  originated DTMF events or on events that are received without a duration specified. 
  This value can be increased or lowered. This value is lower-bounded by min_dtmf_duration 
  and upper-bounded by max_dtmf_duration.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             duration - paramter value.
  '''  

  def __init__(self, sender, **kwargs):
    super(SetDefaultDTMFDurationCommand, self).__init__(sender)
    self.__duration__ = kwargs.get('duration')

  def duration(self):
    return self.__duration__

  def __str__(self):
    return 'bgapi fsctl default_dtmf_duration %i\nJob-UUID: %s\n\n' % (self.__duration__,
      self._job_uuid)

class SetGlobalVariableCommand(BackgroundCommand):
  '''
  Sets the value of a global variable. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             name - name of global variable
             value - value of global variable
  '''  

  def __init__(self, sender, **kwargs):
    super(SetGlobalVariableCommand, self).__init__(sender)
    self._name = kwargs.get('name')
    self._value = kwargs.get('value')
    if not self._name or not self._value:
      raise RuntimeError('The set global variable EventSocketCommand requires both name ' \
                         'and value parameters.')

  def name(self):
    return self._name

  def value(self):
    return self._value

  def __str__(self):
    return 'bgapi global_setvar %s=%s\nJob-UUID: %s\n\n' % (self._name,
                                                            self._value, self._job_uuid)

class SetMaximumDTMFDurationCommand(BackgroundCommand):
  '''
  Sets the max_dtmf_duration switch parameter. The number is in clock ticks (CT) where CT / 8 = ms. 
  The max_dtmf_duration caps the playout of a DTMF event at the specified duration. 
  Events exceeding this duration will be truncated to this duration. 
  You cannot configure a duration on a profile that exceeds this setting. 
  This setting can be lowered, but cannot exceed 192000 (the default). 
  This setting cannot be set lower than min_dtmf_duration.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             duration - the maximum duration if a DTMF event. 
  '''  

  def __init__(self, sender, **kwargs):
    super(SetMaximumDTMFDurationCommand, self).__init__(sender)
    self.__duration__ = kwargs.get('duration')

  def duration(self):
    return self.__duration__

  def __str__(self):
    return 'bgapi fsctl max_dtmf_duration %i\nJob-UUID: %s\n\n' % (self.__duration__,
      self._job_uuid)

class SetMinimumDTMFDurationCommand(BackgroundCommand):
  '''
  Sets the min_dtmf_duration switch parameter to 100ms. The number is in clock ticks where clockticks / 8 = ms. 
  The min_dtmf_duration specifies the minimum DTMF duration to use on outgoing events. 
  Events shorter than this will be increased in duration to match min_dtmf_duration. 
  You cannot configure a DTMF duration on a profile that is less than this setting. 
  You may increase this value, but cannot set it lower than 400 (the default). 
  This value cannot exceed max_dtmf_duration.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             duration - value of parameter.
  '''  

  def __init__(self, sender, **kwargs):
    super(SetMinimumDTMFDurationCommand, self).__init__(sender)
    self.__duration__ = kwargs.get('duration')

  def duration(self):
    return self.__duration__

  def __str__(self):
    return 'bgapi fsctl min_dtmf_duration %i\nJob-UUID: %s\n\n' % (self.__duration__,
      self._job_uuid)

class SetMultipleVariableCommand(UUIDCommand):
  '''
  Set multiple vars on a channel. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              variables - a dictionary list of key/value pairs to set.
  '''
  def __init__(self, *args, **kwargs):
    super(SetMultipleVariableCommand, self).__init__(*args, **kwargs)
    self.__variables__ = kwargs.get('variables')
    if not isinstance(self.__variables__, dict):
      raise TypeError('The variables parameter must be of type dict.')
    variable_list = list()
    for key, value in self.__variables__.iteritems():
      variable_list.append('%s=%s' % (key, value))
    self.__variables_string__ = ';'.join(variable_list)

  def __str__(self):
    return 'bgapi uuid_setvar_multi %s %s\nJob-UUID: %s\n\n' % (self._uuid,
      self.__variables_string__, self._job_uuid)

class SetSessionsPerSecondCommand(BackgroundCommand):
  '''
  This changes the sessions-per-second limit as initially set in switch.conf 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             sessions_per_second - value for paramater.
  '''  

  def __init__(self, sender, **kwargs):
    super(SetSessionsPerSecondCommand, self).__init__(sender)
    self.__sessions_per_second__ = kwargs.get('sessions_per_second')

  def sessions_per_second(self):
    return self.__sessions_per_second__

  def __str__(self):
    return 'bgapi fsctl sps %i\nJob-UUID: %s\n\n' % (self.__sessions_per_second__,
      self._job_uuid)

class SetVariableCommand(UUIDCommand):
  '''
  Set a variable on a channel.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              name - name of the variable.
              value - value of the variable.
  '''
  def __init__(self, *args, **kwargs):
    super(SetVariableCommand, self).__init__(*args, **kwargs)
    self.__name__ = kwargs.get('name')
    self.__value__ = kwargs.get('value')
    if not self.__name__ or not self.__value__:
      raise RuntimeError('The set variable EventSocketCommand requires both name ' \
                         'and value parameters.')

  def name(self):
    return self.__name__

  def value(self):
    return self.__value__

  def __str__(self):
    return 'bgapi uuid_setvar %s %s %s\nJob-UUID: %s\n\n' % (self._uuid,
      self.__name__, self.__value__, self._job_uuid)

class ShutdownCommand(BackgroundCommand):
  '''
  Stop the FreeSWITCH program. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             option - paramater value [cancel, elegant, asap, restart]*
             
  * available options: 
    cancel - discontinue a previous shutdown request.
    elegant - wait for all traffic to stop; do not prevent new traffic.
    asap - wait for all traffic to stop; do not allow new traffic.
    restart - restart FreeSWITCH immediately following the shutdown. 
  '''  

  def __init__(self, sender, **kwargs):
    super(ShutdownCommand, self).__init__(sender)
    self.__option__ = kwargs.get('option')
    if self.__option__ and not self.__option__ == 'cancel' and \
      not self.__option__ == 'elegant' and not self.__option__ == 'asap' and \
      not self.__option__ == 'restart':
      raise ValueError('The option %s is an invalid option.' % self.__option__)

  def option(self):
    return self.__option__

  def __str__(self):
    if not self.__option__:
      return 'bgapi fsctl shutdown\nJob-UUID: %s\n\n' % self._job_uuid
    else:
      return 'bgapi fsctl shutdown %s\nJob-UUID: %s\n\n' % (self.__option__,
        self._job_uuid)

class SimplifyCommand(UUIDCommand):
  '''
  This EventSocketCommand directs FreeSWITCH to remove itself from the SIP signaling path if it can safely do so 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(SimplifyCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_simplify %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class StartDebugMediaCommand(UUIDCommand):
  '''
  Start the Debug Media.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              option - [read|write|both|vread|vwrite|vboth]
  '''
  def __init__(self, *args, **kwargs):
    super(StartDebugMediaCommand, self).__init__(*args, **kwargs)
    self.__option__ = kwargs.get('option')

  def option(self):
    return self.__option__

  def __str__(self):
    return 'bgapi uuid_debug_media %s %s on\nJob-UUID: %s\n\n' % (self._uuid,
      self.__option__, self._job_uuid)

class SmppSendCommand(BackgroundCommand):
  '''
  Sends an SMS message using mod_smpp.

  Arguments:  sender - The freepy actor sending this SmppSendCommand.
              gateway - The SMPP gateway to use for this message.
              source - The mobile number of the SMS sender.
              destination - The mobile number of the SMS recipient.
              message - The 160 character message that will be sent.
  '''
  def __init__(self, sender, **kwargs):
    super(SmppSendCommand, self).__init__(sender)
    self.__destination__ = kwargs.get('destination')
    self.__gateway__ = kwargs.get('gateway')
    self.__message__ = kwargs.get('message')
    self.__source__ = kwargs.get('source')

  def destination(self):
    return self.__destination__

  def gateway(self):
    return self.__gateway__

  def message(self):
    return self.__message__

  def source(self):
    return self.__source__

  def __str__(self):
    return 'bgapi smpp_send %s|%s|%s|%s\nJob-UUID: %s\n\n' % (self.__gateway__,
      self.__destination__, self.__source__, self.__message__,
      self._job_uuid)

class StartDisplaceCommand(UUIDCommand):
  '''
  Displace the audio for the target <uuid> with the specified audio <path>. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              path - path to an audio source (wav, shout, etc...) 
              limit - number of seconds before terminating the displacement
              mux - cause the original audio to be mixed together with 'file', 
              i.e. you can still converse with the other party while the file is playing
  '''
  def __init__(self, *args, **kwargs):
    super(StartDisplaceCommand, self).__init__(*args, **kwargs)
    self.__path__ = kwargs.get('path')
    self.__limit__ = kwargs.get('limit')
    self.__mux__ = kwargs.get('mux')

  def limit(self):
    return self.__limit__

  def mux(self):
    return self.__mux__

  def path(self):
    return self.__path__

  def __str__(self):
    buffer = StringIO()
    buffer.write('bgapi uuid_displace %s start %s' % (self._uuid,
      self.__path__))
    if self.__limit__:
      buffer.write(' %i' % self.__limit__)
    if self.__mux__:
      buffer.write(' mux')
    buffer.write('\nJob-UUID: %s\n\n' % self._job_uuid)
    try:
      return buffer.getvalue()
    finally:
      buffer.close()

class StartRecordingCommand(UUIDCommand):
  '''
  Record the audio associated with the given UUID into a file.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             uuid - universal unique identifier.
             path - The path where the recording should be stored.
             max_length - The max recording length in seconds.
  '''  

  def __init__(self, *args, **kwargs):
    super(StartRecordingCommand, self).__init__(*args, **kwargs)
    self.__path__ = kwargs.get('path', None)
    self.__max_length__ = kwargs.get('max_length', None)
    if not self.__path__:
      raise ValueError('A valid path parameter must be specified.')

  def __str__(self):
    if self.__max_length__:
      return 'bgapi uuid_record %s start %s %i\nJob-UUID: %s\n\n' % (self._uuid, self.__path__, \
                                                                     self.__max_length__, self._job_uuid)
    else:  
      return 'bgapi uuid_record %s start %s\nJob-UUID: %s\n\n' % (self._uuid, self.__path__, \
                                                                  self._job_uuid)

class StatusCommand(BackgroundCommand):
  '''
  Show current status 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(StatusCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi status\nJob-UUID: %s\n\n' % self._job_uuid

class StopDebugMediaCommand(UUIDCommand):
  '''
  Used to stop the debug media.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(StopDebugMediaCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_debug_media %s off\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class StopDisplaceCommand(UUIDCommand):
  '''
  Stop displacing the audio for the target <uuid>

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(StopDisplaceCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_displace %s stop\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class StopRecordingCommand(UUIDCommand):
  '''
  Stop recording the audio associated with the given UUID into a file.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             uuid - universal unique identifier.
             path - The path where the recording should be stored.
  '''  

  def __init__(self, *args, **kwargs):
    super(StopRecordingCommand, self).__init__(*args, **kwargs)
    self._path = kwargs.get('path', None)
    if not self._path:
      raise ValueError('A valid path parameter must be specified.')

  def __str__(self):
    return 'bgapi uuid_record %s stop %s\nJob-UUID: %s\n\n' % (self._uuid, self._path, \
                                                               self._job_uuid)

class SyncClockCommand(BackgroundCommand):
  '''
  FreeSWITCH will not trust the system time. It gets one sample of system time when it first starts and 
  uses the monotonic clock from there. You can sync it back to real time with "fsctl sync_clock"
  Note: 'fsctl sync_clock' immediately takes effect - which can affect the times on your CDRs. 
  You can end up undrebilling/overbilling, or even calls hungup before they originated. 
  e.g. if FS clock is off by 1 month, then your CDRs are going to show calls that lasted for 1 month!
  'fsctl sync_clock_when_idle' is much safer, which does the same sync but doesn't take effect until 
  there are 0 channels in use. That way it doesn't affect any CDRs. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  

  def __init__(self, sender, **kwargs):
    super(SyncClockCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl sync_clock\nJob-UUID: %s\n\n' % self._job_uuid

class SyncClockWhenIdleCommand(BackgroundCommand):
  '''
  You can sync the clock but have it not do it till there are 0 calls (r:2094f2d3) 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
  '''  
  def __init__(self, sender, **kwargs):
    super(SyncClockWhenIdleCommand, self).__init__(sender)

  def __str__(self):
    return 'bgapi fsctl sync_clock_when_idle\nJob-UUID: %s\n\n' % self._job_uuid

class TransferCommand(UUIDCommand):
  '''
  Transfers an existing call to a specific extension within a <dialplan> and <context>.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              leg - bleg or both.
              extension - destination extension.  
              dialplan - destination dialplan.*   
              context - destination context.
  * Dialplan may be "xml" or "directory".
  '''
  def __init__(self, *args, **kwargs):
    super(TransferCommand, self).__init__(*args, **kwargs)
    self._leg = kwargs.get('leg')
    self.__extension__ = kwargs.get('extension')
    self._dialplan = kwargs.get('dialplan')
    self._context = kwargs.get('context')

  def context(self):
    return self._context

  def dialplan(self):
    return self._dialplan

  def extension(self):
    return self.__extension__

  def leg(self):
    return self._leg

  def __str__(self):
    buffer = StringIO()
    buffer.write('bgapi uuid_transfer %s' % self._uuid)
    if self._leg:
      buffer.write(' %s' % self._leg)
    buffer.write(' %s' % self.__extension__)
    if self._dialplan:
      buffer.write(' %s' % self._dialplan)
    if self._context:
      buffer.write(' %s' % self._context)
    buffer.write('\nJob-UUID: %s\n\n' % self._job_uuid)
    try:
      return buffer.getvalue()
    finally:
      buffer.close()

class UnholdCommand(UUIDCommand):
  '''
  Take a call off hold.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(UnholdCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi uuid_hold off %s\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class UnloadModuleCommand(BackgroundCommand):
  '''
  Unload external module. 

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             name - name of external module to unload.
             force - force unload. Default set to False.
  '''  

  def __init__(self, sender, **kwargs):
    super(UnloadModuleCommand, self).__init__(sender)
    self._name = kwargs.get('name')
    self._force = kwargs.get('force', False)

  def name(self):
    return self._name

  def force(self):
    return self._force

  def __str__(self):
    if not self._force:
      return 'bgapi unload %s\nJob-UUID: %s\n\n' % (self._name,
        self._job_uuid)
    else:
      return 'bgapi unload -f %s\nJob-UUID: %s\n\n' % (self._name,
        self._job_uuid)

class UnmaskRecordingCommand(UUIDCommand):
  '''
  Unmask the audio associated with the given UUID into a file.

  Arguments: sender - The freepy actor sending this EventSocketCommand.
             uuid - universal unique identifier.
             path - The path where the recording should be stored.
  '''  

  def __init__(self, *args, **kwargs):
    super(UnmaskRecordingCommand, self).__init__(*args, **kwargs)
    self.__path__ = kwargs.get('path', None)
    if not self.__path__:
      raise ValueError('A valid path parameter must be specified.')

  def __str__(self):
    return 'bgapi uuid_record %s unmask %s\nJob-UUID: %s\n\n' % (self._uuid, self.__path__, \
                                                                 self._job_uuid)

class UnpauseCommand(UUIDCommand):
  '''
  UnPause <uuid> media.

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
  '''
  def __init__(self, *args, **kwargs):
    super(UnpauseCommand, self).__init__(*args, **kwargs)

  def __str__(self):
    return 'bgapi pause %s off\nJob-UUID: %s\n\n' % (self._uuid,
      self._job_uuid)

class UnsetVariableCommand(UUIDCommand):
  '''
  UnSet a variable on a channel. 

  Arguments:  sender - The freepy actor sending this EventSocketCommand.
              uuid - universal unique identifier.
              name - variable to be unset.
  '''
  def __init__(self, *args, **kwargs):
    super(UnsetVariableCommand, self).__init__(*args, **kwargs)
    self._name = kwargs.get('name')
    if not self._name:
      raise RuntimeError('The unset variable commands requires the name ' \
                         'parameter.')

  def name(self):
    return self._name

  def __str__(self):
    return 'bgapi uuid_setvar %s %s\nJob-UUID: %s\n\n' % (self._uuid,
                                                          self._name, self._job_uuid)
