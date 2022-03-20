import random

from temperature_web_control.model.temperature_monitor import TemperatureMonitor, Option


class DummyDevice(TemperatureMonitor):
    def __init__(self, name, fluctuation):
        super().__init__(name)
        self._temperature = 10
        self._setpoint = 0
        self.dummy_fluctuation = fluctuation
        self.run = False

    @property
    def temperature(self) -> float:
        return self._temperature + (random.random() * 2 - 1) * self.dummy_fluctuation

    # ===== Setpoint ====
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

    def stop_program_immediately(self):
        return

    # ==== Other options ====
    @property
    def other_options(self):
        return [
            Option("dummy_fluctuation", "Fluctuation of dummy data.", float),
        ]

def dev_types():
    return ['Dummy']


def from_config_dict(config_dict: dict):
    if config_dict['dev_type'] == 'Dummy':
        return DummyDevice(
            config_dict['name'],
            config_dict['fluctuation'] if 'fluctuation' in config_dict else 5
        )
