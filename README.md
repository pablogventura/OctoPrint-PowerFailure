# OctoPrint-Display-ETA

Display estimated time of finish for current print (Estimated Time of Arrival). Day of finish is displayed only when current print not finish today.

![alt text](./extras/img/screenshot.png)

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/pablogventura/Octoprint-ETA/archive/master.zip

You must have the time zone configured on the host, otherwise you will see the time in UTC.
In Debian the following commands are made "sudo dpkg-reconfigure tzdata", then follow the wizard.
