# OctoPrint Power Failure Recovery

Recovers a print after a power failure. This plugin generates a recovery gcode from the pre-fault offset.
It can be configured to start the printing automatically with the return of the power supply or wait to user  or wait for user intervention.

![alt text](./extras/img/settings_screenshot.png)

## Configuration

By default, when there is a power failure it generates the gcode to continue printing and only selects it, waiting for the user to continue. In the setup menu, you can select to continue printing automatically after power is restored and the connection to the printer is established.

If you use Z_HOMING_HEIGHT in the Marlin firmware (which raises the z-axis when making a home on any axis to avoid collisions) you must set the height in the plugin configuration.

For more advanced configurations, you can directly modify the injected Gcode before restarting printing in the plugin configuration.

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/pablogventura/OctoPrint-PowerFailure/archive/master.zip
