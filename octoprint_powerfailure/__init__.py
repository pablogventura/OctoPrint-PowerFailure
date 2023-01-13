# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.util import RepeatedTimer
import io
import os
import re
import json
from .misc import reverse_readlines, sanitize_number


class PowerFailurePlugin(octoprint.plugin.TemplatePlugin,
                         octoprint.plugin.EventHandlerPlugin,
                         octoprint.plugin.StartupPlugin,
                         octoprint.plugin.SettingsPlugin):

    def __init__(self):
        super(PowerFailurePlugin, self).__init__()
        self.will_print = ""
        self.datafolder = None
        self.datafile = "powerfailure_recovery.json"
        self.recovery_path = None
        #various things we can track while watching the queue
        self.extrusion = None
        self.last_fan = None
        self.linear_advance = None
        self.last_tool = None

        self.recovery_settings = {
            "bedT": 0,
            "tool0T": 0,
            "filepos": 0,
            "filename": None,
            "currentZ": 0,
            "recovery": False,
            "powerloss": False,
            "extrusion": None,
            "last_fan": None,
            "linear_advance": None
        }

    def get_settings_defaults(self):
        return dict(
            auto_continue=False,
            z_homing_height=0,
            save_frequency=1.0,

            #some settings I think will be needed, revisit
            home_z=False,
            home_z_onloss=False,
            home_z_max=300,
            prime_len=3,
            prime_retract=0.2,
            #split gcode into X segments for more control
            #1. Start/temp
            #2. XY homing
            #3. Z homing
            #4 extrusion/priming
            gcode_temp = (";M80 ; power on printer\n"
                   "M140 S{bedT}\n"
                   "M104 S{tool0T}\n"
                   "M190 S{bedT}\n"
                   "M109 S{tool0T}\n"),
            gcode_xy = ("G21 ;metric values\n"
                   "G90 ;absolute positioning\n"
                   "G28 X0 Y0 ;home X/Y to min endstops\n"),
            gcode_z = ("G92 E0 Z{currentZ} ;zero the extruded length again\n"
                   ";M211 S0 ; Deactive software endstops\n"
                   "G91\n"
                   "G1 Z-{z_homing_height} F200 ; correcting Z_HOMING_HEIGHT\n"
                   "G90\n"
                   ";M211 S1 ; Activate software endstops\n"),
            gcode_prime = ("M83\n"
                    "G1 E{prime_len} F100\n"
                    "G92 E0\n"
                    "{extrusion} ;captured from gcode, M82 or M83\n"),
                   #goal is to restrict settings to just things that require user input, nothing below here qualifies
                   recovery=False,
                   filename="",
                   filepos=0,
                   currentZ=0.0,
                   bedT=0.0,
                   tool0T=0.0,
                   extrusion=None,
                   last_fan=None,
                   powerloss=False,
                   linear_advance=None,
                   
        )
        
    def initialize(self):
        self.datafolder = self.get_plugin_data_folder()
        self.recovery_path = os.path.join(self.datafolder, self.datafile)

    def _get_recovery_settings(self):
        try:
            with open (self.recovery_path, 'r') as recovery_settings:
                self.recovery_settings = json.load(recovery_settings)
        except:
            print("Raise some exception here")

    def _write_recovery_settings(self):
        settings_json = json.dumps(self.recovery_settings, indent=4)
        with open(self.recovery_path, "w") as settings_file:
            settings_file.write(settings_json)
        settings_file.close()

    def on_after_startup(self):
        #populate our local settings from json file, remove this after testing complete
        self._get_recovery_settings()
        self.check_recovery()

    def check_recovery(self):
        self._get_recovery_settings()
        rs = self.recovery_settings
        if rs["recovery"]:
            self._logger.info("Recovering from a power failure")
            recovery_fn = self.generateContinuation()
            self.clean()
            if self._settings.getBoolean(["auto_continue"]):
                self.will_print = recovery_fn

            self._printer.select_file(
                recovery_fn, False, printAfterSelect=False)  # selecciona directo
            self._logger.info("Recovered from a power failure")
        else:
            self._logger.info("There was no power failure.")

    def generateContinuation(self):
        #establish all locals
        rs = self.recovery_settings
        filename = rs["filename"]
        filepos = rs["filepos"]
        currentZ = rs["currentZ"]
        bedT = rs["bedT"]
        tool0T = rs["tool0T"]
        extrusion = rs["extrusion"]
        linear_advance = rs["linear_advance"]
        last_fan = rs["last_fan"]

        z_homing_height = self._settings.getFloat(["z_homing_height"])
        prime_len = self._settings.getFloat(["prime_len"])
        currentZ += z_homing_height

        gcode_temp = self._settings.get(["gcode_temp"]).format(**locals())
        gcode_xy = self._settings.get(["gcode_xy"]).format(**locals())
        gcode_z = self._settings.get(["gcode_z"]).format(**locals())
        gcode_prime = self._settings.get(["gcode_prime"]).format(**locals())

        original_fn = self._file_manager.path_on_disk("local", filename)
        path, filename = os.path.split(original_fn)
        recovery_fn = self._file_manager.path_on_disk(
            "local", os.path.join(path, "recovery_" + filename))
        fan = False
        extruder = False

        #this searches back from our terminated position to find fan and extrusion distance.
        #This way works, but it may make more sense to track the things we want (fan, extrusion,  other) from the queue
        #and write those to our recovery settings. Saves the file operation and only writes a bit more data
        #on each save cycle.
        for line in reverse_readlines(original_fn, filepos):
            # buscando las ultimas lineas importantes
            if not fan and (line.startswith("M106") or line.startswith("M107")):
                fan = True  # encontre el fan
                gcode_prime += line + "\n"
            if not extruder and (line.startswith("G1 ") or line.startswith("G92 ")) and ("E" in line):
                # G1 X135.248 Y122.666 E4.03755
                extruder = True  # encontre el extruder
                subcommands = line.split()  # dividido por espacios
                ecommand = [sc for sc in subcommands if "E" in sc]
                assert len(ecommand) == 1
                ecommand = ecommand[0]
                #only need to set E distance if we are in absolute extrusion mode
                if extrusion == "M82":
                    gcode_prime += "G92 " + ecommand + "\n"
            if fan and extruder:
                break
        
        original = open(original_fn, 'r')
        original.seek(filepos)
        data = gcode_temp + gcode_xy + gcode_z + gcode_prime + original.read()
        data = data.encode()
        original.close()

        stream = octoprint.filemanager.util.StreamWrapper(
            recovery_fn, io.BytesIO(data))
        self._file_manager.add_file(
            octoprint.filemanager.FileDestinations.LOCAL, recovery_fn, stream, allow_overwrite=True)

        return os.path.join(path, "recovery_" + filename)

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    def backupState(self):
        currentData = self._printer.get_current_data()
        '''
        #This breaks something on connection,comment out for now
        if currentData["job"]["file"]["origin"] != "local":
            self._logger.info(
                "SD printing does not support power failure recovery")
            self._settings.setBoolean(["recovery"], False)
            self.timer.cancel()
            return
        '''
        #Can sometimes get errors if this gets called and values have not been set yet
        #Can likely be fixed by setting timer runfirst=False
        currentTemp = self._printer.get_current_temperatures()
        bedT = currentTemp["bed"]["target"]
        tool0T = currentTemp["tool0"]["target"]
        filepos = currentData["progress"]["filepos"]
        filename = currentData["job"]["file"]["path"]
        currentZ = currentData["currentZ"]

        #self._logger.info("Backup printing: %s Offset:%s Z:%s Bed:%s Tool:%s" % (
        #    filename, filepos, currentZ, bedT, tool0T))

        self.recovery_settings = {
            "bedT": bedT,
            "tool0T": tool0T,
            "filepos": filepos,
            "filename": filename,
            "currentZ": currentZ,
            "recovery": True,
            "powerloss": True,
            "extrusion": self.extrusion,
            "last_fan": self.last_fan,
            "linear_advance": self.linear_advance
        }

        self._write_recovery_settings()

    def clean(self):
        self.recovery_settings["recovery"] = False
        self.recovery_settings["powerloss"] = False
        self.recovery_settings["extrusion"] = None
        self.recovery_settings["last_fan"] = None
        self.recovery_settings["linear_advance"] = None
        self._write_recovery_settings()

    #Timer diagnostic stuff, remove later
    def _timer_cancel(self):
         self._logger.info("Timer cancelled")

    def _timer_finish(self):
        self._logger.info("Timer finished")

    def _timer_condition(self):
        self._logger.info("Timer condition met")

    def on_event(self, event, payload):
        if self.will_print and self._printer.is_ready():
            will_print, self.will_print = self.will_print, ""
            # larga imprimiendo directamente
            self._printer.select_file(will_print, False, printAfterSelect=True)

        if event.startswith("Connected"):
            self.check_recovery()

        if event.startswith("Print"):
            if event in {"PrintStarted"}:  # empiezo a revisar
                # empiezo a chequear
                self.timer = RepeatedTimer(self._settings.getFloat(["save_frequency"]), PowerFailurePlugin.backupState,
                                           args=[self],
                                           on_condition_false=PowerFailurePlugin._timer_condition(self),
                                           on_cancelled=PowerFailurePlugin._timer_cancel(self),
                                           on_finish=PowerFailurePlugin._timer_finish(self),
                                           run_first=True,
                                           daemon=True)
                self.timer.start()
                self._logger.info("Timer started")
            # casos en que dejo de revisar y borro
            elif event in {"PrintDone", "PrintCancelled"}:
                # cancelo el chequeo
                self.timer.cancel()
                self.clean()
            elif event in {"PrintFailed"}:
                self.timer.cancel()
                self._logger.info("PowerFailure: Print failed with {0}".format(payload["reason"]))
                self.recovery_settings["powerloss"] = False
                self._write_recovery_settings()
                
            else:
                # casos pause y resume
                pass
        #Printer disconnects throws error event, this is not working as expected yet
        if event.startswith("Error"):
            self.timer.cancel()
            self.recovery_settings["powerloss"] = False
            self._write_recovery_settings()

    def check_queue(self, comm_instance, phase, cmd, cmd_type, gcode, tags, *args, **kwargs):
        if not self._printer.is_printing():
            return cmd

        #Parse gcode to find any important things that will be needed

        if cmd == "M82":
            self.extrusion = "M82"
            
        if cmd == "M83":
            self.extrusion = "M83"
            
        if cmd.startswith("M106"):
            self.last_fan = cmd
            
        if cmd.startswith("M900"):
            self.linear_advance = cmd
            

    def get_update_information(self):
        return dict(
            powerfailure=dict(
                displayName=self._plugin_name,
                displayVersion=self._plugin_version,

                type="github_release",
                current=self._plugin_version,
                user="pablogventura",
                repo="Octoprint-PowerFailure",

                pip="https://github.com/pablogventura/OctoPrint-PowerFailure/archive/{target_version}.zip"
            )
        )


__plugin_name__ = "Power Failure Recovery"
__plugin_identifier = "powerfailure"
__plugin_pythoncompat__ = ">=2.7,<4"
__plugin_version__ = "1.0.7"
__plugin_description__ = "Recovers a print after a power failure."
__plugin_implementation__ = PowerFailurePlugin()

__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.check_queue
}
