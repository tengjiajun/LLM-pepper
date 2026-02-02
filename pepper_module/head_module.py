import json
import threading
import time


class head_module:
    def __init__(self, app, dt=100, fractionMaxSpeed=0.5):
        self.runnning = True
        self.dt = float(dt)
        self.fractionMaxSpeed = fractionMaxSpeed
        self.session = app.session
        self.motion = self.session.service("ALMotion")
        self.motion.moveInit()
        self.init_pos()
        self.heads = []

        
        self.nodding = False
        self.nod_step = 0
        self.nod_times = 1
        self.initial_pitch = 0.0

        threading.Thread(target=self.run).start()

    def init_pos(self):
        self.position = {
            "HeadYaw": 0,
            "HeadPitch": -0.0945,
        }

    def run(self):
        while self.runnning:
            if self.heads:
                for action in list(self.heads):
                    if action == ord("'"):
                        self.position["HeadPitch"] -= 1 / self.dt
                    elif action == ord("/"):
                        self.position["HeadPitch"] += 1 / self.dt
                    elif action == ord("["):
                        self.position["HeadYaw"] += 5 / self.dt
                    elif action == ord("]"):
                        self.position["HeadYaw"] -= 5 / self.dt
                for name in self.position:
                    if self.position[name] > 6:
                        self.position[name] = 6
                    if self.position[name] < -6:
                        self.position[name] = -6
                if ord("m") in self.heads:
                    self.motion.moveInit()
                    self.heads = []
                    self.init_pos()
                    self.motion.setIdlePostureEnabled("Head", True)
                else:
                    self.motion.setIdlePostureEnabled("Head", False)
                    for name, angles in self.position.items():
                        self.motion.setAngles(name, angles, self.fractionMaxSpeed)
                    self.heads = []
            else:
                time.sleep(0.1)

    def start_nod(self, times=1):
            if not self.nodding:
              self.nodding = True
              self.initial_pitch = self.position["HeadPitch"]
              for i in range(0 , times):
                  self.position["HeadPitch"] -= 10 / self.dt
                  self.motion.setAngles("HeadPitch", self.position["HeadPitch"], 0.1)
                  time.sleep(1)
                  self.position["HeadPitch"] += 10 / self.dt
                  self.motion.setAngles("HeadPitch", self.position["HeadPitch"], 0.1)
                  time.sleep(1)
              # self.nod_times = times
              # self.nod_step = 0
              self.nodding = False

    def head(self, data):
        a = data.decode()
        b = str(a)
        if b[0] == '[':
            self.heads = eval(data.decode())
        else:
            try:
                command = json.loads(data)
                print(command)
                intent = command.get("intent")
                slots = command.get("params", {})
                print(intent)
                if intent == u'start_nod':
                    times = slots.get("times", 1)
                    print("start_nod")
                    self.start_nod(times)
            except json.JSONDecodeError:
                print("error")
                # self.heads = eval(data.decode())
            # self.heads = eval(data.decode())

    def stop(self):
        self.runnning = False
        self.nodding = False
        self.motion.moveInit()
