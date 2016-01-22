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
#
# Lyle Pratt <lylepratt@gmail.com>

from lib.server import ServerInfoEvent
from pykka import ThreadingActor
from services.http import HttpRequestEvent
from services.freeswitch import EventSocketEvent
from utils import *

import json
import logging

class Monitor(ThreadingActor):
  def __init__(self, *args, **kwargs):
    super(Monitor, self).__init__(*args, **kwargs)
    self.__logger__ = logging.getLogger('examples.heartbeat.Monitor')
    self.__info__ = [{
      'Status': 'Waiting on Heartbeat',
      'Idle-CPU': 100,
      'Session-Count': 0,
      'Event-Date-Timestamp': '',
      'Session-Peak-FiveMin': 0,
      'Session-Peak-Max': 0
    }]

  def on_receive(self, message):
    message = message.get('body')
    if isinstance(message, EventSocketEvent):
      self.__info__ = [message.headers()]
    elif isinstance(message, HttpRequestEvent):
      request = message.request()
      if request.method == 'GET':        
        # POST Data to Google Spreadsheet via Sheetsu.com
        if request.args.get("sheetsu_url") and not self.__info__[0].get('Status') and not self.__info__[0].get("Saved"):
          from twisted.web.client import Agent
          from twisted.internet import reactor
          from twisted.web.http_headers import Headers

          data_to_post = {
            "Timestamp": self.__info__[0]['Event-Date-Timestamp'],
            "CPU Idle": self.__info__[0]['Idle-CPU'],
            "Sessions": self.__info__[0]['Session-Count'],
            "Sessions 5-Min": self.__info__[0]['Session-Peak-FiveMin'],
            "Sessions Peak": self.__info__[0]['Session-Peak-Max'],
          }

          agent = Agent(reactor)
          def callback(response):
            if response.code == 201:
              self.__logger__.info('Spreadsheet Data Saved to: %s' % (request.args.get("sheetsu_url")[0]))
          def callback_error_handler(failure):
            self.__logger__.warn(failure.getErrorMessage())          
          
          # Execute the request.
          headers = {
            "Content-type": ["application/json"],
          }
          deferred = agent.request('POST', request.args.get("sheetsu_url")[0], Headers(headers), StringProducer(json.dumps(data_to_post)))
          deferred.addCallback(callback)
          deferred.addErrback(callback_error_handler)
          self.__info__[0]['Saved'] = True

        request.setResponseCode(200)
        responseString = '''
        <html>
          <head>
           <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
           <script type="text/javascript">
              google.charts.load('current', {'packages':['gauge']});
              google.charts.setOnLoadCallback(drawChart);
              function drawChart() {

                var data = google.visualization.arrayToDataTable([
                  ['Label', 'Value'],
                  ['CPU', %s],
                ]);
                var options = {
                  width: 400, height: 120,
                  redFrom: 90, redTo: 100,
                  yellowFrom:75, yellowTo: 90,
                  minorTicks: 5
                };
                var chart = new google.visualization.Gauge(document.getElementById('chart_div1'));
                chart.draw(data, options);
                var data = google.visualization.arrayToDataTable([
                  ['Label', 'Value'],
                  ['Sessions', %s],
                ]);
                var options = {
                  width: 400, height: 120,
                  redFrom: 900, redTo: 1000,
                  yellowFrom:750, yellowTo: 900,
                  minorTicks: 5,
                  max: 1000
                };
                var chart = new google.visualization.Gauge(document.getElementById('chart_div2'));
                chart.draw(data, options);
              }
              setTimeout(function(){
                window.location.replace(window.location.href)
              },15000)
            </script>
          </head>
          <body>
            <div id="chart_div1" style="float:left; width: 120px; height: 120px; margin-right: 20px;"></div>
            <div id="chart_div2" style="float: left; width: 120px; height: 120px; margin-right: 20px;"></div>
            <div style="clear: both;"></div>
            <pre>%s</pre>
          </body>
        </html>
        ''' % ((100-float(self.__info__[0]['Idle-CPU'])), self.__info__[0]['Session-Count'], json.dumps(self.__info__, indent = 2, sort_keys = True))
        request.write(responseString)
        request.finish()