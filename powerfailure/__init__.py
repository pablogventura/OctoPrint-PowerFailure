# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.util import RepeatedTimer
import time
import os

from .misc import reverse_readlines,sanitize_number

class PowerFailurePlugin(octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.EventHandlerPlugin,
                       octoprint.plugin.StartupPlugin,
                       octoprint.plugin.SettingsPlugin):


    def __init__(self):
        super(PowerFailurePlugin, self).__init__()
        self.will_print = ""

            
    def get_settings_defaults(self):
        return dict(
            auto_continue=False,
            z_homing_height=0,
            gcode=("M80\n"
                   "M140 S{bedT}\n"
                   "M104 S{tool0T}\n"
                   "M190 S{bedT}\n"
                   "M109 S{tool0T}\n"
                   "G21 ;metric values\n"
                   "G90 ;absolute positioning\n"
                   "G28 X0 Y0 ;move X/Y to min endstops\n"
                   "G92 E0 Z{currentZ} ;zero the extruded length again\n"
                   "M211 S0\n"
                   "G91\n"
                   "G1 Z-{z_homing_height} F200 ; correcting Z_HOMING_HEIGHT\n"
                   "G90\n"
                   "M211 S1\n"
                   "G1 F9000\n"
                  ),
            recovery=False,
            filename = "",
            filepos = 0,
            currentZ = 0.0,
            bedT = 0.0,
            tool0T = 0.0
            
        )

        
    def on_after_startup(self):

        if self._settings.getBoolean(["recovery"]):
            #hay que recuperar
            self._logger.info("Hubo un corte de luz la ultima vez")
            
            filename = self._settings.get(["filename"])
            filepos = self._settings.getInt(["filepos"])
            currentZ = self._settings.getFloat(["currentZ"])
            bedT = self._settings.getFloat(["bedT"])
            tool0T = self._settings.getFloat(["tool0T"])
            
            self._logger.info("y fue asi %s por %s en Z:%s a Bed:%s Tool:%s"%(filename,filepos,currentZ, bedT, tool0T))
            recovery_fn = self.generateContinuation(filename,filepos,currentZ, bedT, tool0T)
            self.clean()
            if self._settings.getBoolean(["auto_continue"]):
                self.will_print = recovery_fn
                self._logger.info("Autocontinue")
            else:
                self._logger.info("No Autocontinue")
            self._printer.select_file(recovery_fn, False, printAfterSelect=False) # selecciona directo
        else:
            self._logger.info("No Hubo un corte de luz la ultima vez")
    
    def generateContinuation(self,filename,filepos,currentZ, bedT, tool0T):

        z_homing_height=self._settings.getFloat(["z_homing_height"])
        currentZ += z_homing_height 
        gcode = self._settings.get(["gcode"]).format(**locals())
        
        original_fn = self._file_manager.path_on_disk("local",filename)
        recovery_fn=self._file_manager.path_on_disk("local","recovery_" + filename)
        
        fan=False
        extruder=False
        for line in reverse_readlines(original_fn, filepos):
            # buscando las ultimas lineas importantes
            if not fan and (line.startswith("M106") or line.startswith("M107")):
                fan = True # encontre el fan
                gcode += line +"\n"
            if not extruder and (line.startswith("G1 ") or line.startswith("G92 ")) and ("E" in line):
                # G1 X135.248 Y122.666 E4.03755
                extruder = True # encontre el extruder
                subcommands = line.split() # dividido por espacios
                ecommand = [sc for sc in subcommands if "E" in sc]
                assert len(ecommand)==1
                ecommand = ecommand[0]
                gcode += "G92 " + ecommand +"\n"
            if fan and extruder:
                break
        
        original = open(original_fn, 'r')
        recovery = open(recovery_fn, 'w')
        
        recovery.write(gcode)
        original.seek(filepos)
        recovery.write(original.read())
        original.close()
        recovery.close()
        return recovery_fn
    def get_template_configs(self):
        return [
            dict(type="settings",custom_bindings=False)
        ]

            
    def backupState(self):

        currentData = self._printer. get_current_data()
        currentTemp = self._printer.get_current_temperatures()
        self._logger.info(currentTemp)
        bedT=currentTemp["bed"]["target"]
        tool0T=currentTemp["tool0"]["target"]
        filepos=currentData["progress"]["filepos"]
        filename=currentData["job"]["file"]["name"]
        currentZ=currentData["currentZ"]
        self._logger.info("imprimiendo %s por %s en Z:%s a Bed:%s Tool:%s"%(filename,filepos,currentZ, bedT, tool0T))
        self._settings.setBoolean(["recovery"],True)
        self._settings.set(["filename"],str(filename))
        self._settings.setInt(["filepos"],sanitize_number(filepos))
        self._settings.setFloat(["currentZ"],sanitize_number(currentZ))
        self._settings.setFloat(["bedT"],sanitize_number(bedT))
        self._settings.setFloat(["tool0T"],sanitize_number(tool0T))
        self._settings.save()
        self._logger.info("Escrito")
        if self._settings.getBoolean(["auto_continue"]):
            self._logger.info("Autocontinue")
        else:
            self._logger.info("No Autocontinue")

    def clean(self):
        self._settings.setBoolean(["recovery"],False)
        self._settings.save()
            
    def on_event(self,event, payload):
        if self.will_print and self._printer.is_ready():
            will_print, self.will_print = self.will_print,""
            self._printer.select_file(self.will_print, False, printAfterSelect=True) # larga imprimiendo directamente
        if event.startswith("Print"):
            if event in {"PrintStarted"}: # empiezo a revisar
                # empiezo a chequear
                self.timer = RepeatedTimer(1.0, PowerFailurePlugin.backupState, args=[self], run_first=True,)
                self.timer.start()
            elif event in {"PrintDone","PrintFailed","PrintCancelled"}: # casos en que dejo de revisar y borro
                # cancelo el chequeo
                self.timer.cancel()
                self.clean()
            else:
                # casos pause y resume
                pass 
                
            

__plugin_name__ = "Power Failure Recovery"

__plugin_implementation__ = PowerFailurePlugin()
