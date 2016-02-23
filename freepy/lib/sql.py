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
from freepy.lib.server import RouteMessageCommand, ServerInitEvent

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import logging
from freepy import settings

class SQLAlchemyService(Actor):
  def __init__(self, *args, **kwargs):
    super(SQLAlchemyService, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('lib.sql.SQLAlchemyService')
    self.__engines__ = {}
    self.__session_makers__ = {}
    self.__start__()

  def __fetch_engine__(self, message):
    message.observer().tell(FetchEngineResponse(
      self.__engines__.get(message.name())
      )
    )

  def __fetch_object_relational_mapper__(self, message):
    message.observer().tell(
      FetchObjectRelationalMapperResponse(
        self.__session_makers__.get(message.name())
      )
    )

  def __start__(self):
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
            engine = create_engine(url)
          else:
            engine = create_engine(
              url,
              max_overflow = max_overflow,
              pool_size = pool_size,
              pool_timeout = timeout
            )
          self.__engines__.update({
            database.get('name'): engine
          })
          orm = database.get('orm')
          if orm is not None and orm == True:
            session_maker = sessionmaker()
            session_maker.configure(bind = engine)
            self.__session_makers__.update({
              database.get('name'): session_maker
            })
          self.__logger__.info('Loaded %s database resource' % \
                               database.get('name'))
    except Exception as e:
      self.__logger__.critical(
        'There was an error initializing the SQL Alchemy service.'
      )
      self.__logger__.exception(e)

  def __stop__(self):
    for name, engine in self.__engines__.iteritems():
      engine.dispose()

  def receive(self, message):
    if isinstance(message, FetchEngineRequest):
      self.__fetch_engine__(message)
    elif isinstance(message, FetchObjectRelationalMapperRequest):
      self.__fetch_object_relational_mapper__(message)
    elif isinstance(message, ServerInitEvent):
      self.__server__ = message.server()

class FetchEngineRequest(object):
  def __init__(self, name, observer):
    self.__name__ = name
    self.__observer__ = observer

  def name(self):
    return self.__name__

  def observer(self):
    return self.__observer__

class FetchEngineResponse(object):
  def __init__(self, engine):
    self.__engine__ = engine

  def engine(self):
    return self.__engine__

class FetchObjectRelationalMapperRequest(object):
  def __init__(self, name, observer):
    self.__name__ = name
    self.__observer__ = observer

  def name(self):
    return self.__name__

  def observer(self):
    return self.__observer__

class FetchObjectRelationalMapperResponse(object):
  def __init__(self, session_maker):
    self.__session_maker__ = session_maker

  def session_maker(self):
    return self.__session_maker__
