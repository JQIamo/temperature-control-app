from temperature_web_control.driver.io_device import IODevice
from temperature_web_control.driver.omega_driver import OmegaISeries


class DummyIODevice(IODevice):
    def __init__(self):
        self.dummy_resp = {}
        self.last_send = b""
        self.expectation = []

    def send(self, data: bytes):
        self.last_send = data
        print(">> " + data.decode("utf-8"))

        if self.expectation:
            assert data == self.expectation[0]
            del self.expectation[0]

    def recv(self, max_len=-1):
        assert self.last_send in self.dummy_resp
        return self.dummy_resp[self.last_send]

    def expect(self, expect):
        self.expectation.append(expect)
        if expect not in self.dummy_resp:
            self.dummy_resp[expect] = b""


class TestOmega:
    def test_read_temperature(self):
        io_dev = DummyIODevice()

        io_dev.dummy_resp = {
            b"*R1F\r": b"R1F14\r",
            b"*R08\r": b"R0842\r"
        }

        omega = OmegaISeries(io_dev, output=1)
        assert omega.echo_enabled
        assert omega.unit == "C"

        io_dev.dummy_resp[b"*X01\r"] = b"X01075.4\r"
        assert omega.temperature == 75.4

        io_dev.dummy_resp[b"*R01\r"] = b"R012003E8\r"
        assert omega.setpoint == 100

        io_dev.expect(b"*D03\r")
        omega.control_enabled = False

        io_dev.expect(b"*E03\r")
        omega.control_enabled = True

        io_dev.expect(b"*W01A003E8\r")
        omega.setpoint = -100

        io_dev.dummy_resp[b"*R0C\r"] = b"R0C01\r"
        assert not omega.auto_pid

        io_dev.expect(b"*R0C\r")
        io_dev.expect(b"*W0C05\r")
        omega.auto_pid = True

        io_dev.dummy_resp[b"*R17\r"] = b"R1700C8\r"
        assert omega.p_param == 200

        io_dev.dummy_resp[b"*R18\r"] = b"R1800B4\r"
        assert omega.i_param == 180

        io_dev.dummy_resp[b"*R19\r"] = b"R190000\r"
        assert omega.d_param == 0

        io_dev.expect(b"*W170096\r")
        omega.p_param = 150

        io_dev.expect(b"*W180096\r")
        omega.i_param = 150

        io_dev.expect(b"*W190096\r")
        omega.d_param = 150





