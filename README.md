# Temperature Control App

_Access and monitor your favorite temperature controllers from your browser._

### Supported devices

Currently, supports
- `Omega iSeries Ethernet`: Omega iSeries controller, with Ethernet connection
- `Omega iSeries Serial`: Omega iSeries controller, with Serial connection
- 
Support for more devices can be easily added. Pull requests are welcomed!

![Screenshot](screenshot.jpg)

A web app that gathers data from temperature controllers and posts them to a
web dashboard. Suitable for people who want to simplify day-to-day temperature
routine.

Basic function like _changing setpoint_ and _ramping_ can be triggered inside
the web app, while one can also define more complicated routines like a 
combination of ramping up and down involving multiple controllers.


## Installation

This app requires [Python 3.7+](https://www.python.org/) and [npm](https://www.npmjs.com/) (for
managing web dependencies). You should install them first and make sure they can be invoked from
command line.

It is always a good habit to create a virtual environment first to make
sure your local environment won't be contaminated:
```
python -m venv venv
```

Now you have two choices: install the _wheel_ or install from source.

### Install from pre-built wheel

Download pre-built wheel (.whl file) from [Release](https://github.com/JQIamo/temperature-control-app/releases/)
and run
```
venv/bin/pip install [path_to_downloaded_wheel]
```

That's it.

### Install from source

First, clone this repo to a convenient location.

After creating the virtual environment, build web assets and install them by
```
venv/bin/pip install .
```

This line will **copy the source code to the `site-packages` location** and install the package to
your virtual environment. If you don't want `pip` to copy the source but would to like to install
_in place_, run
```
venv/bin/pip install --editable .
```

This way, you may edit the source code under this folder and directly and run and test them easily.

## Run

To run the app, simply by
```
venv/bin/temperature_app --config [path to config]
```
The format of the configuration file will be introduced in the next section.

If you stick to the default settings, you should be able to access the web app via 
[http://{your ip address}:8000](http://localhost:8000).

## Configuration

The configuration file is in [YAML](https://yaml.org/) format. Here in this
repo, I present two sample configuration file [config_dummy.yml](config_dummy.yml)
(which controls two dummy test instance) and [config_omega.yml](config_omega.yml).
(which controls three Omega iSeries process controllers through Ethernet).

The configuration file is more or less self-explanatory. There's a few fields
defines some time constants.

### Network

The _network_ section define the address and ports the server binds to.
The http port is for accessing the web app. Internally, the web app communicates
with the server via [WebSockets](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API),
The WebSockets backend also needs a port to bind to.

Network settings can be confusing. I recommend just keep the default settings untouched, all
except the line `websocket_access_addr: ws://192.168.12.26:3001/` below. **In order to make the
web app connects to the WebSockets backend, you need to replace `192.168.12.26` with the server's
own ip address.**

Also, you need to set your firewall to allow incoming connection to port `8000` and `3001`.

```yaml
# binding to 0.0.0.0 means listening to all incoming connection, whereas
# binding to 127.0.0.1 will only accept connection from localhost
bind_addr: 0.0.0.0

# the port that serves the web server. In this case, the app can be accessed
#  via http://localost:8000
http_port: 8000

websocket_port: 3001

# == IMPORTANT: need to change 192.168.12.26 to your ip address ==
websocket_access_addr: ws://192.168.12.26:3001/
```

General guidelines for deploying web apps include _don't expose http services on a lot of ports,
[use a reverse proxy instead](https://www.linode.com/docs/guides/use-nginx-reverse-proxy/)._
[WebSockets endpoints can also be reverse-proxied](https://www.nginx.com/blog/websocket-nginx/).
In general, if you are good at dealing with http server, I would suggest you do this.

### Devices

The _devices_ section defines devices the app accesses. For example,
```yaml
devices:
  - name: SodiumCup(T1)
    dev_type: Omega iSeries Ethernet
    addr: 192.168.12.200
    port: 2000 
```

Here I defined a device called `SodiumCup(T1)` with device type to be 
`Omega iSeries Ethernet`. `addr` and `port` are two device-dependent
parameters.

#### Supported devices

Currently, supports
- `Omega iSeries Ethernet`: Omega iSeries controller, with Ethernet connection
- `Omega iSeries Serial`: Omega iSeries controller, with Serial connection

More devices can be easily added. See the following sections.

### Programs

Each program is divided into several steps, and in each step, one can specify
a series of actions performed across different devices.

For actions supported, see the table below:

| Operation   | Description                                                                    | Parameters  |                                                           |
|-------------|--------------------------------------------------------------------------------|-------------|-----------------------------------------------------------|
| CHANGE      | Immediately change the setpoint to a value and wait until temperature settles. | SETPOINT    | Target setpoint, in °C.                                   |
| LINEAR_RAMP | Linearly ramp up/down the temperature.                                         | TARGET_TEMP | Target temperature, in °C.                                |
|             |                                                                                | RATE        | Temperature raise per minute.                             |
| SOAK        | Hold the current temperature.                                                  | TIME        | Duration of soak in minutes.                              |
| STANDBY     | Disengage the controller. Put it into Standby mode.                            |             |                                                           |
| LOOP        | Jump back to a specific step and loop for a defined number of times.           | GOTO        | The number of the step to jump back to (starting from 0). |
|             |                                                                                | TIMES       | The number of times to loop.                              |

The following code defines a _Cool Down_ program that ramp down the temperatures
of two different controllers (in step 0) and put both of them in standby
mode (step 1).

Expressing nested list can be somewhat confusing in YAML. Please note the difference between
`-` and `- -`.

```yaml
  - name: Oven Cool Down
    description: Cool the sodium oven down to 20 °C in 100 minutes
    steps:
      - - action: LINEAR_RAMP
          device: SodiumCup(T1)
          params:
            TARGET_TEMP: 20
            RATE: 2
        - action: LINEAR_RAMP
          device: Flange(T2)
          params:
            TARGET_TEMP: 20
            RATE: 2.4
      - - action: STANDBY
          device: SodiumCup(T1)
        - action: STANDBY
          device: Flange(T2)
```

## Plugins

If you have an external logger like InfluxDB, you may want to also add a plugin to grab the
temperature data and upload them.

Now the only I have made is the one that pushes data to InfluxDB. To use it, add the following
section to your configuration file:
```yaml
influx_plugin:
  influx_api_url: http://jqi-logger.physics.umd.edu:8086/
  token: {your secret token}
  database: naer_db
  measurement: NaOven_readings
  push_interval: 0.25  # 1/4 min = 15 s
  ```

## Development

This app relies on Python for the server and [React.js](https://reactjs.org/) for the web 
dashboard. I used quite a bit of Async IO in the server.

### Add new drivers

The good news is if you just want to add new devices to this app, you don't need to know web
development and Async IO. All you need is:

1. Copy [driver/dummy_driver.py](temperature_web_control/driver/dummy_driver.py)
   (which is an example) and rename it to `[blah]_driver.py` and put
   it under the `driver/` folder. It has to end with `_driver.py` to be auto-imported by the 
   core.
2. Rewrite all methods inside `DummyDevice` and functions below (see comments). This part is 
   the code that really interacts with the controller devices.

### Add plugins

You can write plugins that subscribe to the events (like `status_available` event) of the app core
and process it in your own way. You are also free to call the event handlers insider app core
just like what the web app does.

You may check out [plugin/influx_push_plugin.py](temperature_web_control/plugin/influx_push_plugin.py)
and change the push logic to suit your need.

Also, save you plugin into the `plugin/` folder and named it with `[blah]_plugin.py` for the
auto-import mechanism to work.

