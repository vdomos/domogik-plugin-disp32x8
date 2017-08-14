#!/usr/bin/python
# -*- coding: utf-8 -*-

""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Plugin purpose
==============

Disp32x8Manager

Implements
==========

Disp32x8Manager

Info.
=====

$ wget -qO- "http://hermes:40406/rest/cmd/id/49?message=Bonjour domos&type=center"

Pour simuler l'afficheur:
# netcat -ul -p 8888

@author: domos  (domos dt vesta at gmail dt com)
@copyright: (C) 2007-2015 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

from domogik.common.plugin import Plugin
from domogikmq.message import MQMessage
from domogikmq.reqrep.client import MQSyncReq
from domogik_packages.plugin_disp32x8.lib.disp32x8 import Disp32x8, Disp32x8Exception

import threading
import json
import time
import traceback

class Disp32x8Manager(Plugin):
    """
    """

    def __init__(self):
        """ Init plugin
        """
        Plugin.__init__(self, name='disp32x8')

        # check if the plugin is configured. If not, this will stop the plugin and log an error
        # if not self.check_configured():
        #	return

        # get the devices list
        self.devices = self.get_device_list(quit_if_no_device=True)
        # self.log.info(u"==> device:   %s" % format(self.devices))

        # get the sensors id per device:
        # self.sensors = self.get_sensors(self.devices)
        # self.log.info(u"==> sensors:   %s" % format(self.sensors))	
        # INFO ==> sensors:   {66: {u'set_info_number': 159}}  ('device id': 'sensor name': 'sensor id')

        self.osdmsgtype = {"scroll": "%\n", "left": "@\n", "center": "#\n", "right": "*\n", "beep": "$\n", "time": "!\n"}
        
        # for each device ...
        for a_device in self.devices:
            # global device parameters
            device_name = a_device["name"]					# Ex.: ""
            device_id = a_device["id"]						# Ex.: ""
            displayip = self.get_parameter(a_device, "displayip")
            displayport = int(self.get_parameter(a_device, "displayport"))
            tempintsensorid = self.get_parameter(a_device, "tempintsensorid")
            tempextsensorid = self.get_parameter(a_device, "tempextsensorid")
            rainsensorid = self.get_parameter(a_device, "rainsensorid")         # id sensor flowHour pluie
            self.log.info(u"==> Device '%s' (id:%s), address: %s:%d, sensors id tempint: %d, tempext: %d, rain: %d" % 
                          (device_name, device_id, displayip, displayport, tempintsensorid, tempextsensorid, rainsensorid))
            
            self.display = Disp32x8(self.log, self.get_stop(), displayip, displayport, self.getMQValue)
            
            threads = {}
            self.log.info(u"Start to run Display loop '{0}'".format(device_name))
            thr_name = "dev_{0}".format(device_id)
            threads[thr_name] = threading.Thread(None,
                                        self.display.run,
                                        thr_name,
                                            (
                                                tempintsensorid,
                                                tempextsensorid,
                                                rainsensorid
                                            ),
                                        {})
            threads[thr_name].start()
            self.register_thread(threads[thr_name])

        self.ready()


    def getMQValue(self, id):
        """  REQ/REP message to get sensor value
        """
        mq_client = MQSyncReq(self.zmq)
        msg = MQMessage()
        msg.set_action('sensor_history.get')
        msg.add_data('sensor_id', id)
        msg.add_data('mode', 'last')
        try:
            sensor_history = mq_client.request('admin', msg.get(), timeout=10).get()  
            #self.log.info(u"==> 0MQ REQ/REP: Last sensor history: %s" % format(sensor_history))  # sensor_history est une list   ['sensor_history.result', '{"status": true, "reason": "", "sensor_id": 183, "values": [{"timestamp": 1452017810.0, "value_str": "7.0", "value_num": 7.0}], "mode": "last"}']
            sensor_last = json.loads(sensor_history[1])
            if sensor_last['status'] == True:
                sensor_timestamp = sensor_last['values'][0]['timestamp']  
                if (time.time() - sensor_timestamp) > 3600:                             # Si dernière data à moins de 60mn (60mn à cause de "duplicate = false").
                    self.log.info(u"==> Sensor '%d' value too old: %s" % (id, time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(sensor_timestamp))))
                    return "Failed"     
                sensor_value = sensor_last['values'][0]['value_str']
                self.log.info(u"==> 0MQ REP: Last sensor '%d' value: %s (%s)" % (id, sensor_value , time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(sensor_timestamp))))
                return sensor_value
            else:
                self.log.info(u"==> 0MQ REP: Last sensor '%d' status = FALSE" % id)
                return "Failed"
        except AttributeError:  # Erreur rencontrée: 'NoneType' object has no attribute 'get'
            self.log.error(u"### 0MQ REQ/REP: '%s'", format(traceback.format_exc()))
            return "Failed"
        


    def on_mdp_request(self, msg):
        """ Called when a MQ req/rep message is received
        """
        Plugin.on_mdp_request(self, msg)
        if msg.get_action() == "client.cmd":
            data = msg.get_data()
            self.log.info(u"==> Received 0MQ message data: %s" % format(data))
            # INFO ==> Received 0MQ message data: {u'message': u'Bonjour', u'command_id': 49, u'position': u'center', u'device_id': 132}
            self.display.osdmsg = data['message'] + self.osdmsgtype[data['position']]
            self.log.info(u"==> Message = '%s'" % self.display.osdmsg)

            status = True
            reason = None

            self.log.info("Reply to command 0MQ")
            reply_msg = MQMessage()
            reply_msg.set_action('client.cmd.result')
            reply_msg.add_data('status', status)
            reply_msg.add_data('reason', reason)
            self.reply(reply_msg.get())


if __name__ == "__main__":
    Disp32x8Manager()

