# OctoPrint Power Failure Recovery

This plugin attempts to recover a print after a power failure or printer disconnect. Tracking printed lines during the course of a print, it can then create a recovery gcode file based on the known commands that have printed. Like any recovery operation, it is intended as a last resort and does not replace the use of proper power backup and appropriate communication setup. The results of a recovered print will vary depending on printer, material, and circumstances.  Recovered parts are certain to show small defects, but this may be acceptable in some cases. **To be clear: RESULTS WILL VARY**

![alt text](./extras/img/settings_screenshot.png)

## Configuration

* By default, when there is a power failure the plugin generates the gcode to continue printing and only selects it, waiting for the user to continue. In the setup menu, you can select to continue printing automatically after power is restored and the connection to the printer is established.

* If you use Z_HOMING_HEIGHT in the Marlin firmware (which raises the z-axis when making a home on any axis to avoid collisions) you must set the height in the plugin configuration.

* For slightly more advanced configurations, you can directly modify the injected Gcode before restarting printing in the plugin configuration. Defaults are based on established Marlin Gcode.

* For use with Klipper firmware, you must have the `[force_move]` with `enable_force_move=true` in your Klipper configuration and check the appropriate box in the settings. If `[safe_z_home]` is set, use the `z_hop` value as Z_HOMING_HEIGHT.

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/pablogventura/OctoPrint-PowerFailure/archive/master.zip
