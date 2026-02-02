from controller_module.header import *
import time
import numpy as np
import cv2
import threading


MODULE_NAME = "图像模块"


@register(MODULE_NAME)
class MODULE_CLASS(base_class):

    def __init__(self, controller):
        self.client = Client(SERVER_IP, SERVER_PORT, "video", "receiver", self.callback)
        self.width = controller.width
        self.height = controller.height
        self.image = pygame.Surface((controller.width, controller.height))
        self.image.fill("blue")
        self.lock = threading.Lock()

    def update(self, controller):
        controller.screen.blit(self.image, (0, 0))

    def callback(self, data):
        from util.compress import decompress_data

        try:
            data = decompress_data(data)
        except:
            return
        #print(data[:50])
        img_array = np.frombuffer(data, np.uint8)

        img_array = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        #cv2.imshow("im",img_array)
        img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
        image = pygame.surfarray.make_surface(img_array.swapaxes(0, 1))
        self.image = pygame.transform.scale(image, (self.width, self.height))
        
    def yuv422_to_rgb(self, yuv_array):
        """将YUV422格式转换为RGB格式"""
        n_pixels = yuv_array.size // 4
        rgb_array = np.zeros((n_pixels * 2, 3), dtype=np.uint8)

        for i in range(n_pixels):
            y1 = yuv_array[4 * i]
            u = yuv_array[4 * i + 1]
            y2 = yuv_array[4 * i + 2]
            v = yuv_array[4 * i + 3]

            for y, index in zip((y1, y2), (2 * i, 2 * i + 1)):
                c = y - 16
                d = u - 128
                e = v - 128

                r = (298 * c + 409 * e + 128) >> 8
                g = (298 * c - 100 * d - 208 * e + 128) >> 8
                b = (298 * c + 516 * d + 128) >> 8

                rgb_array[index, :] = [r, g, b]

        return rgb_array.reshape((self.height, self.width, 3))
