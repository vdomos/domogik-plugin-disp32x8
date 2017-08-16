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

Disp32x8 

Implements
==========

- Disp32x8

$ wget -qO- "http://hermes:40406/rest/cmd/id/49?message=Bonjour&type=scroll" 
$ wget -qO- "http://hermes:40406/rest/cmd/id/49?message=100,50,300&type=beep"

@author: domos  (domos dt vesta at gmail dt com)
@copyright: (C) 2007-2015 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import os
import traceback
import time
from datetime import datetime
import locale
import socket
import traceback

class Disp32x8Exception(Exception):
    """
    Disp32x8 exception
    """

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


class Disp32x8:
    """ Disp32x8
    """

    def __init__(self, log, stop, ip, port, getsensorvalue):
        """ Init Disp32x8 object
            @param log : log instance
            @param send : send
            @param stop : stop flag
            @param device_id : domogik device id
            @param weather_id : Weather location ID
        """
        self.log = log
        self.stop = stop
        self.displayip = ip
        self.displayport = port
        self.getsensorvalue = getsensorvalue
        self.osdmsg = ""

        self.log.info("==> Open Dips32x8 board UDP socket...")
        try:
            self.displaysocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            self.log.error("### Failed to create socket")
            self.force_leave()
            return
        self.displaysocket.settimeout(20)                   # TimeOut pour message défilant !
        self.log.info("==> Socket Dips32x8 board open.")

    # ---------------------------------------------------------------------
    def write(self, msg):
        """ 
            Write message to Disp32x8 board
        """
        self.log.debug("==> Send message to Disp32x8 board: '%s'" % msg.rstrip())
        self.displaysocket.sendto(msg, (self.displayip, self.displayport))
        try:
            resp, addr = self.displaysocket.recvfrom(1024)
            self.log.debug("==> Answer from Disp32x8 board: '%s'" % resp.rstrip())
            if "Ack" in resp:
                self.log.debug("==> Ack receive from Dips32x8 board")
            else:
                self.log.debug("### Ack error from Dips32x8 board")
        except socket.timeout:
                self.log.debug("### Timeout waiting Ack from Dips32x8 board")
        

    def close(self):
        """ 
            Close Disp32x8 UDP connexion
        """
        self.displaysocket.close()


    def displayTemp(self, id):
        """ 
            Affiche temperature int ou ext.
        """
        temp = self.getsensorvalue(id)
        if temp != "Failed":
            msg = temp + u"° *\n"
        else:
            msg = u"--.-° *\n"
        self.log.info("==> Demande affichage temp '%s'" % msg.rstrip())
        self.write(msg.encode('utf-8'))                            # Write message to the Disp32x8 board


    def displayRain(self, id):
        """ 
            Affiche pluviometrie dans l'heure.
        """
        value = self.getsensorvalue(id)
        if value != "Failed" and value != "0.0":
            msg = "%.1fM *\n" % float(value)
            self.log.info("==> Demande affichage pluviometrie '%s'" % msg.rstrip())
            self.write(msg.encode('utf-8'))                            # Write message to the Disp32x8 board
            return msg
        else:
            return ""


    def run(self, tempintsensorid, tempextsensorid, rainsensorid):
        """ 
        """        
        secondes_courantes = 60
        offset_affichage = 3
        x_affichage = 0            # x sert au decalage d'affichage.
        
        locale_fr = locale.setlocale(locale.LC_ALL, '')

        while not self.stop.isSet():
            if secondes_courantes != datetime.now().second:
                #print "==> Seconde : %d" % secondes
                secondes_courantes = datetime.now().second
                if secondes_courantes == 0:                                     # Affichage heure
                    self.log.debug(u"==> Heure: '%s'" % datetime.now().strftime("%k:%M"))
                    time.sleep(1)                                               # C'est l'Arduino qui affiche l'heure 0 seconde, tempo pour ne pas ecraser si decaloge.
                if secondes_courantes == offset_affichage * 1 :                        # Affichage TEMP_INT
                    self.displayTemp(tempintsensorid)
                if secondes_courantes == offset_affichage * 2 :                        # Affichage TEMP_EXT
                    self.displayTemp(tempextsensorid)
                if secondes_courantes == offset_affichage * 3 :                        # Affichage pluvio1h
                    if self.displayRain(rainsensorid):
                        x_affichage = offset_affichage
                    else:
                        x_affichage = 0                            # A '0' si pas d'affichage pluvio1h.
                if secondes_courantes == offset_affichage * 3 + (x_affichage) :        # Affichage heure
                    self.log.info(u"==> Réaffichage heure")
                    self.write(datetime.now().strftime("%k:%M") + "#" + "\n")          # Write message to the Disp32x8 board
                if self.osdmsg != "" :
                    self.log.info(u"==> Demande d'affichage message texte '%s'" % self.osdmsg)
                    self.write(self.osdmsg)                                          # Write message to the Disp32x8 board
                    self.osdmsg = ""
                    self.write(datetime.now().strftime("%k:%M")  + "#" + "\n")  # Write message to the Disp32x8 board
            time.sleep(0.9)

        self.displaysocket.close()

