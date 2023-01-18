# OctoPrint Power Failure Recovery

This plugin attempts to recover a print after a power failure or printer disconnect. Tracking printed lines during the course of a print, it can then create a recovery gcode file based on the known commands that have printed. Like any recovery operation, it is intended as a last resort and does not replace the use of proper power backup and appropriate communication setup. Because the printer buffers some commands, it is certain that some commands will be lost. The results of a recovered print will vary depending on printer, material, and in some cases, plain old luck.  Recovered parts are certain to show small defects, but this may be acceptable in some cases. **To be clear: RESULTS WILL VARY AND NO GUARANTEES ARE MADE**

## Settings Configuration
* By default, when there is a power failure the plugin generates the gcode and selects the recovery file once the printer is reconnected. In the setup menu, you can select to continue printing automatically after power is restored and the connection to the printer is established. If you want the printer to recover without any intervention, you can use the Portlister plugin along with the automatic recovery feature.
* The `Save Frequency` setting determines how often the plugin will write the current state information to disk in seconds. Lower values (0.3-0.5) provide greater accuracy at the expense of a greater number of disk writes. Larger values risk missing a greater number of commands.
* **Critical: Determine if your printer has Z_HOMING_HEIGHT set.** This setting raises the Z-axis on any homing event to avoid collisions. You can check your printer firmware configuration or in a resting state issue the command `G28 X0 Y0` in the command terminal and observe if the Z-axis is raised, and by how much. This value is used for Z_HOMING_HEIGHT.
* Klipper firmware. You must have the `[force_move]` section with the `enable_force_move=true` option in your Klipper configuration. Check the appropriate box in the settings. If `[safe_z_home]` is set, use the `z_hop` value as Z_HOMING_HEIGHT.
* For slightly more advanced configurations, you can directly modify the injected Gcode before restarting printing in the plugin configuration. Defaults are based on established Marlin Gcode. All values in curly braces ({}) in the Gcode blocks are local variables that are populated by the plugin. Typically you do not want to remove these.
* For printers that turn Z-axis motors off after some time out, it may benefit to check the `Enable Z before XY` setting. This makes a small Z movement before doing the XY homing step to prevent any movement that might result from homing.
* Simliarly, if the Z-axis has a consistent amount of sag when the motors are disabled, this can be corrected by putting this value in for the `Sagging Z value` setting. You will have to determine this value experimentally.

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/pablogventura/OctoPrint-PowerFailure/archive/master.zip
