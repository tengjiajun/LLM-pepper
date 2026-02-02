import json
import socket
import threading
import traceback
from typing import Union, Dict, List
from communication.SafeSocket import SafeSocket
import os
from util.compress import decompress_data


class Server:
    def __init__(self, port=5556):
        self.running = True
        self.port = port
        self.group: Dict[str, List[SafeSocket]]
        self.group = {}
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def run(self):
        s = socket.socket()
        try:
            s.bind(("0.0.0.0", self.port))
            print("端口已开启")
        except:
            print("端口被占用，程序将在10秒后退出")
            import time
            time.sleep(10)
            raise
        s.listen(50)
        while self.running:
            c, _ = s.accept()
            threading.Thread(target=self.process, args=(SafeSocket(c),)).start()
        s.close()

    def append(self, group_name: str, s: SafeSocket):
        with self.lock:
            if not group_name in self.group:
                self.group[group_name] = []
            self.group[group_name].append(s)

    def remove(self, s: SafeSocket):
        with self.lock:
            for group_name in self.group:
                if s in self.group[group_name]:
                    self.group[group_name].remove(s)
                    print(f"有客户端退出群组{group_name}")

    def send(self, s: SafeSocket, data: bytes):
        try:
            s.send(data)
        except:
            self.remove(s)

    def process(self, s: SafeSocket):
        group_name = s.recv().decode()
        user_name = s.recv().decode()
        print(f"{user_name}已经加入群组{group_name}")
        self.append(group_name, s)

        while True:
            try:
                data = s.recv()
            except:
                self.remove(s)
                break
            try:

                if data.decode('utf-8')=="DINGDONG":

                    for client in self.group["sound"]:
                        if client != s:
                            print("DINGDONG")
                            threading.Thread(target=self.send, args=(client, "DINGDONG".encode('utf-8'))).start()
                if data.decode('utf-8')=="reply_action":
                    for client in self.group["active_1"]:
                        threading.Thread(target=self.send, args=(client, "reply_action".encode('utf-8'))).start()
                message = json.loads(data.decode('utf-8'))
                json_str = json.dumps(message).encode()

                if "joint_names" in message:
                    print(message)
                    for client in self.group["body"]:
                        threading.Thread(target=self.send, args=(client, json_str)).start()

                if "module" in message and "intent" in message:
                    target_module = message["module"]
                    try:
                        targets = self.group.get(target_module, [])
                        print("route to module={}, clients={}".format(target_module, len(targets)))
                        for client in targets:
                            if client != s:  # 避免回传给自己
                                threading.Thread(target=self.send, args=(client, json_str)).start()
                    except Exception:
                        print("route failed for module {}".format(target_module))
                        print(traceback.format_exc())
                    continue  # 跳过后续广播逻辑

            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # 非 JSON 数据，按原有逻辑处理
            except Exception:
                # Any other unexpected error should not kill the connection thread
                print("process error")
                print(traceback.format_exc())

            for i in self.group[group_name]:
                if i != s:
                    threading.Thread(target=self.send, args=(i, data)).start()

    def join(self):
        self.thread.join()

    def stop(self):
        self.running = False
        return


if __name__ == "__main__":
    server = Server(5556)
