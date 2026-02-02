import time
from abc import ABC,abstractmethod
import pygame
import threading
import os

controller = None


class MovementController:
    screen: pygame.Surface
    obj: dict[str, object]
    key: dict[int, object]
    lock: threading.Lock

    def __init__(self, width=1280, height=720, fps=30):
        pygame.init()
        pygame.display.init
        self.FontSize = height // 20
        self.FontStyle = pygame.font.SysFont("simsun", self.FontSize)
        self.FontData = []
        self.lock = threading.Lock()
        self.fps = fps
        self.running = True
        self.key = {}
        self.obj = {}
        self.width = width
        self.height = height
        # self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        threading.Thread(target=self.run).start()
        time.sleep(1)  # screen 传递等待

    def regiterKey(self, key, callback):
        if not key in self.key:
            self.key[key] = []
        self.key[key].append(callback)

    def registerObj(self, name, obj):
        if name in self.obj:
            raise Exception(f"object {name} is already registered")
        self.obj[name] = obj

    def run(self):
        pygame.display.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.running = True
        while self.running:
            self.lock.acquire()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    os._exit(0)
                    return
            self.screen.fill("white")
            keys = pygame.key.get_pressed()
            for key in self.key:
                if keys[key]:
                    for func in self.key[key]:
                        func(key, self)
            for key in self.obj:
                self.obj[key].update(self)
            self.FontData = [
                self.FontStyle.render(font, True, color)
                for (font, color) in self.FontData
            ]
            max_l = max([0] + [i.get_width() for i in self.FontData])
            text_background = pygame.Surface(
                (max_l, len(self.FontData) * self.FontSize)
            )
            text_background.set_alpha(128)
            text_background.fill("white")
            self.screen.blit(text_background, (0, 0))
            for i, text_surface in enumerate(self.FontData):
                self.screen.blit(text_surface, (0, i * self.FontSize))
            self.FontData = []
            pygame.display.flip()
            self.lock.release()
            self.clock.tick(self.fps)
        pygame.display.quit()

    def stop(self):
        self.running = False
        return

    def text(self, data, color="black"):
        self.FontData.append((data, color))

        
class base_class(ABC):
    @abstractmethod
    def __init__(self, controller):
        pass

    @abstractmethod
    def update(self, controller: MovementController):
        pass


def register(args=None):
    global controller

    def decorator(obj):
        controller.lock.acquire()
        if isinstance(args, int):
            controller.regiterKey(args, obj)
        elif isinstance(args, list):
            for key in args:
                if isinstance(key, int):
                    controller.regiterKey(key, obj)
                else:
                    controller.regiterKey(ord(key), obj)
        else:
            assert issubclass(obj, base_class), "please inherit from base_class"
            controller.registerObj(args, obj(controller))
        controller.lock.release()
        return obj

    if not controller:
        assert isinstance(args, MovementController), "please register controller first"
        controller = args
    return decorator

