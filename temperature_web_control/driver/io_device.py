from abc import ABC, abstractmethod
from threading import Lock


class IODevice(ABC):
    def __init__(self):
        self.query_lock = Lock()

    @abstractmethod
    def send(self, data: bytes) -> bytes:
        pass

    @abstractmethod
    def recv(self, max_len=-1) -> bytes:
        pass

    def query(self, query: bytes, max_len=-1) -> bytes:
        with self.query_lock:
            self.send(query)
            return self.recv(max_len)

    @abstractmethod
    def reset(self, wait=0.5):
        pass