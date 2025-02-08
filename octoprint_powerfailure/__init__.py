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
                         octoprint.plugin.WizardPlugin,
                         octoprint.plugin.SettingsPlugin,
                         octoprint.plugin.RestartNeedingPlugin):

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
        #increment this value with each release
        self.wizardVersion = 2

        self.recovery_settings = {
            "bedT": 0,
            "tool0T": 0,
            "filepos": 0,
            "filename": None,
            "currentZ": 0,
            "last_X": 0,
            "last_Y": 0,
            "recovery": False,
            "powerloss": False,
            "extruder": None,
            "extrusion": None,
            "feedrate": None,
            "last_fan": None,
            "linear_advance": None
        }

        self.MOVE_RE = re.compile("^G0\s+|^G1\s+")
        self.X_COORD_RE = re.compile(r".*\s+X([-]*\d*\.*\d*)")
        self.Y_COORD_RE = re.compile(r".*\s+Y([-]*\d*\.*\d*)")
        self.E_COORD_RE = re.compile(r".*\s+E([-]*\d*\.*\d*)")
        self.SPEED_VAL_RE = re.compile(r".*\s+F(\d*\.*\d*)")


    def get_settings_defaults(self):
        return dict(
            auto_continue=False,
            z_homing_height=0,
            save_frequency=1.0,
            klipper_z=False,
            z_sag=0.0,
            xy_feed=3000,
            enable_z=False,
            #some settings I think will be needed, revisit
            home_z=False,
            home_z_onloss=False,
            home_z_max=300,
            prime_len=3,
            prime_retract=0.2,
            wizard_version = 1,
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
                    "{klipper_z}\n"
                    "{enable_z}\n"
                    "G90 ;absolute positioning\n"
                    "G28 X0 Y0 ;home X/Y to min endstops\n"),
            gcode_z = ("G92 Z{adjustedZ} ;set Z with any homing offsets\n"
                    ";M211 S0 ; Deactive software endstops\n"
                    "G91 ;relative positioning\n"
                    "G1 Z-{z_homing_height} F200 ; correcting Z_HOMING_HEIGHT\n"
                    "G90 ;absolute positioning\n"
                    ";M211 S1 ; Activate software endstops\n"),
            gcode_prime = ("M83\n"
                    "G1 E{prime_len} F100\n"
                    "G92 E0\n"
                    "{extrusion} ;captured from gcode, M82 or M83\n"
                    "G1 X{last_X} Y{last_Y} F{xy_feed}; move to last known XY\n"
                    ";fan state, extruder reset, feedrate and linear advance settings will be injected here\n"),
                   #goal is to restrict settings to just things that require user input, nothing below here qualifies
                   
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
            settings_file.flush()
            os.fsync(settings_file.fileno())
        settings_file.close()

    def check_recovery(self):
        self._logger.debug("Checking recovery")
        self._get_recovery_settings()
        rs = self.recovery_settings
        if rs["recovery"]:
            self._logger.info("Recovering from a print failure")
            recovery_fn = self.generateContinuation()
            self.clean()
            if self._settings.getBoolean(["auto_continue"]):
                self.will_print = recovery_fn

            self._printer.select_file(
                recovery_fn, False, printAfterSelect=False)  # selecciona directo
        else:
            self._logger.debug("There was no print failure.")

    def generateContinuation(self):
        #establish all locals
        rs = self.recovery_settings
        filename = rs["filename"]
        filepos = rs["filepos"]
        currentZ = rs["currentZ"]
        last_X = rs["last_X"]
        last_Y = rs["last_Y"]
        bedT = rs["bedT"]
        tool0T = rs["tool0T"]
        extruder = rs["extruder"]
        extrusion = rs["extrusion"]
        feedrate = rs["feedrate"]
        linear_advance = rs["linear_advance"]
        last_fan = rs["last_fan"]

        z_homing_height = self._settings.getFloat(["z_homing_height"])
        prime_len = self._settings.getFloat(["prime_len"])
        z_sag = self._settings.getFloat(["z_sag"])
        xy_feed = self._settings.getFloat(["xy_feed"])
        enable_z = "; Z enable is not checked\n"
        klipper_z = "; Klipper Z is not checked"

        #Create any locals that are referenced in gcode blocks
        #handle klipper which will just move to Z=z_hop if below, so find the difference 
        if (self._settings.getBoolean(["klipper_z"])):
            if (currentZ >= z_homing_height):
                z_homing_height = 0
            else:
                z_homing_height = z_homing_height - currentZ
            klipper_z = "SET_KINEMATIC_POSITION x=50 y=50 z={};\n".format(currentZ)

        if self._settings.getBoolean(["enable_z"]):
            enable_z = "G91\nG1 Z0.2 F200\nG1 Z-0.2\n"

        adjustedZ = currentZ + z_homing_height

        #Establish gcode blocks
        gcode_temp = self._settings.get(["gcode_temp"]).format(**locals())
        gcode_xy = self._settings.get(["gcode_xy"]).format(**locals())
        gcode_z = self._settings.get(["gcode_z"]).format(**locals())
        gcode_prime = self._settings.get(["gcode_prime"]).format(**locals())

        #Append modifications to our various gcodes blocks based on settings here
        #Could make these all locals, but then would have to handle None assignments.
        if last_fan:
            gcode_prime += last_fan + "\n" 
        if feedrate:
            gcode_prime += "G0 F" + str(feedrate) + "\n"
        if extrusion == "M82":
            gcode_prime += "G92 E" + str(extruder) + "\n"
        if linear_advance:
            gcode_prime += linear_advance + "\n"
        if z_sag:
            sag = "G91\nG1 Z" + str(z_sag) + " ; z_sag value\nG90\n"
            gcode_z = sag + gcode_z
 
        original_fn = self._file_manager.path_on_disk("local", filename)
        path, filename = os.path.split(original_fn)
        recovery_fn = self._file_manager.path_on_disk(
            "local", os.path.join(path, "recovery_" + filename))

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
            {
                    "type": "settings",
                    "template": "powerfailure_settings.jinja2",
                    "custom_bindings": False
            },
            {
                    "type": "wizard",
                    "name": "PowerFailure",
                    "template": "powerfailure_wizard.jinja2",
                    "custom_bindings": True
            }
        ]

    def backupState(self):
        if not self._printer.is_printing():
            return

        currentData = self._printer.get_current_data()
        '''
        #This breaks something on connection,comment out for now
        if currentData["job"]["file"]["origin"] != "local":
            self._logger.debug(
                "SD printing does not support power failure recovery")
            self._settings.setBoolean(["recovery"], False)
            self.timer.cancel()
            return
        '''
        currentTemp = self._printer.get_current_temperatures()

        try:
            rs = self.recovery_settings
            rs["bedT"] = currentTemp["bed"]["target"]
            rs["tool0T"] = currentTemp["tool0"]["target"]
            rs["filepos"] = currentData["progress"]["filepos"]
            rs["filename"] = currentData["job"]["file"]["path"]
            rs["currentZ"] = currentData["currentZ"]
            rs["recovery"] = True
            rs["powerloss"] = True
            self._write_recovery_settings()
        except:
            self._logger.debug("Keys missing exception")

    def clean(self):
        self.recovery_settings = {
            "bedT": 0,
            "tool0T": 0,
            "filepos": 0,
            "filename": None,
            "currentZ": 0,
            "last_X": 0,
            "last_Y": 0,
            "recovery": False,
            "powerloss": False,
            "extruder": None,
            "extrusion": None,
            "feedrate": None,
            "last_fan": None,
            "linear_advance": None
        }
        self._write_recovery_settings()

    #Timer diagnostic stuff, remove later
    def _timer_cancel(self):
         self._logger.debug("Timer cancelled")

    def _timer_finish(self):
        self._logger.debug("Timer finished")

    def _timer_condition(self):
        self._logger.debug("Timer condition met")

    def on_event(self, event, payload):
        if self.will_print and self._printer.is_ready():
            will_print, self.will_print = self.will_print, ""
            # larga imprimiendo directamente
            self._printer.select_file(will_print, False, printAfterSelect=True)

        if event.startswith("Connected"):
            self._logger.debug("Connected Event. Check Recovery")
            self.check_recovery()

        if event.startswith("Print"):
            if event in {"PrintStarted"}:  # empiezo a revisar
                # empiezo a chequear
                self.timer = RepeatedTimer(self._settings.getFloat(["save_frequency"]), PowerFailurePlugin.backupState,
                                           args=[self],
                                           on_condition_false=PowerFailurePlugin._timer_condition(self),
                                           on_cancelled=PowerFailurePlugin._timer_cancel(self),
                                           on_finish=PowerFailurePlugin._timer_finish(self),
                                           run_first=False,
                                           daemon=True)
                self.timer.start()
                self._logger.debug("Timer started")
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

    def hook_gcode_sending(self, comm_instance, phase, cmd, cmd_type, gcode, tags, *args, **kwargs):
        if not self._printer.is_printing():
            return cmd
        
        #Parse gcode to find any important things that will be needed
        if (cmd.startswith("G1 ") or cmd.startswith("G92 ")) and ("E" in cmd):
            m = self.E_COORD_RE.match(cmd)
            if m:
                self.recovery_settings["extruder"] = float(m.groups()[0])
        
        if (cmd.startswith("G0 ") or cmd.startswith("G1 ")):
            m = self.SPEED_VAL_RE.match(cmd)
            if m:
                self.recovery_settings["feedrate"] = float(m.groups()[0])
            
            m = self.X_COORD_RE.match(cmd)
            if m:
                self.recovery_settings["last_X"] = float(m.groups()[0])

            m = self.Y_COORD_RE.match(cmd)
            if m:
                self.recovery_settings["last_Y"] = float(m.groups()[0])
        
        if cmd == "M82":
            self.recovery_settings["extrusion"] = "M82"
           
        if cmd == "M83":
            self.recovery_settings["extrusion"] = "M83"
            
        if cmd.startswith("M106") or cmd.startswith("M107"):
            self.recovery_settings["last_fan"] = cmd
 
        if cmd.startswith("M900"):
            self.recovery_settings["linear_advance"] = cmd

        return cmd
        
    def on_wizard_finish(self, handled):
        #self._logger.debug("__init__: on_wizard_finish handled=[{}]".format(handled))
        if handled:
            self._settings.set(["wizard_version"], self.wizardVersion)
            self._settings.save()

    def is_wizard_required(self):
        requiredVersion = self.wizardVersion
        currentVersion = self._settings.get(["wizard_version"])
        #self._logger.debug("__init__: is_wizard_required=[{}]".format(currentVersion is None or currentVersion != requiredVersion))
        return currentVersion is None or currentVersion != requiredVersion

    def get_wizard_version(self):
        #self._logger.debug("__init__: get_wizard_version")
        return self.wizardVersion

    def get_wizard_details(self):
        #self._logger.debug("__init__: get_wizard_details")
        return None

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
__plugin_version__ = "1.2.1"
__plugin_description__ = "Recovers a print after a power failure."
__plugin_implementation__ = PowerFailurePlugin()

__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    "octoprint.comm.protocol.gcode.sending": __plugin_implementation__.hook_gcode_sending
}
