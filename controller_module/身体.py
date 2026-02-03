from controller_module.header import *
import time
import json
import threading
import contextlib

import requests

MODULE_NAME = "身体指示器"


@register(MODULE_NAME)
class MODULE_CLASS(base_class):
    key: list[int]
    active: bool

    def __init__(self, controller):
        self.active = False
        # self.last_key = None
        self.key = []
        self.last_time = 0
        self.client = Client(SERVER_IP, SERVER_PORT, "body", "sender", None)

        # 姿态识别流（转发给 Pepper Server，再由 Server 转发给 body_module）
        self.pose_stream_active = False
        self.pose_stream_stop = threading.Event()
        self.pose_stream_thread: threading.Thread | None = None

        # 与 pose_client.stream_pose 保持一致的默认配置
        self.pose_stream_url = "http://172.20.10.3:5000/open_external_video"
        self.pose_stream_payload = {
            "show_window": True,
            "cutoff_hz": 6.0,
            "output_fps": 10.0,
        }

    def _start_pose_stream(self):
        if self.pose_stream_thread and self.pose_stream_thread.is_alive():
            return
        self.pose_stream_stop.clear()
        self.pose_stream_thread = threading.Thread(
            target=self._pose_stream_loop,
            name="pose_stream_forwarder",
            daemon=True,
        )
        self.pose_stream_thread.start()

    def _stop_pose_stream(self):
        self.pose_stream_stop.set()

    def _pose_stream_loop(self):
        while not self.pose_stream_stop.is_set():
            try:
                with contextlib.closing(
                    requests.post(
                        self.pose_stream_url,
                        json=self.pose_stream_payload,
                        stream=True,
                        timeout=None,
                    )
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines(decode_unicode=True):
                        if self.pose_stream_stop.is_set():
                            break
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if not isinstance(data, dict):
                            continue

                        # body_module.body 对 function==open_external_video 有专门处理
                        if "function" not in data:
                            data["function"] = "open_external_video"

                        # 通过 Pepper Server.py 转发给 group==body 的客户端（机器人端 body_module）
                        payload = json.dumps(data, ensure_ascii=False).encode()
                        self.client.send(payload)
            except Exception:
                # 连接失败/中断：稍等后自动重连
                time.sleep(1.0)

    def update(self, controller):
        s = (
            f"身体模式（F5）: {self.active} "
            f"当前按键：{' '.join([chr(i) for i in self.key])}"
            f"姿态模仿（F11）: {self.pose_stream_active} "
        )
        controller.text(s, "red" if self.active else "black")
        if self.active:
            # if self.key != self.last_key:
            self.client.send(str(self.key).encode())
            # self.last_key = self.key

        self.key = []


@register([";", "."])
def set_key(key: int, controller: MovementController):
    controller.obj[MODULE_NAME].key.append(key)


@register(pygame.K_F5)
def set_active(key: int, controller: MovementController):
    obj: MODULE_CLASS
    obj = controller.obj[MODULE_NAME]
    if time.time() - obj.last_time > 0.5:
        obj.active = not obj.active
        obj.last_time = time.time()


@register(pygame.K_F11)
def toggle_pose_stream(key: int, controller: MovementController):
    obj: MODULE_CLASS
    obj = controller.obj[MODULE_NAME]
    if time.time() - obj.last_time <= 0.5:
        return

    obj.pose_stream_active = not obj.pose_stream_active
    obj.last_time = time.time()
    if obj.pose_stream_active:
        obj._start_pose_stream()
    else:
        obj._stop_pose_stream()
