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

from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET

# The Event Socket configuration used to connect to FreeSWITCH.
freeswitch = {
  'name':     'FreeSWITCH',
  'address':  '127.0.0.1',
  'port':      8021,
  'password': 'ClueCon'
}

# The HTTP server configuration.
http = {
  'port': 8080,
  'pages': {
    # '404': '/path/to/404.html'
  }
}

# The possible logging level values are:
#   CRITICAL
#   ERROR
#   WARNING
#   INFO
#   DEBUG
#   NOTSET
logging = {
  'level': DEBUG,
  'format': '%(asctime)s %(levelname)s - %(name)s - %(message)s',
  'filename': None # '/var/log/freepy/freepy.log'
}

# A list of services to register with the router.
services = [
  {
    'name': 'FreeSWITCH Event Socket Service',
    'messages': [
      'services.freeswitch.commands.ACLCheckCommand',
      'services.freeswitch.commands.AnswerCommand',
      'services.freeswitch.commands.BreakCommand',
      'services.freeswitch.commands.BridgeCommand',
      'services.freeswitch.commands.BroadcastCommand',
      'services.freeswitch.commands.ChatCommand',
      'services.freeswitch.commands.CheckUserGroupCommand',
      'services.freeswitch.commands.DeflectCommand',
      'services.freeswitch.commands.DialedExtensionHupAllCommand',
      'services.freeswitch.commands.DisableMediaCommand',
      'services.freeswitch.commands.DisableVerboseEventsCommand',
      'services.freeswitch.commands.DisplayCommand',
      'services.freeswitch.commands.DomainExistsCommand',
      'services.freeswitch.commands.DualTransferCommand',
      'services.freeswitch.commands.DumpCommand',
      'services.freeswitch.commands.EarlyOkayCommand',
      'services.freeswitch.commands.EnableMediaCommand',
      'services.freeswitch.commands.EnableSessionHeartbeatCommand',
      'services.freeswitch.commands.EnableVerboseEventsCommand',
      'services.freeswitch.commands.FileManagerCommand',
      'services.freeswitch.commands.FlushDTMFCommand',
      'services.freeswitch.commands.GetAudioLevelCommand',
      'services.freeswitch.commands.GetBugListCommand',
      'services.freeswitch.commands.GetDefaultDTMFDurationCommand',
      'services.freeswitch.commands.GetGlobalVariableCommand',
      'services.freeswitch.commands.GetMaxSessionsCommand',
      'services.freeswitch.commands.GetMaximumDTMFDurationCommand',
      'services.freeswitch.commands.GetMinimumDTMFDurationCommand',
      'services.freeswitch.commands.GetSessionsPerSecondCommand',
      'services.freeswitch.commands.GetVariableCommand',
      'services.freeswitch.commands.GetGroupCallBridgeStringCommand',
      'services.freeswitch.commands.HoldCommand',
      'services.freeswitch.commands.HupAllCommand',
      'services.freeswitch.commands.KillCommand',
      'services.freeswitch.commands.LimitCommand',
      'services.freeswitch.commands.LoadModuleCommand',
      'services.freeswitch.commands.MaskRecordingCommand',
      'services.freeswitch.commands.OriginateCommand',
      'services.freeswitch.commands.ParkCommand',
      'services.freeswitch.commands.PauseCommand',
      'services.freeswitch.commands.PauseSessionCreationCommand',
      'services.freeswitch.commands.PreAnswerCommand',
      'services.freeswitch.commands.PreProcessCommand',
      'services.freeswitch.commands.ReceiveDTMFCommand',
      'services.freeswitch.commands.ReclaimMemoryCommand',
      'services.freeswitch.commands.RenegotiateMediaCommand',
      'services.freeswitch.commands.ResumeSessionCreationCommand',
      'services.freeswitch.commands.SendDTMFCommand',
      'services.freeswitch.commands.SendInfoCommand',
      'services.freeswitch.commands.SetAudioLevelCommand',
      'services.freeswitch.commands.SetDefaultDTMFDurationCommand',
      'services.freeswitch.commands.SetGlobalVariableCommand',
      'services.freeswitch.commands.SetMaximumDTMFDurationCommand',
      'services.freeswitch.commands.SetMinimumDTMFDurationCommand',
      'services.freeswitch.commands.SetMultipleVariableCommand',
      'services.freeswitch.commands.SetSessionsPerSecondCommand',
      'services.freeswitch.commands.SetVariableCommand',
      'services.freeswitch.commands.ShutdownCommand',
      'services.freeswitch.commands.SimplifyCommand',
      'services.freeswitch.commands.StartDebugMediaCommand',
      'services.freeswitch.commands.StartDisplaceCommand',
      'services.freeswitch.commands.StartRecordingCommand',
      'services.freeswitch.commands.StatusCommand',
      'services.freeswitch.commands.StopDebugMediaCommand',
      'services.freeswitch.commands.StopDisplaceCommand',
      'services.freeswitch.commands.StopRecordingCommand',
      'services.freeswitch.commands.SyncClockCommand',
      'services.freeswitch.commands.SyncClockWhenIdleCommand',
      'services.freeswitch.commands.TransferCommand',
      'services.freeswitch.commands.UnholdCommand',
      'services.freeswitch.commands.UnloadModuleCommand',
      'services.freeswitch.commands.UnmaskRecordingCommand',
      'services.freeswitch.commands.UnpauseCommand',
      'services.freeswitch.commands.UnsetVariableCommand'
    ],
    'target': 'services.freeswitch.EventSocketDispatcher'
  },
  {
    'name': 'HTTP Service',
    'messages': [],
    'target': 'services.http.HttpDispatcher'
  },
  {
    'name': 'Timer Service',
    'messages': [
      'lib.timer.ReceiveTimeoutCommand',
      'lib.timer.StopTimeoutCommand'
    ],
    'target': 'lib.timer.TimerService'
  }
]
