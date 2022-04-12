import time
import requests
import base64
from typing import Union
from logging import Logger

from temperature_web_control.plugin.plugin_base import PluginState
from temperature_web_control.server.app_core import TemperatureAppCore
from temperature_web_control.utils import Config


class TokenAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers['Authorization'] = f'Basic {self.token}'
        return r


class InfluxPushPluginState(PluginState):
    def __init__(self, config: Config, app_core: TemperatureAppCore, logger: Logger):
        self.config = config
        self.app_core = app_core
        self.logger = logger

        token = self.config.get("influx_plugin", "token", default=None)
        if not token:
            user = self.config.get("influx_plugin", "user")
            password = self.config.get("influx_plugin", "password")

            token = base64.b64decode(f"{user}:{password}".encode("utf-8"))

        self.auth = TokenAuth(token)
        self.url = self.config.get("influx_plugin", "influx_api_url")
        self.database =self.config.get("influx_plugin", "database")
        self.measurement = self.config.get("influx_plugin", "measurement")
        self.interval = self.config.get("influx_plugin", "push_interval", default=5) * 60

        self.last_push_time = 0

        self.app_core.subscribe_to("status_available", self, self.on_status_available_event)

    async def on_status_available_event(self, subscribers, message):
        if time.time() - self.last_push_time < self.interval:
            return

        self.last_push_time = time.time()

        try:
            status = message['status']
            t = f"{int(time.time()*1e9):d}"

            req_url = requests.compat.urljoin(self.url, f"/write?db={self.database}")
            self.logger.debug(f"Influx Push Plugin: Push to {req_url}")

            req = []
            for dev in status.values():
                req.append(f"{self.measurement} {dev['name']}={dev['temperature']:.1f},{dev['name']}_units=\"C\" {t}")

            self.logger.debug(f"Influx Push Plugin: Request {req}")
            r = requests.post(req_url, data="\n".join(req), auth=self.auth, timeout=3)

            r.raise_for_status()
        except Exception as e:
            self.logger.error("Influx Push Plugin: Error while making request:")
            self.logger.exception(e)


    async def run(self):
        pass


async def initialize(config: Config, app_core: TemperatureAppCore, logger: Logger) -> Union[PluginState, None]:
    if config.get("influx_plugin", default=None):
        plugin = InfluxPushPluginState(config, app_core, logger)
        return plugin
    else:
        return None
