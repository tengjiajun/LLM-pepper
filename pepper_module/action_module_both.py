import threading
import time
import json
import math


class action_module_both:
    def __init__(self, app, dt=100, fractionMaxSpeed=0.5):
        self.runnning = True
        self.dt = float(dt)
        self.fractionMaxSpeed = fractionMaxSpeed
        self.session = app.session
        self.motion = self.session.service("ALMotion")
        self.motion.moveInit()
        self.tray_active = False
        self.init_pos()
        self.actions = []
        threading.Thread(target=self.run).start()

    def _angle_interp(self, names, angles, duration):
        try:
            self.motion.angleInterpolation(names, angles, [duration] * len(names), True)
        except:
            return

    def _apply_arm_angles(self):
        # To reduce collision risk:
        # 1) pre-extend ShoulderRoll outward
        # 2) move all other joints to target
        # 3) apply ShoulderRoll target last
        self.motion.setIdlePostureEnabled("Arms", False)

        duration = float(getattr(self, "arm_move_time", 0.8))

        target_roll = float(self.position.get("LShoulderRoll", 0.0))
        outward_roll = max(target_roll, float(getattr(self, "shoulder_roll_outward", 0.0)))

        # Phase 1: pre-extend ShoulderRoll outward
        self._angle_interp(
            ["LShoulderRoll", "RShoulderRoll"],
            [outward_roll, -outward_roll],
            duration,
        )

        # Phase 2: move all other joints to target
        names = []
        angles = []

        for name, angle in self.position.items():
            if "ShoulderRoll" in name:
                continue
            names.append(name)
            angles.append(float(angle))

        for name, mirror in self.mirror.items():
            if "ShoulderRoll" in name:
                continue
            names.append(name)
            angles.append(float(self.position[mirror]))

        for name, reverse in self.reverse.items():
            if "ShoulderRoll" in name:
                continue
            names.append(name)
            angles.append(-float(self.position[reverse]))

        if "LHand" in self.position:
            names.append("RHand")
            angles.append(float(self.position["LHand"]))

        if names:
            self._angle_interp(names, angles, duration)

        # Phase 3: apply ShoulderRoll target last
        self._angle_interp(
            ["LShoulderRoll", "RShoulderRoll"],
            [target_roll, -target_roll],
            duration,
        )

    def init_pos(self):
        self.position = {
            "LShoulderPitch": 1.6214,  # 46.2 -2pi~2pi moved
            # "LShoulderRoll": 0.1303,  # 8.5 0~2pi check
            "LShoulderRoll": 0.3000,
            "LElbowYaw": 0.0,  # -30.9 check
            "LElbowRoll": -0.3405,  # -27.5s
            # "LWristYaw": -0.3375,
            "LWristYaw": 0.0,
            "LHand": 0.67,
        }
        self.mirror = {
            "RShoulderPitch": "LShoulderPitch",
        }
        self.reverse = {
            "RShoulderRoll": "LShoulderRoll",
            "RElbowRoll": "LElbowRoll",
            "RElbowYaw": "LElbowYaw",
            "RWristYaw": "LWristYaw",
        }

        # Safe outward pre-roll value (radians)
        self.shoulder_roll_outward = math.radians(40.5)

        # Arm interpolation duration per phase (seconds)
        self.arm_move_time = 0.8

        # Tray pose captured from the provided UI (degrees converted to radians)
        self.tray_pose = {
            "RShoulderPitch": math.radians(-40.4),
            "RShoulderRoll": math.radians(-33.7),
            "RElbowYaw": math.radians(93.7),
            "RElbowRoll": math.radians(7.1),
            "RWristYaw": math.radians(-3.7),
            "HeadPitch": math.radians(-9.1),
            "HeadYaw": math.radians(-55.2),
            "RHand": 0.93,
        }

    def set_tray_pose(self):
        # Enable tray mode and set target joint positions
        try:
            print("[action_module_both] tray_pose activated")
        except:
            pass
        self.tray_active = True
        duration = float(getattr(self, "arm_move_time", 0.8))

        names = []
        angles = []
        for k, v in self.tray_pose.items():
            if k == "RHand":
                continue
            names.append(k)
            angles.append(float(v))

        if names:
            self._angle_interp(names, angles, duration)

        if "RHand" in self.tray_pose:
            self._angle_interp(["RHand"], [float(self.tray_pose["RHand"])], duration)

    def run(self):
        while self.runnning:
            self.motion.setSmartStiffnessEnabled(False)
            if self.actions:
                # Any manual action cancels tray hold
                self.tray_active = False
                for action in list(self.actions):
                    if action == 1073741906:  # UP
                        self.position["LShoulderPitch"] -= 3 / self.dt
                    elif action == 1073741905:  # DOWN
                        self.position["LShoulderPitch"] += 3 / self.dt
                    elif action == 1073741904:  # LEFT
                        self.position["LShoulderRoll"] -= 1 / self.dt
                        self.position["LElbowRoll"] -= 1 / self.dt
                    elif action == 1073741903:  # RIGHT
                        self.position["LShoulderRoll"] += 1 / self.dt
                        self.position["LElbowRoll"] += 1 / self.dt
                for name in self.position:
                    if self.position[name] > 6:
                        self.position[name] = 6
                    if self.position[name] < -6:
                        self.position[name] = -6
                if ord("x") in self.actions:
                    self.motion.moveInit()
                    self.actions = []
                    self.init_pos()
                    self.motion.setIdlePostureEnabled("Arms", True)
                elif ord("u") in self.actions:
                    self.motion.closeHand("LHand")
                elif ord("i") in self.actions:
                    self.motion.closeHand("RHand")
                elif ord("t") in self.actions:
                    self.motion.openHand("LHand")
                elif ord("y") in self.actions:
                    self.motion.openHand("RHand")
                else:
                    self._apply_arm_angles()
                    self.actions = []
            else:
                time.sleep(0.1)

    def action(self, data):
        # Supports two payload types:
        # 1) legacy keyboard list (e.g. "[1073741906, ...]")
        # 2) JSON command with {"intent":..., "module":..., "params":...}

        decoded = data.decode()

        if decoded and decoded[0] == '{':
            try:
                cmd = json.loads(decoded)
            except:
                return
            intent = cmd.get("intent")
            if intent == "tray_pose":
                self.set_tray_pose()
            else:
                try:
                    print("[action_module_both] unknown intent: {}".format(intent))
                except:
                    pass
            return

        # Legacy mode
        self.actions = eval(decoded)

    def stop(self):
        self.runnning = False
        self.motion.moveInit()
