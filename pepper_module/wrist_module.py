import threading
import time


class wrist_module:
    def __init__(self, app, dt=100, fractionMaxSpeed=0.5):
        self.runnning = True
        self.dt = float(dt)
        self.fractionMaxSpeed = fractionMaxSpeed
        self.session = app.session
        self.motion = self.session.service("ALMotion")
        self.motion.moveInit()
        self.init_pos()
        self.wrists = []
        threading.Thread(target=self.run).start()

    def init_pos(self):
        self.position = {
            "LWristYaw": -0.3375,
            "RWristYaw": 0.3375,
        }

    def run(self):
        while self.runnning:
            if self.wrists:
                for action in list(self.wrists):
                    if action == ord("k"):
                        self.position["LWristYaw"] -= 5 / self.dt
                    elif action == ord("l"):
                        self.position["LWristYaw"] += 5 / self.dt
                    elif action == ord("o"):
                        self.position["RWristYaw"] -= 5 / self.dt
                    elif action == ord("p"):
                        self.position["RWristYaw"] += 5 / self.dt
                for name in self.position:
                    if self.position[name] > 6:
                        self.position[name] = 6
                    if self.position[name] < -6:
                        self.position[name] = -6
                for name, angles in self.position.items():
                    self.motion.setAngles(name, angles, self.fractionMaxSpeed)
                self.wrists = []
            else:
                time.sleep(0.1)

    def wrist(self, data):
        self.wrists = eval(data.decode())

    def stop(self):
        self.runnning = False
        self.motion.moveInit()
