import socket
import threading

class SafeSocket:
    def __init__(self, s = None):
        if not s:
            s = socket.socket()
        self.s = s
        self.lock=threading.Lock()
        self.exception = None

    def recv(self):
        if self.exception:
            raise self.exception
        try:
            first_byte = int(self.s.recv(1).decode())
            data_length = ""
            for _ in range(first_byte):
                data_length += self.s.recv(1).decode()
            data = b""
            data_length = int(data_length)
            while len(data) != data_length:
                data += self.s.recv(data_length - len(data))
            return data
        
        except Exception as exception:
            self.exception = exception
            raise

    def send(self, data):
        data_length = len(data)
        data_length_str = str(data_length)
        data_length_str_length = len(data_length_str)
        data_length_str_length_str = str(data_length_str_length)
        
        data_length_str_encode = data_length_str.encode()
        data_length_str_length_str_encode = data_length_str_length_str.encode()
        to_send = data_length_str_length_str_encode + data_length_str_encode + data
        
        with self.lock:
            if self.exception:
                raise self.exception
            try:
                self.s.sendall(to_send)
            except Exception as exception:
                self.exception = exception
                raise

    def __getattr__(self, item):
        return self.s.__getattribute__(item)
    
    def __del__(self):
        self.s.close()

if __name__ == "__main__":
    s = SafeSocket()
    s.bind(("0.0.0.0", 5556))