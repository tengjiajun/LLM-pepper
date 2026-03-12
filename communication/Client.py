from __future__ import print_function  # only needed for Python 2
import random
from communication.SafeSocket import SafeSocket
import threading
import sys
import traceback
import time


class Client:
    def __init__(self, ip, port, group_name, user_name, callback, retry=5):
        self.running = True
        self.para = {
            "ip": ip,
            "port": port,
            "group_name": group_name,
            "user_name": user_name,
            "callback": callback,
        }
        self.retry = retry
        self.connecting = False
        self.lock = threading.Lock()
        self.s = None
        self.listener_thread = None
        self.connect_socket()
        self.callback = callback
        if self.callback:
            self.listener_thread = threading.Thread(target=self.listener, daemon=True)
            self.listener_thread.start()

    def connect_socket(self):
        with self.lock:
            if not self.running:
                return
            self.connecting = True
            while self.running:
                if self.s:
                    try:
                        self.s.close()
                    except:
                        pass
                    self.s = None
                try:
                    self.s = SafeSocket()
                    self.s.connect((self.para["ip"], self.para["port"]))
                    self.s.send(self.para["group_name"].encode())
                    self.s.send(self.para["user_name"].encode())
                    print("group {" + self.para["group_name"] + "} connect success")
                    break
                except:
                    print(traceback.format_exc())
                    print(
                        "group {"
                        + self.para["group_name"]
                        + "} connect faild, retry after %ds" % self.retry
                    )
                    if not self.running:
                        break
                    time.sleep(self.retry)
            self.connecting = False

    def listener(self):
        while self.running:
            try:
                data = self.s.recv()
                try:
                    self.callback(data)
                except:
                    print(traceback.format_exc())
                    print("group {" + self.para["group_name"] + "} callback faild")
            except:
                if not self.running:
                    break
                print(
                    "group {"
                    + self.para["group_name"]
                    + "} recv faild, trying to reconnect"
                )
                self.connect_socket()

    def send(self, data):
        try:
            if self.connecting:
                return
            with self.lock:
                self.s.send(data)
        except:
            #self.connect_socket()
            print("lock")

    def stop(self):
        self.running = False
        with self.lock:
            if self.s is not None:
                try:
                    self.s.shutdown(2)
                except:
                    pass
                try:
                    self.s.close()
                except:
                    pass
                self.s = None
        return

    def set_callback(self, callback):
        assert not self.callback, "callback is already running"
        self.callback = callback
        self.listener_thread = threading.Thread(target=self.listener, daemon=True)
        self.listener_thread.start()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        id_ = str(random.randint(1, 9))
    else:
        id_ = sys.argv[1]
    client1 = Client("127.0.0.1", 5556, "default", "user" + str(id_), print)
    client1.send(b"client" + id_.encode())
    while True:
        inp = input()
        client1.send(inp.encode())