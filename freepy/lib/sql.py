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
from sqlalchemy.pool import StaticPool

from freepy.lib.application import Actor
from freepy.lib.server import RouteMessageCommand, ServerInitEvent

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import logging
from freepy import settings

class SQLAlchemyService(Actor):
  def __init__(self, *args, **kwargs):
    super(SQLAlchemyService, self).__init__(*args, **kwargs)
    self._logger = logging.getLogger('lib.sql.SQLAlchemyService')
    self._engines = {}
    self._session_makers = {}
    self._start()

  def _fetch_engine(self, message):
    message.observer().tell(FetchEngineResponse(
      self._engines.get(message.name())
      )
    )

  def _fetch_object_relational_mapper(self, message):
    message.observer().tell(
      FetchObjectRelationalMapperResponse(
        self._session_makers.get(message.name())
      )
    )

  def _start(self):
    try:
      for database in settings.databases:
        if database.has_key('name') and database.has_key('url'):
          connections = database.get('connections')
          if connections is not None:
            max_overflow = connections.get('max_overflow', 10)
            pool_size = connections.get('pool_size', 5)
            timeout = connections.get('timeout', 30)
          else:
            max_overflow = 10
            pool_size = 20
            timeout = 30
          url = database.get('url')
          if 'sqlite' in url:
            engine = create_engine(
              url,
              connect_args = {
               'check_same_thread': False
              },
              poolclass = StaticPool
            )
          else:
            engine = create_engine(
              url,
              max_overflow = max_overflow,
              pool_size = pool_size,
              pool_timeout = timeout
            )
          self._engines.update({
            database.get('name'): engine
          })
          orm = database.get('orm')
          if orm is not None and orm == True:
            session_maker = sessionmaker()
            session_maker.configure(bind = engine)
            self._session_makers.update({
              database.get('name'): session_maker
            })
          self._logger.info('Loaded %s database resource' % \
                            database.get('name'))
    except Exception as e:
      self._logger.critical(
        'There was an error initializing the SQL Alchemy service.'
      )
      self._logger.exception(e)

  def __stop__(self):
    for name, engine in self._engines.iteritems():
      engine.dispose()

  def receive(self, message):
    if isinstance(message, FetchEngineRequest):
      self._fetch_engine(message)
    elif isinstance(message, FetchObjectRelationalMapperRequest):
      self._fetch_object_relational_mapper(message)
    elif isinstance(message, ServerInitEvent):
      self._server = message.server()

class FetchEngineRequest(object):
  def __init__(self, name, observer):
    self.name = name
    self.observer = observer

class FetchEngineResponse(object):
  def __init__(self, engine):
    self.engine = engine

class FetchObjectRelationalMapperRequest(object):
  def __init__(self, name, observer):
    self.name = name
    self.observer = observer

class FetchObjectRelationalMapperResponse(object):
  def __init__(self, session_maker):
    self._session_maker = session_maker

  def session_maker(self):
    return self._session_maker
