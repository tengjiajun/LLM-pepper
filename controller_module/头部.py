from controller_module.header import *
import time

MODULE_NAME = "头部指示器"


@register(MODULE_NAME)
class MODULE_CLASS(base_class):
    key: list[int]
    active: bool

    def __init__(self, controller):
        self.active = False
        # self.last_key = None
        self.key = []
        self.last_time = 0
        self.client = Client(SERVER_IP, SERVER_PORT, "head", "sender", None)

    def update(self, controller):
        s = f"头部模式（F4）: {self.active} 当前按键：{' '.join([chr(i) for i in self.key])}"
        controller.text(s, "red" if self.active else "black")
        if self.active:
            # if self.key != self.last_key:
            self.client.send(str(self.key).encode())
            # self.last_key = self.key
        self.key = []


@register(["'", "/", "[", "]","m"])
def set_key(key: int, controller: MovementController):
    controller.obj[MODULE_NAME].key.append(key)


@register(pygame.K_F4)
def set_active(key: int, controller: MovementController):
    obj: MODULE_CLASS
    obj = controller.obj[MODULE_NAME]
    if time.time() - obj.last_time > 0.5:
        obj.active = not obj.active
        obj.last_time = time.time()
