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

from config import DB_CONNECTION_DEFAULTS
from freepy.lib.application import Actor
from freepy.lib.server import ServerInitEvent

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
        self._load_db_session(database)
    except Exception as e:
      self._logger.critical(
        'There was an error initializing the SQL Alchemy service.'
      )
      self._logger.exception(e)

  @staticmethod
  def _has_required_fields(database):
    has_url = 'url' in database
    has_urls = 'urls' in database
    has_name = 'name' in database

    return has_name and (has_url or has_urls)

  def _load_db_session(self, database):
    if not self._has_required_fields(database):
      return None

    use_orm = database.get('orm', False)

    connections = DB_CONNECTION_DEFAULTS.copy()
    connections.update(database.get('connections', {}))

    max_overflow = connections['max_overflow']
    pool_size = connections['pool_size']
    timeout = connections['timeout']

    try:
      # database has multiple URLs
      self._load_multi_bind_db_session(
        database, max_overflow, pool_size, timeout, use_orm)

    except KeyError:
      # database has single URL
      self._load_single_bind_db_session(
        database, max_overflow, pool_size, timeout, use_orm)

    self._logger.info('Loaded {} database resource'.format(database['name']))

  def _load_single_bind_db_session(self, database, max_overflow, pool_size,
                                   timeout, use_orm):
    engine = self._get_engine(
      max_overflow, pool_size, timeout, database['url'])
    self._engines[database['name']] = engine
    if use_orm is True:
      self._add_single_db_session_to_context(database['name'], engine)

  def _load_multi_bind_db_session(self, database, max_overflow, pool_size,
                                  timeout, use_orm):
    binds = []
    for url_key in database['urls'].keys():
      url = database['urls'][url_key]
      binds.append(url)
      engine = self._get_engine(
        max_overflow, pool_size, timeout, url)
      self._engines[url_key] = engine
    if use_orm is True:
      self._add_multi_db_session_to_context(database['name'], binds)

  def _add_single_db_session_to_context(self, db_name, engine):
    session_maker = sessionmaker()
    session_maker.configure(bind=engine)
    self._session_makers[db_name] = session_maker

  def _add_multi_db_session_to_context(self, db_name, binds):
    session_maker = sessionmaker()
    session_maker.configure(binds=binds)
    self._session_makers[db_name] = session_maker

  @staticmethod
  def _get_engine(max_overflow, pool_size, timeout, url):
    if 'sqlite' in url:
      engine = create_engine(
        url,
        connect_args={
          'check_same_thread': False
        },
        poolclass=StaticPool
      )
    else:
      engine = create_engine(
        url,
        max_overflow=max_overflow,
        pool_size=pool_size,
        pool_timeout=timeout
      )
    return engine

  def _stop(self):
    for engine in self._engines.values():
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
    self._name = name
    self._observer = observer

  def name(self):
    return self._name

  def observer(self):
    return self._observer

class FetchEngineResponse(object):
  def __init__(self, engine):
    self._engine = engine

  def engine(self):
    return self._engine

class FetchObjectRelationalMapperRequest(object):
  def __init__(self, name, observer):
    self._name = name
    self._observer = observer

  def name(self):
    return self._name

  def observer(self):
    return self._observer

class FetchObjectRelationalMapperResponse(object):
  def __init__(self, session_maker):
    self._session_maker = session_maker

  def session_maker(self):
    return self._session_maker
