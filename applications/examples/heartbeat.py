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

from freepy.lib.actors.actor import Actor
from freepy.lib.server import ServerInfoEvent
from freepy.services.http import HttpRequestEvent
from freepy.services.freeswitch import EventSocketEvent
from utils import *

import json
import logging

class Monitor(Actor):
  def __init__(self, *args, **kwargs):
    super(Monitor, self).__init__(*args, **kwargs)
    self._logger = logging.getLogger('examples.heartbeat.Monitor')
    self._info = [{
      'Status': 'Waiting on Heartbeat',
      'Idle-CPU': 100,
      'Session-Count': 0,
      'Event-Date-Local': '',
      'Session-Peak-FiveMin': 0,
      'Session-Peak-Max': 0
    }]

  def receive(self, message):
    if isinstance(message, EventSocketEvent):
      self._info = [message.headers()]
    elif isinstance(message, HttpRequestEvent):
      request = message.request()
      if request.method == 'GET':          
        # POST Data to Google Spreadsheet via Sheetsu.com. Get the Sheetsu URL from the post_url arg
        if request.args.get("post_url") and not self._info[0].get('Status') and not self._info[0].get("Saved"):
          from twisted.web.client import Agent
          from twisted.internet import reactor
          from twisted.web.http_headers import Headers

          data_to_post = {
            "Timestamp": self._info[0]['Event-Date-Local'],
            "CPU": (100 - float(self._info[0]['Idle-CPU'])),
            "Sessions": self._info[0]['Session-Count'],
            "Sessions 5-Min": self._info[0]['Session-Peak-FiveMin'],
            "Sessions Peak": self._info[0]['Session-Peak-Max'],
          }

          agent = Agent(reactor)
          def callback(response):
            if response.code == 201:
              self._logger.info('Spreadsheet Data Saved to: %s' % (request.args.get("post_url")[0]))
          def callback_error_handler(failure):
            self._logger.warn(failure.getErrorMessage())
          
          # Execute the request.
          headers = {
            "Content-type": ["application/json"],
          }
          deferred = agent.request('POST', request.args.get("post_url")[0], Headers(headers), StringProducer(json.dumps(data_to_post)))
          deferred.addCallback(callback)
          deferred.addErrback(callback_error_handler)
          self._info[0]['Saved'] = True

        request.setResponseCode(200)

        #Fetch timeseries data from a google spreadsheet if a public url is provided
        google_spreadsheet_url = request.args.get("spreadsheet_url")
        timeseries_js = ''
        if google_spreadsheet_url:
          google_spreadsheet_url = google_spreadsheet_url[0]
          timeseries_js = '''
          var opts = {sendMethod: 'auto'};
          var query = new google.visualization.Query('%s?headers=1range=B2:B,C2:C&gid=0&pub=1', opts);
          query.setQuery('select A, B, C');
          query.send(handleQueryResponse);
          ''' % (google_spreadsheet_url)

        responseString = '''
        <html>
          <head>
            <script type="text/javascript" src="https://www.google.com/jsapi"></script>
            <script type="text/javascript">
              google.load("visualization", "1", {packages:["corechart", "gauge"]});

              google.setOnLoadCallback(drawChart);
              function drawChart() {

                var data1 = google.visualization.arrayToDataTable([
                  ['Label', 'Value'],
                  ['CPU', %s],
                ]);
                var options1 = {
                  width: 400, height: 120,
                  redFrom: 90, redTo: 100,
                  yellowFrom:75, yellowTo: 90,
                  minorTicks: 5
                };
                var chart1 = new google.visualization.Gauge(document.getElementById('chart_div1'));
                chart1.draw(data1, options1);

                var data2 = google.visualization.arrayToDataTable([
                  ['Label', 'Value'],
                  ['Sessions', %s],
                ]);
                var options2 = {
                  width: 400, height: 120,
                  redFrom: 900, redTo: 1000,
                  yellowFrom:750, yellowTo: 900,
                  minorTicks: 5,
                  max: 1000
                };
                var chart2 = new google.visualization.Gauge(document.getElementById('chart_div2'));
                chart2.draw(data2, options2);

                drawTimeseries();
                
              }              
              setTimeout(function(){
                window.location.replace(window.location.href)
              },15000)

              function drawTimeseries() {
                %s
              }
              function handleQueryResponse(response) {
                if (response.isError()) {
                  alert('Error in query: ' + response.getMessage() + ' ' + response.getDetailedMessage());
                  return;
                }

                var data3 = response.getDataTable();

                var options3 = {
                  title: 'System Utilization',
                  width: 900,
                  legend: 'bottom'
                };

                var chart3 = new google.visualization.LineChart(document.getElementById('chart_div3'));
                chart3.draw(data3, options3);
              }

            </script>
          </head>
          <body>
            <div id="chart_div3" style="float: left; width: 1200px; height: 120px;"></div>
            <div style="clear: both;"></div>
            <div id="chart_div1" style="float:left; width: 120px; height: 120px; margin-left: 60px; margin-right: 20px;"></div>
            <div id="chart_div2" style="float: left; width: 120px; height: 120px; margin-right: 20px;"></div>            
            <div style="clear: both;"></div>
            <pre>%s</pre>
          </body>
        </html>
        ''' % ((100 - float(self._info[0]['Idle-CPU'])), self._info[0]['Session-Count'], timeseries_js, json.dumps(self._info, indent = 2, sort_keys = True))
        request.write(responseString)
        request.finish()
    self.stop()