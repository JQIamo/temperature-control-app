from abc import ABC, abstractmethod
from collections import namedtuple
from typing import List


Option = namedtuple("Option", ["name", "description", "type"])

class TemperatureMonitor(ABC):
    def __init__(self, name):
        self.name = name
        self._current_program = None
        self._program_stop_flag = False
        self.ramp_interval = 1  # interval in 1 min

    @property
    @abstractmethod
    def temperature(self) -> float:
        raise NotImplementedError

    # ===== Setpoint ====
    @property
    @abstractmethod
    def controllable(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def control_enabled(self) -> bool:
        raise NotImplementedError

    @control_enabled.setter
    @abstractmethod
    def control_enabled(self, value):
        raise NotImplementedError

    @property
    @abstractmethod
    def setpoint(self):
        raise NotImplementedError

    @setpoint.setter
    @abstractmethod
    def setpoint(self, value):
        raise NotImplementedError

    # ==== Other options ====
    @property
    @abstractmethod
    def other_options(self) -> List[Option]:
        # return a list of options
        raise NotImplementedError
