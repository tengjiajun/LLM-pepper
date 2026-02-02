import json
import threading
import time
import os
import action
from collections import deque
#from pepper_module.joint_smoother import (
#    build_control_points,
#    smooth_control_points_for_joint,
#)

JOINT_INIT_RAD = {
    "HeadPitch": 0.0,
    "KneePitch": 0.0,
    "HipPitch": 0.0,
    "LShoulderPitch": 1.768,
    "LShoulderRoll": 0.096,
    "LElbowYaw": -1.716,
    "LElbowRoll": -0.103,
    "LWristYaw": 0.176,
    "RShoulderPitch": 1.768,
    "RShoulderRoll": -0.096,
    "RElbowYaw": 1.716,
    "RElbowRoll": 0.103,
    "RWristYaw": -0.176,
}

class body_module:
    def __init__(self, app, dt=100, fractionMaxSpeed=0.5):
        self.runnning = True
        self.dt = float(dt)
        self.fractionMaxSpeed = fractionMaxSpeed
        self.session = app.session
        self.motion = self.session.service("ALMotion")
        self.motion.moveInit()
        self.bending = False
        self.behavior_manager = self.session.service("ALBehaviorManager")
        self.behavior_name = "bz10002_nutcracker_v"
        self.dance1ing = False
        self.dance2ing = False
        self.init_pos()
        self.bodys = []
        self.joint_names = []
        self.times = []
        self.control_points = []

        self.actionControl = action.PepperAction(self.motion)
        #self.pose_queue = deque()
        #self.pose_queue_lock = threading.Lock()
        #self.max_pose_queue = 100 
        self.pose = None
        threading.Thread(target=self.run).start()

    def init_pos(self):
        self.position = {
            "HipRoll": 0,
            "KneePitch": 0,
        }

    def run(self):
        while self.runnning:
            if self.bodys:
                for action_code in list(self.bodys):
                    if action_code == ord(";"):
                        self.motion.changeAngles(
                            "HipPitch", 1 / self.dt, self.fractionMaxSpeed
                        )
                    elif action_code == ord("."):
                        self.motion.changeAngles(
                            "HipPitch", -1 / self.dt, self.fractionMaxSpeed
                        )
                for name, angles in self.position.items():
                    self.motion.setAngles(name, angles, self.fractionMaxSpeed)
                self.bodys = []
            else:
                time.sleep(0.1)
            if self.pose:
                try:
                    self.joint_names = self.pose.get("joint_names", [])
                    self.angles = self.pose.get("angles", [])
                    print(self.pose)
                    if self.pose.get("angles") != None:
                      self.motion.setAngles(self.joint_names, self.angles, 0.1)
                    print(self.joint_names,self.angles)
                    time.sleep(0.02)
                except Exception as e:
                    print("error: "+e)
                

    def bend_body(self, angle):
        if not self.bending:
            self.bending = True
            self.position["HipPitch"] = angle * (-0.01745)
            self.motion.setAngles("HipPitch", self.position["HipPitch"], 0.1)
            time.sleep(1)
            self.position["HipPitch"] = 0
            self.motion.setAngles("HipPitch", self.position["HipPitch"], 0.1)
            self.bending = False

    def dance1(self):
        if not self.dance1ing:
            self.dance1ing = True
            print("dance1ing = True")
            print(self.behavior_manager.isBehaviorInstalled(self.behavior_name))
            self.behavior_manager.runBehavior(self.behavior_name, _async=True)
            time.sleep(60)
            self.dance1ing = False
        print("dance2")

    def body(self, data):
        a = data.decode()
        b = str(a)
        if b[0] == '[':
            self.bodys = eval(data.decode())
        else:
            try:
                command = json.loads(data)
                if command.get('function') == 'open_external_video':
                   self.pose = command
                   #print(self.pose)
                   # with self.pose_queue_lock:
                   #     if len(self.pose_queue) >= self.max_pose_queue:
                   #         self.pose_queue.popleft()
                   #     self.pose_queue.append(command)
                   return  

                if command.get("angles") and command.get('function') == 'set_angles':
                    angles = command.get("angles")
                    joint_names = command.get("joint_names")
                    times = command.get("times")
                    if not times:
                        times = [[0.0, 1.0, 3.0, 4.0]] * len(joint_names)
                    control_points = [
                        [JOINT_INIT_RAD[name], angles[i], angles[i], JOINT_INIT_RAD[name]]
                        for i, name in enumerate(joint_names)
                    ]
                    self.joint_names = joint_names
                    self.times = times
                    self.control_points = control_points
                    print(joint_names,control_points)
                    self.actionControl.customize(
                        joint_names, times, control_points
                    )
                elif command.get("LShoulderPitch"):
                    print("analyze_pose_batch")
                    joint_names = command.get("joint_names", [])
                    total_images = command.get("total_images")
                    times_base = [0.0] + [round(1.0 + 0.1 * (i + 1), 3) for i in range(total_images)] + [round(1.0 + 0.1 * total_images + 1.0, 3)]
                    times = [list(times_base) for _ in joint_names]

                    sequences = {name: command.get(name, []) for name in joint_names}
                    joint_times = {
                        name: times[idx] if idx < len(times) else None
                        for idx, name in enumerate(joint_names)
                    }
                    #control_points = build_control_points(
                    #    joint_names,
                    #    sequences,
                    #    JOINT_INIT_RAD,
                    #    joint_times=joint_times,
                    #)

                    self.joint_names = joint_names
                    self.times = times
                    self.control_points = control_points
                    self.actionControl.customize(joint_names, times, control_points)

                else:
                    intent= command.get("intent")
                    slots = command.get("params", {})
                    print(intent)
                    if intent == u'bend_body':
                        angle = slots.get("angle", 1)
                        self.bend_body(angle)
                    elif intent == u'dance1':
                        self.dance1()
                    elif intent == u'bow':
                        self.actionControl.bow()
                    elif intent == u'shy':
                        self.actionControl.shy()
                    elif intent == u'proud':
                        self.actionControl.proud()
                    elif intent == u'think':
                        self.actionControl.think()
                    elif intent == u'salute':
                        self.actionControl.salute()
                    elif intent == u'modify_action':
                        json_str = slots.get("json", "{}")
                        if json_str:
                            params = json.loads(json_str)
                            for joint, angle in params.items():
                                if joint in self.joint_names:
                                    print(joint, self.joint_names)
                                    idx = self.joint_names.index(joint)
                                    print(idx)
                                    print(self.control_points[idx][1])
                                    self.control_points[idx][1] += angle
                                    self.control_points[idx][2] += angle
                                    print(self.control_points[idx][1])
                            self.actionControl.customize(
                              self.joint_names, self.times, self.control_points
                            )
                            print(self.control_points)
                    elif intent == u'play_again':
                        if self.joint_names and self.times and self.control_points:
                            self.actionControl.customize(
                                self.joint_names, self.times, self.control_points
                            )
                    elif intent == u'save_action':
                        if self.joint_names and self.times and self.control_points:
                            action_name = slots.get("action_name")
                            if not action_name:
                                print("action_name not exist")
                                return
                            action_json_path = "action.json"
                            if os.path.exists(action_json_path):
                                with open(action_json_path, "r", encoding="utf-8") as f:
                                    actions = json.load(f)
                            else:
                                actions = {}
                            actions[action_name] = {
                                "joint_names": self.joint_names,
                                "times": self.times,
                                "control_points": self.control_points
                            }
                            with open(action_json_path, "w", encoding="utf-8") as f:
                                json.dump(actions, f, ensure_ascii=False, indent=2)
                            print("Action"+action_name +"saved to action.json")
                        
                        
                            
            except json.JSONDecodeError:
                print('error')

    def stop(self):
        self.runnning = False
        self.motion.moveInit()
