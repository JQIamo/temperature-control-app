from abc import ABC, abstractmethod


class IODevice(ABC):
    @abstractmethod
    def send(self, data: bytes) -> bytes:
        pass

    @abstractmethod
    def recv(self, max_len=-1) -> bytes:
        pass

    def query(self, query: bytes, max_len=-1) -> bytes:
        self.send(query)
        return self.recv(max_len)

    @abstractmethod
    def reset(self):
        pass