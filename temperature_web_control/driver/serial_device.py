import time
import serial

from temperature_web_control.driver.io_device import IODevice


class SerialDevice(IODevice):
    def __init__(self, port, baudrate, terminator=b'\r', parity='N', timeout=1, interval=0.3):
        self.terminator = terminator
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.parity = parity
        self.ser = serial.Serial(port, baudrate, timeout, parity=parity)
        self.last_send = 0
        self.interval = interval

    def send(self, data: bytes):
        if time.time() - self.last_send < self.interval:
            time.sleep(self.interval - (time.time() - self.last_send))
        self.last_send = time.time()

        self.ser.write(data + self.terminator)

    def recv(self, max_len=-1):
        data = b''
        c = b''
        while c != self.terminator and (max_len != 0 or len(data) < max_len):
            c = self.ser.read(1)
            data += c

        return data

    def reset(self, wait=0.5):
        self.ser.close()
        time.sleep(wait)
        self.ser = serial.Serial(self.port, self.baudrate, self.timeout, parity=self.parity)

    def __del__(self):
        self.ser.close()
