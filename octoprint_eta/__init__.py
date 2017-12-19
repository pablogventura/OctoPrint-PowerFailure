# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.util import RepeatedTimer
import time
import os.path


class DisplayETAPlugin(octoprint.plugin.ProgressPlugin,
                       octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.AssetPlugin,
                       octoprint.plugin.EventHandlerPlugin,
                       octoprint.plugin.StartupPlugin):

    def __init__(self):
        self.timer = RepeatedTimer(5.0, DisplayETAPlugin.fromTimer, args=[self], run_first=True,)
        self.path = "/home/pi/.octoprint/uploads/"
        
    def on_after_startup(self):
        if os.path.isfile(self.path+"print_recovery"):
            #hay que recuperar
            self._logger.info("Hubo un corte de luz la ultima vez")
            f = open(self.path+'print_recovery', 'r')
            filename,filepos,currentZ,bedT,tool0T=f.readline().split()
            self._logger.info("y fue asi %s por %s en Z:%s a Bed:%s Tool:%s"%(filename,filepos,currentZ, bedT, tool0T))
            self.generateContinuation(filename,filepos,currentZ, bedT, tool0T)
        else:
            self._logger.info("No Hubo un corte de luz la ultima vez")
    
    def generateContinuation(self,filename,filepos,currentZ, bedT, tool0T):
        filepos = int(filepos)
        gcode = "M80\n"
        gcode += "M140 S%s\n" % bedT
        gcode += "M104 S%s\n" % tool0T
        gcode += "M190 S%s\n" % bedT
        gcode += "M109 S%s\n" % tool0T
        gcode += "G21 ;metric values\n"
        gcode += "G90 ;absolute positioning\n"
        gcode += "G28 X0 Y0 ;move X/Y to min endstops\n"
        gcode += "G92 E0 Z%s ;zero the extruded length again\n" % (float(currentZ)+2) # le sumo Z_HOMING_HEIGHT
        gcode += "M211 S0\n" #desactivo los software endstops
        gcode += "G1 F9000\n"
        original = open(self.path+filename, 'r')
        recovery = open(self.path+"recovery.gcode", 'w')
        recovery.write(gcode)
        original.seek(filepos)
        recovery.write(original.read())
        recovery.write("\nM211 S1\n")# reactivo los software endstops
        original.close()
        recovery.close()
        
    def fromTimer(self):
        #self.eta_string = self.calculate_ETA()
        #self._plugin_manager.send_plugin_message(self._identifier, dict(eta_string=self.eta_string))
        currentData = self._printer. get_current_data()
        currentTemp = self._printer.get_current_temperatures()
        self._logger.info(currentTemp)
        bedT=currentTemp["bed"]["target"]
        tool0T=currentTemp["tool0"]["target"]
        filepos=currentData["progress"]["filepos"]
        filename=currentData["job"]["file"]["name"]
        currentZ=currentData["currentZ"]
        self._logger.info("imprimiendo %s por %s en Z:%s a Bed:%s Tool:%s"%(filename,filepos,currentZ, bedT, tool0T))
        f = open(self.path+'print_recovery', 'w')
        f.write("%s %s %s %s %s"%(filename,filepos,currentZ, bedT, tool0T))
        f.close()
        self._logger.info("Escrito")

    def clean(self):
        try:
            os.remove(self.path+"print_recovery")
        except:
            pass
            
    def on_event(self,event, payload):
        if event.startswith("Print"):
            if event in {"PrintStarted","PrintPaused","PrintResumed"}:
                # empiezo a chequear
                self.timer = RepeatedTimer(5.0, DisplayETAPlugin.fromTimer, args=[self], run_first=True,)
                self.timer.start()
            else:
                # cancelo el chequeo
                #self.clean()
                pass
            

__plugin_name__ = "Display ETA"
__plugin_identifier = "display-eta"
__plugin_version__ = "1.0.0"
__plugin_description__ = "A quick \"Hello World\" example plugin for OctoPrint"
__plugin_implementation__ = DisplayETAPlugin()
