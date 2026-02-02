from controller_module.header import *
import time

MODULE_NAME = "动作双手指示器"
MAP = {
    pygame.K_UP: "↑",
    pygame.K_DOWN: "↓",
    pygame.K_LEFT: "←",
    pygame.K_RIGHT: "→",
    ord("i"): "i",
    ord("u"): "u",
    ord("t"): "t",
    ord("y"): "y",
    ord("x"): "x",
}

@register(MODULE_NAME)
class MODULE_CLASS(base_class):
    key: list[int]
    active: bool

    def __init__(self, controller):
        self.active = False
        # self.last_key = None
        self.key = []
        self.last_time = 0
        self.client = Client(SERVER_IP, SERVER_PORT, "active_2", "sender", None)

    def update(self, controller):
        s = f"动作双手模式（F2）: {self.active} 当前按键：{' '.join([MAP[i] for i in self.key])}"
        controller.text(s, "red" if self.active else "black")
        if self.active:
            # if self.key != self.last_key:
            self.client.send(str(self.key).encode())
            # self.last_key = self.key

        self.key = []


@register([key for key in MAP])
def set_key(key: int, controller: MovementController):
    controller.obj[MODULE_NAME].key.append(key)


@register(pygame.K_F2)
def set_active(key: int, controller: MovementController):
    obj: MODULE_CLASS
    obj = controller.obj[MODULE_NAME]
    if time.time() - obj.last_time > 0.5:
        obj.active = not obj.active
        obj.last_time = time.time()
