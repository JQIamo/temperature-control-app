import time
import socket

from temperature_web_control.driver.io_device import IODevice


class EthernetDevice(IODevice):
    def __init__(self, addr, port, terminator=b"\r", interval=0):
        super().__init__()
        self.addr = addr
        self.port = port
        self.terminator = terminator
        self.socket = socket.create_connection((addr, port), timeout=5)
        self.interval = interval
        self.last_send = 0

    def send(self, data: bytes):
        if time.time() - self.last_send < self.interval:
            time.sleep(self.interval - (time.time() - self.last_send))
        self.last_send = time.time()

        # print(f"{self.addr}:{self.port} <<<" + data.decode("utf8"))
        self.socket.sendall(data + self.terminator)

    def recv(self, max_len=-1):
        if max_len == 0:
            return

        data = b''
        c = b''
        while c != self.terminator and (max_len == -1 or len(data) < max_len):
            c = self.socket.recv(1)
            data += c

        return data

    def reset(self, wait=0.5):
        self.socket.close()
        time.sleep(wait)
        self.socket = socket.create_connection((self.addr, self.port), timeout=5)
        self.query_lock.release()

    def __del__(self):
        self.socket.close()