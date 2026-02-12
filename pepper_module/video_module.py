# coding=utf-8
from util.Config import *
from util.compress import compress_data
import numpy as np
from PIL import Image
from io import BytesIO
import io
#import imageio
import time
import threading

def numpy_array_to_jpeg_bytes(array):
    print("start jpg")
    image = Image.fromarray(array)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=30)
    jpeg_bytes = buffer.getvalue()
    buffer.close()
    #buffer = io.BytesIO()
    #imageio.imwrite(buffer, array, format='JPEG')
    #jpeg_bytes = buffer.getvalue()
    print("end")
    return jpeg_bytes

class video_module:
    def __init__(self, app, socket):
        self.socket = socket
        self.handle = None
        self.running = False
        self.lock = threading.Lock()
        self.video = app.session.service("ALVideoDevice")
        try:
            self.video.unsubscribe("video1_0")
        except Exception:
            pass
        self.handle = self.video.subscribeCamera("video1", 3, 14, 11, 30)
        print(self.handle)
        if not self.handle:
            print("subscribe video fail")
        self.running = True
        self.run()
        #self.th=threading.Thread(target=self.run)
        #self.th.start()
        #time.sleep(3)

    def run(self):
        while self.running:
            image = self.video.getImageRemote(self.handle)
            if image is None:
                print("get image fail ,try to restart program or pepper")
                time.sleep(0.2)
                continue
            image_binary = image[6]
            #print(image_binary[:50])
            #print(str(image_binary[:50]))

            #array = np.frombuffer(bytearray(image_binary), dtype=np.uint8)

            #print((image[1], image[0]))
            #img_array = array.reshape((int(image[1]), int(image[0]), 3))
            #print(img_array.shape)
            #print(img_array)
            #print("?")
            #try:
            #    jpg = numpy_array_to_jpeg_bytes(img_array)
            #except:
            #    print("err")
            #print(jpg[:50])
            #print(image_binary[:10])
            image_string = str(bytearray(image_binary))
            im = Image.frombytes("RGB", (image[0], image[1]), image_string)
            im = im.crop((0, 0, image[0]//2, image[1]))
            buffer = BytesIO()
            im.save(buffer, "JPEG")
            jpeg_bytes = buffer.getvalue()
            buffer.close()
            #print(jpeg_bytes[:50])
            image_binary = compress_data(jpeg_bytes)
            

            with self.lock:
                self.socket.send(image_binary)
            time.sleep(1.0 / 15)

   

    def stop(self):
        self.running = False

    def __del__(self):
        try:
            self.running = False
            if getattr(self, "video", None) is not None and getattr(self, "handle", None):
                self.video.unsubscribe(self.handle)
        except Exception:
            pass