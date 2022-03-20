import serial

from temperature_web_control.driver.io_device import IODevice


class SerialDevice(IODevice):
    def __init__(self, port, baudrate, terminator=b'\r', parity='N', timeout=1):
        self.terminator = terminator
        self.ser = serial.Serial(port, baudrate, timeout, parity=parity)

    def send(self, data: bytes):
        self.ser.write(data + self.terminator)

    def recv(self, max_len=-1):
        data = b''
        c = b''
        while c != self.terminator and (max_len != 0 or len(data) < max_len):
            c = self.ser.read(1)
            data += c

        return data

    def __del__(self):
        self.ser.close()
