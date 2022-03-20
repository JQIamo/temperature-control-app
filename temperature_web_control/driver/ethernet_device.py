import socket

from temperature_web_control.driver.io_device import IODevice


class EthernetDevice(IODevice):
    def __init__(self, addr, port, terminator=b"\r"):
        self.addr = addr
        self.port = port
        self.terminator = terminator
        self.socket = socket.create_connection((addr, port), timeout=5)

    def send(self, data: bytes):
        self.socket.sendall(data + self.terminator)

    def recv(self, max_len=-1):
        if max_len == 0:
            return

        data = b''
        c = b''
        while c != self.terminator and (max_len != -1 or len(data) < max_len):
            c = self.socket.recv(1)
            data += c

        return data

    def __del__(self):
        self.socket.close()