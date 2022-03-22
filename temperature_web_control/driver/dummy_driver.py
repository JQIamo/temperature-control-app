import random

from temperature_web_control.model.temperature_monitor import TemperatureMonitor, Option


class DummyDevice(TemperatureMonitor):
    def __init__(self, name, fluctuation, logger):
        super().__init__(name)
        self._temperature = 10
        self._setpoint = 0
        self.dummy_fluctuation = fluctuation
        self.run = False
        self.logger = logger

    @property
    def temperature(self) -> float:
        return self._temperature + (random.random() * 2 - 1) * self.dummy_fluctuation

    @property
    def controllable(self) -> bool:
        return True

    @property
    def control_enabled(self) -> bool:
        return self.run

    @control_enabled.setter
    def control_enabled(self, value):
        self.run = value

    @property
    def setpoint(self):
        return self._setpoint

    @setpoint.setter
    def setpoint(self, value):
        self._setpoint = value
        self._temperature = value

    # ==== Other options ====
    @property
    def other_options(self):
        return [
            Option("dummy_fluctuation", "Fluctuation of dummy data.", float),
        ]


def dev_types():
    # In this function, you should return the device type to map to.
    # The App Core will send the device config items whose type is one of the values below
    # to the `from_config_dict` function.
    return ['Dummy']


def from_config_dict(config_dict: dict, logger):
    # Initialize device instance with the parameters in config_dict.
    if config_dict['dev_type'] == 'Dummy':
        return DummyDevice(
            config_dict['name'],
            config_dict['fluctuation'] if 'fluctuation' in config_dict else 5,
            logger
        )
