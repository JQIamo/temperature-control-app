from typing import List

from temperature_web_control.driver.ethernet_device import EthernetDevice
from temperature_web_control.driver.io_device import IODevice
from temperature_web_control.driver.serial_device import SerialDevice
from temperature_web_control.model.temperature_monitor import TemperatureMonitor, Option


class OmegaCommunicationError(Exception):
    def __init__(self, cmd: str, error_response: bytes):
        super().__init__(f"Received {self.error_to_msg(error_response)} while sending command {cmd}.")

    @staticmethod
    def error_to_msg(error_response):
        if error_response == b'?43':
            return "Command Error"
        elif error_response == b'?46':
            return "Format Error"
        elif error_response == b'?50':
            return "Parity Error"
        elif error_response == b'?56':
            return "Serial Device Address Error"
        else:
            err_str = error_response.decode("utf-8")
            return f"Unknown Error {err_str}"


class OmegaISeries(TemperatureMonitor):
    """
    Control interface for Omega iSeries Temperature Controller.

    See https://assets.omega.com/manuals/M3397.pdf
    """

    def __init__(self, name, io_dev: IODevice, output):
        super().__init__(name)
        self.io_dev = io_dev
        self.echo_enabled = self._check_echo_enable()
        self.unit = self._check_unit()
        self.run = False

        assert output in [1, 2]
        self.output = output

    @staticmethod
    def get_ethernet_instance(name, addr, port, output=1):
        io_dev = EthernetDevice(addr, port, b'\r')
        return OmegaISeries(name, io_dev, output)

    @staticmethod
    def get_serial_instance(name, port, baudrate=9600, output=1):
        io_dev = SerialDevice(port, baudrate, b'\r')
        return OmegaISeries(name, io_dev, output)

    def other_options(self) -> List[Option]:
        return [
            Option("auto_pid", "Auto-adjust PID control parameters.", bool),
            Option("p_param", "P parameter of PID control.", int),
            Option("i_param", "i parameter of PID control.", int),
            Option("d_param", "d parameter of PID control.", int),
        ]

    @property
    def controllable(self):
        return True

    @property
    def support_pid(self):
        return True

    @property
    def temperature(self):
        return self._convert_temperature(float(self.query("*X01")))

    @property
    def control_enabled(self):
        # Let me surprise you: this server doesn't have a command to check the standby status.
        # I have to keep track the status internally. But this is not guaranteed to work.
        return self.run

    @control_enabled.setter
    def control_enabled(self, value):
        if value:
            self.send("*E03")
            self.run = True
        else:
            self.send("*D03")
            self.run = False

    @property
    def setpoint(self):
        # See manual 5.2 Example (p.18)
        ret = int(self.query("*R01"), 16)
        sign = 1 if ret & (1 << 23) == 0 else -1

        factor_mask = (ret & (0b111 << 20)) >> 20
        factor = 0
        if factor_mask == 0b001:
            factor = 1
        elif factor_mask == 0b010:
            factor = 0.1
        elif factor_mask == 0b011:
            factor = 0.01
        elif factor_mask == 0b100:
            factor = 0.001

        assert factor != 0

        setpoint_data = ret & 0xFFFFF
        return sign * self._convert_temperature(setpoint_data) * factor

    @setpoint.setter
    def setpoint(self, val):
        sign_mask = 0
        if val < 0:
            sign_mask = (1 << 23)
        setpoint_data = int(abs(val * 10))
        assert setpoint_data < 0xFFFF
        factor_mask = 0b010 << 20
        cmd = f"*W01{sign_mask | factor_mask | setpoint_data:06X}"
        self.send(cmd)

    def stop_program_immediately(self):
        self._program_stop_flag = True

    def _query_output_config(self):
        cmd_index = "R"
        if self.output == 1:
            cmd_index += "0C"
        else:
            cmd_index += "0D"

        out_cfg = int(self.query(f"*{cmd_index}"), 16)
        return out_cfg

    def _write_output_config(self, val):
        cmd_index = "W"
        if self.output == 1:
            cmd_index += "0C"
        else:
            cmd_index += "0D"

        cmd = f"*{cmd_index}{val:02X}"
        self.send(cmd)

    @property
    def auto_pid(self):
        out_cfg = self._query_output_config()
        return (out_cfg & (1 << 2)) != 0

    @auto_pid.setter
    def auto_pid(self, value: bool):
        out_cfg = self._query_output_config()
        if value:
            if (out_cfg & (1 << 2)) == 0:
                out_cfg = out_cfg | (1 << 2)
                self._write_output_config(out_cfg)
        else:
            if (out_cfg & (1 << 2)):
                out_cfg = out_cfg & ~(1 << 2)
                self._write_output_config(out_cfg)

    @property
    def p_param(self):
        p_param = int(self.query("*R17"), 16)
        return p_param

    @p_param.setter
    def p_param(self, val: int):
        assert 0 < val < 9999
        self.send(f"*W17{val:04X}")

    @property
    def i_param(self):
        i_param = int(self.query("*R18"), 16)
        return i_param

    @i_param.setter
    def i_param(self, val: int):
        assert 0 < val < 9999
        self.send(f"*W18{val:04X}")

    @property
    def d_param(self):
        d_param = int(self.query("*R19"), 16)
        return d_param

    @d_param.setter
    def d_param(self, val: int):
        assert 0 < val < 9999
        self.send(f"*W19{val:04X}")

    def _check_echo_enable(self):
        cmd = "*R1F\r"
        _ret = self.io_dev.query(cmd.encode("utf-8"))
        if _ret[0] == b'?':
            raise OmegaCommunicationError(cmd, _ret)

        ret = _ret.decode("utf-8")

        if ret[0] == "R":
            ret = ret[3:]
            # return True

        mask = int(ret, 16)
        echo = mask & (1 << 2)  # Echo setting bit, sanity check

        return echo != 0

    def _check_unit(self):
        ret = self.query("*R08")  # Query Reading Configuration

        mask = int(ret, 16)
        unit = mask & (1 << 3)

        return "C" if unit == 0 else "F"

    def query(self, cmd: str, max_len=-1) -> str:
        ret = self.io_dev.query(cmd.encode("utf-8") + b"\r", max_len)
        if not ret:
            return ""

        if ret[0] == b'?':
            raise OmegaCommunicationError(cmd, ret)

        ret_str = ret.decode("utf-8")

        if self.echo_enabled:
            return ret_str[len(cmd) - 1:]  # -1: get rid of *
        return ret_str

    def send(self, cmd):
        if self.echo_enabled:
            self.query(cmd)
        else:
            self.io_dev.send(cmd.encode("utf-8"))

    def _convert_temperature(self, val):
        if self.unit == "F":
            return (val - 32) * 5 / 9
        else:
            return val


def dev_types():
    return ['Omega iSeries Ethernet', 'Omega iSeries Serial']


def from_config_dict(config_dict: dict):
    if config_dict['dev_type'] == 'Omega iSeries Ethernet':
        return OmegaISeries.get_ethernet_instance(
            config_dict['name'],
            config_dict['addr'],
            config_dict['port'] if 'port' in config_dict else 2000,
            config_dict['output'] if 'output' in config_dict else 1
        )
    elif config_dict['dev_type'] == 'Omega iSeries Serial':
        return OmegaISeries.get_serial_instance(
            config_dict['name'],
            config_dict['port'],
            config_dict['baudrate'] if 'baudrate' in config_dict else 9600,
            config_dict['output'] if 'output' in config_dict else 1
        )
