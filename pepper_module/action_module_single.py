import json
import threading
import time
import random


class action_module_single:
    def __init__(self, app, dt=100, fractionMaxSpeed=0.5):
        self.Is_rwave = False
        self.Is_lwave = False
        self.Is_rfinger = False
        self.runnning = True
        self.speaking = False
        self.handshaking = False
        self.dt = float(dt)
        self.fractionMaxSpeed = fractionMaxSpeed
        self.session = app.session
        self.motion = self.session.service("ALMotion")
        self.behavior_manager = self.session.service("ALBehaviorManager")
        self.behavior_name = ["test-81f705/replyaction_1",
                              "test-81f705/replyaction_2",
                              "test-81f705/replyaction_3"]
        self.handshake_name = "-6b46fb/woshou_2"
        self.motion.moveInit()
        self.init_pos()
        self.actions = []

        threading.Thread(target=self.run).start()

    def init_pos(self):
        self.position = {
            "RShoulderPitch": 1.6214,  # 46.2 -2pi~2pi moved
            "RShoulderRoll": -0.3000,
            "LShoulderPitch": 1.6214,  # 46.2 -2pi~2pi moved
            "LShoulderRoll": 0.3000,
            "LWristYaw": -0.3375,
            "RWristYaw": 0.3375,
            "RElbowRoll": 0.3405,  # -27.5s
            "LElbowRoll": 0.3405,  # -27.5s
            # "RElbowYaw": 0.0
        }

    def rl_wave_pos(self):
        self.position = {
            "RShoulderPitch": 0.2,  # 90du
            "RShoulderRoll": -0.3000,
            "LShoulderPitch": 1.6214,
            "LShoulderRoll": 0.3000,
            "LWristYaw": -0.3375,
            "RWristYaw": -1,
            "RElbowRoll": 90 * 3.14159 / 180,
            "RElbowYaw": 120 * 3.14159 / 180,
        }

    def rr_wave_pos(self):
        self.position = {
            "RShoulderPitch": 0.2,
            "RShoulderRoll": -0.3000,
            "LShoulderPitch": 1.6214,
            "LShoulderRoll": 0.3000,
            "LWristYaw": -0.3375,
            "RWristYaw": -1,
            "RElbowRoll": 90 * 3.14159 / 180,
            "RElbowYaw": 60 * 3.14159 / 180,
        }

    def run(self):
        while self.runnning:
            if self.actions:
                    for action in list(self.actions):
                        if action == ord("j"):
                            self.position["RShoulderPitch"] -= 3 / self.dt
                        elif action == ord("n"):
                            self.position["RShoulderPitch"] += 3 / self.dt
                        elif action == ord("h"):
                            self.position["LShoulderPitch"] -= 3 / self.dt
                        elif action == ord("b"):
                            self.position["LShoulderPitch"] += 3 / self.dt
                        elif action == ord("g"):
                            self.position["RShoulderRoll"] -= 2 / self.dt
                        elif action == ord("v"):
                            self.position["RShoulderRoll"] += 2 / self.dt
                        elif action == ord("c"):
                            self.position["LShoulderRoll"] -= 2 / self.dt
                        elif action == ord("f"):
                            self.position["LShoulderRoll"] += 2 / self.dt
                        elif action == ord("1"):
                            self.rwave_thread()
                        elif action == ord("2"):
                            self.lwave_thread()
                        elif action == ord("3"):
                            self.rfinger_thread()
                    for name in self.position:
                        if self.position[name] > 6:
                            self.position[name] = 6
                        if self.position[name] < -6:
                            self.position[name] = -6
                    if ord("z") in self.actions:
                        self.motion.moveInit()
                        self.actions = []
                        self.init_pos()
                        self.motion.setIdlePostureEnabled("Arms", True)
                    else:
                        self.motion.setIdlePostureEnabled("Arms", False)
                        for name, angles in self.position.items():
                            self.motion.setAngles(name, angles, self.fractionMaxSpeed)
                        self.actions = []

            else:
                time.sleep(0.1)

    def rwave(self):  # right arm wave
        if self.Is_rwave == True:
            print("rwaveTrue")
            return
        self.Is_rwave == True
        # joint_names = self.motion.getJointNames("Actuators")
        # print("Chains names:", joint_names)
        self.init_pos()
        for name, angles in self.position.items():
            self.motion.setAngles(name, angles, 0.1)
        time.sleep(0.5)

        self.rl_wave_pos()
        self.motion.setAngles("RShoulderPitch", self.position["RShoulderPitch"], 0.1)
        time.sleep(0.5)

        for name, angles in self.position.items():
            self.motion.setAngles(name, angles, 0.3)
        time.sleep(0.5)

        self.rr_wave_pos()
        for name, angles in self.position.items():
            self.motion.setAngles(name, angles, 0.3)
        time.sleep(0.5)
        self.rl_wave_pos()
        for name, angles in self.position.items():
            self.motion.setAngles(name, angles, 0.3)
        time.sleep(0.5)
        self.rr_wave_pos()
        for name, angles in self.position.items():
            self.motion.setAngles(name, angles, 0.3)
        time.sleep(0.5)
        self.init_pos()
        for name, angles in self.position.items():
            self.motion.setAngles(name, angles, 0.1)
        self.Is_rwave = False

    def rwave_thread(self):
        wave_thread = threading.Thread(target=self.rwave)
        wave_thread.start()

    def lwave(self):
        if self.Is_lwave == True:
            print("lwaveTrue")
            return
        self.Is_lwave == True
        self.Is_lwave = False

    def lwave_thread(self):
        wave_thread = threading.Thread(target=self.lwave)
        wave_thread.start()

    def rfinger(self):
        if self.Is_rfinger == True:
            return
        self.Is_rfinger == True
        # self.init_finger_pos()
        # time.sleep(0.5)
        # for name, angles in self.fingerpos.items():
        #     self.motion.setAngles(name, angles, self.fractionMaxSpeed)
        # n=5
        # while n :
        #     for name, angles in self.fingerpos.items():
        #         self.motion.setAngles(name, angles+30 * 3.14159 / 180, self.fractionMaxSpeed)
        #     for name, angles in self.fingerpos.items():
        #         self.motion.setAngles(name, angles, self.fractionMaxSpeed)
        #         time.sleep(0.1)
        #     n=n-1
        n = 5
        while n:
            self.motion.openHand("RHand")
            self.motion.waitUntilMoveIsFinished()
            self.motion.closeHand("RHand")
            self.motion.waitUntilMoveIsFinished()
            n = n - 1
        self.motion.openHand("RHand")
        self.Is_rfinger == False

    def rfinger_thread(self):
        thread = threading.Thread(target=self.rfinger)
        thread.start()

    def speak_action(self):
        if self.speaking == False:
            self.speaking = True
            name = self.behavior_name[random.randint(0, 2)]
            #names = self.behavior_manager.getInstalledBehaviors()
            #print("Behaviors on the robot:")
            #print(names)
            #print(self.behavior_manager.isBehaviorInstalled(name))
            self.behavior_manager.runBehavior(name, _async=True)
            time.sleep(5)
            if self.behavior_manager.isBehaviorRunning(name):
                self.behavior_manager.stopBehavior(name)
                time.sleep(1.0)
            else:
                print("Behavior is already stopped.")
            # names =self.behavior_manager.getInstalledBehaviors()
            # print("Behaviors on the robot:")
            # print(names)
            # for i in range(0,3):
            #     self.position = {
            #         "RElbowRoll": random.randint(3, 50)*3.1415/180,
            #         "LElbowRoll": random.randint(-50, -30)*3.1415/180
            #     }
            #     print(self.position["RElbowRoll"])
            #     print(self.position["LElbowRoll"])
            #     for name, angles in self.position.items():
            #         self.motion.setAngles(name, angles, 0.3)
            #     time.sleep(1)
            # self.init_pos()
            # for name, angles in self.position.items():
            #     self.motion.setAngles(name, angles, 0.3)
            # print(self.position["RElbowRoll"])
            # print(self.position["LElbowRoll"])
            self.speaking = False

    def handshake(self):
        if self.handshaking:
            print("Handshake already in progress")
            return
        if self.handshaking == False:
            self.handshaking = True
            
            BasicAwareness = self.session.service("ALBasicAwareness")
            if BasicAwareness.isEnabled():
              print("BasicAwareness off")
              BasicAwareness.setEnabled(False)
            
            self.behavior_manager.runBehavior(self.handshake_name, _async=True)
            time.sleep(12)
            if self.behavior_manager.isBehaviorRunning(self.handshake_name):
                self.behavior_manager.stopBehavior(self.handshake_name)
                time.sleep(1.0)
            else:
                print("Behavior is already stopped.")
            self.handshaking = False

    def action(self, data):
        a = data.decode()
        b = str(a)
        if b[0] == '[':
            if b[1] != ']':
              self.actions = eval(data.decode())
        elif b == u'reply_action':
            print("speak_action")
            self.speak_action()
        else:
            command = json.loads(data.decode())
            print(command)
            intent = command.get("intent")
            slots = command.get("slots", {})

            if intent == u'wave_hand':
                angle = slots.get("angle", 45)
                self.rwave_thread()
            if intent == u'handshake':
                self.handshake()

        # except json.JSONDecodeError:
        #     print("not json")
        #     self.actions = eval(data.decode())

    def stop(self):
        self.runnning = False
        self.motion.moveInit()
