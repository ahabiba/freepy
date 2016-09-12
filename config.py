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

# Concurrency settings.
concurrency = {
  'threads': {
    # 'pool_size': 4
  }
}

# The SQL Alchemy service configuration.
databases = [
  {
    'name': 'telerest',
    'url': 'postgresql://bettervoice:bettervoice@127.0.0.1:5432/telerest',
    'orm': True,
    'connections': {
      'max_overflow': -1,
      'pool_size': 25,
      'timeout': 30
    }
  }
]

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

# The SMTP server configuration.
# WIP
smtp = {
  'port': 25,
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
    'name': 'SQL Alchemy Object Relational Mapper Service',
    'messages': [
      'freepy.lib.sql.FetchEngineRequest',
      'freepy.lib.sql.FetchObjectRelationalMapperRequest'
    ],
    'target': 'freepy.lib.sql.SQLAlchemyService'
  },
  {
    'name': 'Timer Service',
    'messages': [
      'freepy.lib.timer.ReceiveTimeoutCommand',
      'freepy.lib.timer.StopTimeoutCommand'
    ],
    'target': 'freepy.lib.timer.TimerService'
  },
  {
    'name': 'FreeSWITCH Event Socket Service',
    'messages': [
      'freepy.services.freeswitch.EventSocketWatchCommand',
      'freepy.services.freeswitch.EventSocketUnwatchCommand',
      'freepy.services.freeswitch.commands.ACLCheckCommand',
      'freepy.services.freeswitch.commands.AnswerCommand',
      'freepy.services.freeswitch.commands.BreakCommand',
      'freepy.services.freeswitch.commands.BridgeCommand',
      'freepy.services.freeswitch.commands.BroadcastCommand',
      'freepy.services.freeswitch.commands.ChatCommand',
      'freepy.services.freeswitch.commands.CheckUserGroupCommand',
      'freepy.services.freeswitch.commands.DeflectCommand',
      'freepy.services.freeswitch.commands.DialedExtensionHupAllCommand',
      'freepy.services.freeswitch.commands.DisableMediaCommand',
      'freepy.services.freeswitch.commands.DisableVerboseEventsCommand',
      'freepy.services.freeswitch.commands.DisplayCommand',
      'freepy.services.freeswitch.commands.DomainExistsCommand',
      'freepy.services.freeswitch.commands.DualTransferCommand',
      'freepy.services.freeswitch.commands.DumpCommand',
      'freepy.services.freeswitch.commands.EarlyOkayCommand',
      'freepy.services.freeswitch.commands.EnableMediaCommand',
      'freepy.services.freeswitch.commands.EnableSessionHeartbeatCommand',
      'freepy.services.freeswitch.commands.EnableVerboseEventsCommand',
      'freepy.services.freeswitch.commands.FileManagerCommand',
      'freepy.services.freeswitch.commands.FlushDTMFCommand',
      'freepy.services.freeswitch.commands.GetAudioLevelCommand',
      'freepy.services.freeswitch.commands.GetBugListCommand',
      'freepy.services.freeswitch.commands.GetDefaultDTMFDurationCommand',
      'freepy.services.freeswitch.commands.GetGlobalVariableCommand',
      'freepy.services.freeswitch.commands.GetMaxSessionsCommand',
      'freepy.services.freeswitch.commands.GetMaximumDTMFDurationCommand',
      'freepy.services.freeswitch.commands.GetMinimumDTMFDurationCommand',
      'freepy.services.freeswitch.commands.GetSessionsPerSecondCommand',
      'freepy.services.freeswitch.commands.GetVariableCommand',
      'freepy.services.freeswitch.commands.GetGroupCallBridgeStringCommand',
      'freepy.services.freeswitch.commands.HoldCommand',
      'freepy.services.freeswitch.commands.HupAllCommand',
      'freepy.services.freeswitch.commands.KillCommand',
      'freepy.services.freeswitch.commands.LimitCommand',
      'freepy.services.freeswitch.commands.LoadModuleCommand',
      'freepy.services.freeswitch.commands.MaskRecordingCommand',
      'freepy.services.freeswitch.commands.OriginateCommand',
      'freepy.services.freeswitch.commands.ParkCommand',
      'freepy.services.freeswitch.commands.PauseCommand',
      'freepy.services.freeswitch.commands.PauseSessionCreationCommand',
      'freepy.services.freeswitch.commands.PreAnswerCommand',
      'freepy.services.freeswitch.commands.PreProcessCommand',
      'freepy.services.freeswitch.commands.ReceiveDTMFCommand',
      'freepy.services.freeswitch.commands.ReclaimMemoryCommand',
      'freepy.services.freeswitch.commands.RenegotiateMediaCommand',
      'freepy.services.freeswitch.commands.ResumeSessionCreationCommand',
      'freepy.services.freeswitch.commands.SendDTMFCommand',
      'freepy.services.freeswitch.commands.SendInfoCommand',
      'freepy.services.freeswitch.commands.SetAudioLevelCommand',
      'freepy.services.freeswitch.commands.SetDefaultDTMFDurationCommand',
      'freepy.services.freeswitch.commands.SetGlobalVariableCommand',
      'freepy.services.freeswitch.commands.SetMaximumDTMFDurationCommand',
      'freepy.services.freeswitch.commands.SetMinimumDTMFDurationCommand',
      'freepy.services.freeswitch.commands.SetMultipleVariableCommand',
      'freepy.services.freeswitch.commands.SetSessionsPerSecondCommand',
      'freepy.services.freeswitch.commands.SetVariableCommand',
      'freepy.services.freeswitch.commands.ShutdownCommand',
      'freepy.services.freeswitch.commands.SimplifyCommand',
      'freepy.services.freeswitch.commands.SmppSendCommand',
      'freepy.services.freeswitch.commands.StartDebugMediaCommand',
      'freepy.services.freeswitch.commands.StartDisplaceCommand',
      'freepy.services.freeswitch.commands.StartRecordingCommand',
      'freepy.services.freeswitch.commands.StatusCommand',
      'freepy.services.freeswitch.commands.StopDebugMediaCommand',
      'freepy.services.freeswitch.commands.StopDisplaceCommand',
      'freepy.services.freeswitch.commands.StopRecordingCommand',
      'freepy.services.freeswitch.commands.SyncClockCommand',
      'freepy.services.freeswitch.commands.SyncClockWhenIdleCommand',
      'freepy.services.freeswitch.commands.TransferCommand',
      'freepy.services.freeswitch.commands.UnholdCommand',
      'freepy.services.freeswitch.commands.UnloadModuleCommand',
      'freepy.services.freeswitch.commands.UnmaskRecordingCommand',
      'freepy.services.freeswitch.commands.UnpauseCommand',
      'freepy.services.freeswitch.commands.UnsetVariableCommand'
    ],
    'target': 'freepy.services.freeswitch.EventSocketDispatcher'
  },
  {
    'name': 'HTTP Service',
    'messages': [],
    'target': 'freepy.services.http.HttpDispatcher'
  },
  # not sure about this? we will see
  {
    'name': 'SMTP Service',
    'messages': [],
    'target': 'freepy.services.smtp.SmtpDispatcher'
  }
]
