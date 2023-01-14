# OctoPrint Power Failure Recovery

This plugin attempts to recover a print after a power failure or printer disconnect. Tracking printed lines during the course of a print, it can then create a recovery gcode file based on the known commands that have printed. It can be configured to start the printing automatically with the return of the power supply or a printer reconnection. Like any recovery, it is intended as a last resort and does not replace the use of proper power backup and appropriate communication setup. The results of a recovered print will vary depending on printer, material, and circumstances.  Recovered parts are certain to show small defects, but this may be acceptable in some cases.

![alt text](./extras/img/settings_screenshot.png)

## Configuration

By default, when there is a power failure it generates the gcode to continue printing and only selects it, waiting for the user to continue. In the setup menu, you can select to continue printing automatically after power is restored and the connection to the printer is established.

If you use Z_HOMING_HEIGHT in the Marlin firmware (which raises the z-axis when making a home on any axis to avoid collisions) you must set the height in the plugin configuration.

For slightly more advanced configurations, you can directly modify the injected Gcode before restarting printing in the plugin configuration. Defaults are based on established Marlin Gcode.

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/pablogventura/OctoPrint-PowerFailure/archive/master.zip
