import asyncio
import json

from controller_module.header import *
import time
import threading
import io

from controller_module.ASR import transcribe_audio
from controller_module.ShenFenDaiRu0528 import PepperServer
# from controller_module.IntentReco import send_message_to_rasa
# from controller_module.IntentReco import PepperServer
MODULE_NAME = "语音指示器"

@register(MODULE_NAME)
class MODULE_CLASS(base_class):
    key: list[int]
    active: bool

    def __init__(self, controller):
        self.fontSize = 16
        self.pos = [0, self.fontSize * 2]
        self.active = False
        self.last_time = 0
        self.sound_list = []
        self.client = Client(SERVER_IP, SERVER_PORT, "sound", "receiver", self.callback)
        self.need_send = None
        self.data = []
        self.lock = threading.Lock()




        # 语言识别相关
        self.loop = None
        self.recognize_running = False
        self.stop_event = asyncio.Event()  # 使用asyncio事件

        # 意图识别相关
        self.pepper_server = PepperServer()
        self.server_thread = threading.Thread(target=self.pepper_server.start)
        self.server_thread.daemon = True  # 设置为守护线程，这样主程序退出时会自动结束
        self.server_thread.start()

        # threading.Thread(target=self.get_input).start()
        threading.Thread(target=self.sound_play).start()
        threading.Thread(target=self.receipt_rasa_thread).start()
        threading.Thread(target=self.text_input).start()
    # async def action_encode(self,data):
    #     if data:

    async def intention_recognition(self , data):
         self.client.send("DINGDONG".encode('utf-8'))
         self.pepper_server.process_command(data)
    def receipt_rasa_thread(self):
        while True:
            if self.pepper_server.json_cache:
                json_str = self.pepper_server.json_cache.pop(0)
                print(json_str)
                self.get_input(json_str["reply"])
                if json_str["group"]:
                    for i in json_str["group"]:
                        with self.lock:
                            self.client.send(json.dumps(i).encode('utf-8'))
                else:
                    print("sendreply")
                    self.client.send("reply_action".encode('utf-8'))
            time.sleep(1)

    def text_input(self):
        while True:
            inp = input()
            if not inp:
                continue
            with self.lock:
                self.pepper_server.process_command(inp)
                # send_message_to_rasa(inp)

    def get_input(self,inp = ""):
        # while True:
        #     if not inp:
        #         continue
        #     with self.lock:
        # #         from util.Baidu_Text_transAPI import translate_text
        #
        #         self.need_send = "SOUND"+inp
        if inp:
            self.need_send = "SOUND"+inp


                #self.need_send = translate_text(self.need_send)
                #self.need_send = inp.encode('ansi')
                #print(inp)
                #print("con"+self.need_send)
                #self.sound_list.append(self.need_send.encode())
                #self.need_send = inp

    def sound_play(self):
        while True:
            if self.sound_list:
                data = self.sound_list.pop(0)
                audio_stream = io.BytesIO(data)
                sound = pygame.mixer.Sound(audio_stream)
                sound.play()
                while pygame.mixer.get_busy():
                    pygame.time.Clock().tick(10)
                # if self.active:
                #    self.data.append(data)
            time.sleep(0.1)

    def callback(self, data):
        from util.compress import decompress_data

        data = decompress_data(data)
        self.sound_list.append(data)
        # self.lock.acquire()
        #     if self.data:
        #         # 转文字+匹配
        #         self.need_send = "匹配的回答"
        #         self.data = []
        # self.lock.release()



    def update(self, controller):
        s = f"录音模式（F8开关,F9取消）: {self.active}"
        controller.text(s, "red" if self.active else "black")
        if self.need_send:
           self.lock.acquire()
           self.client.send(self.need_send.encode('utf-8'))
           self.need_send = None
           self.lock.release()

    def stop_transcription(self):
        self.stop_event.set()
        # if self.loop and self.task:
        #     self.loop.call_soon_threadsafe(self.task.cancel)
        # if self.recognize_thread and self.recognize_thread.is_alive():
        #     self.recognize_thread.join(timeout=1)
        self.active = False

    def run_transcribe_audio(self):
        try:
            # 在一个单独的线程中运行 asyncio.run
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            self.loop.run_until_complete(transcribe_audio(
                lang='auto',
                sv=False,
                callback=self.intention_recognition,
                stop_event=self.stop_event  # 传递事件对象
            ))
        except Exception as e:
            print(f"Exception occurred in transcribe_audio: {e}")
            raise  # 重新抛出异常以便外层捕获

    @register(pygame.K_F8)
    def set_active(key: int, controller: MovementController):
        obj: MODULE_CLASS
        obj = controller.obj[MODULE_NAME]
        if time.time() - obj.last_time > 0.5:
            obj.active = not obj.active
            if obj.active:
                # 开启语言识别
                obj.stop_event.clear()
                obj.recognize_running = True
                # 在一个单独的线程中运行 transcribe_audio

                threading.Thread(target=obj.run_transcribe_audio).start()
                print("语言识别启动")

            else:
                # 关闭语言识别
                obj.stop_transcription()
                obj.recognize_running = False
                print("语言识别停止")
            obj.last_time = time.time()


    @register(pygame.K_F9)
    def set_active(key: int, controller: MovementController):
        obj: MODULE_CLASS
        obj = controller.obj[MODULE_NAME]
        with obj.lock:
            """F9键强制停止录音"""
            obj.data = b""
            obj.active = False
            obj.recognize_running = False
            obj.stop_transcription()
            print("语音识别强制停止")
