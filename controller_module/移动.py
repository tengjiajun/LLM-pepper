from controller_module.header import *
from controller_module.navigation_client import get_nav_client
import time

MODULE_NAME = "移动指示器"


@register(MODULE_NAME)
class MODULE_CLASS(base_class):
    key: list[int]
    active: bool

    def __init__(self, controller):
        self.fontSize = 16
        self.pos = [0, self.fontSize * 0]
        self.active = False
        self.last_key = None
        self.key = []
        self.last_time = 0
        self.client = Client(SERVER_IP, SERVER_PORT, "move", "sender", None)
        
        # Navigation client for map stream
        self.nav_client = None
        self.map_stream_active = False
        self.last_map_toggle_time = 0

    def update(self, controller):
        s = f"移动模式（F1）: {self.active} 当前按键：{' '.join([chr(i) for i in self.key])}"
        #map_status = f" | 地图（F2）: {self.map_stream_active}"
        #controller.text(s + map_status, "red" if self.active else "black")
        controller.text(s, "red" if self.active else "black")
        if self.active:
            if self.key or self.key != self.last_key:
                self.client.send(str(self.key).encode())
                self.last_key = self.key
        self.key = []


@register(["w", "a", "s", "d", "q", "e"])
def set_key(key: int, controller: MovementController):
    controller.obj[MODULE_NAME].key.append(key)


@register(pygame.K_F1)
def set_active(key: int, controller: MovementController):
    obj: MODULE_CLASS
    obj = controller.obj[MODULE_NAME]
    if time.time() - obj.last_time > 0.5:
        obj.active = not obj.active
        obj.last_time = time.time()


@register(pygame.K_F2)
def toggle_map_stream(key: int, controller: MovementController):
    """Toggle SLAM map video stream (F2 key)"""
    obj: MODULE_CLASS
    obj = controller.obj[MODULE_NAME]
    
    # Debounce
    if time.time() - obj.last_map_toggle_time < 0.5:
        return
    obj.last_map_toggle_time = time.time()
    
    # Initialize nav client on first use
    if obj.nav_client is None:
        try:
            obj.nav_client = get_nav_client("192.168.1.100", 8080)
            print("[移动] Navigation client initialized")
        except Exception as e:
            print(f"[移动] Navigation client init failed: {e}")
            return
    
    # Toggle map stream
    if obj.map_stream_active:
        obj.nav_client.stop_map_stream()
        obj.map_stream_active = False
        print("[移动] Map stream stopped")
    else:
        obj.nav_client.start_map_stream("SLAM Map")
        obj.map_stream_active = True
        print("[移动] Map stream started")
