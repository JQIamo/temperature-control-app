from abc import ABC
from logging import Logger
from typing import Union

from temperature_web_control.server.app_core import TemperatureAppCore
from temperature_web_control.utils import Config

class PluginState(ABC):
    async def run(self):
        pass

def initialize(config: Config, app_core: TemperatureAppCore, logger: Logger) -> Union[PluginState, None]:
    pass