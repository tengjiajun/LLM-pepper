import json
import math
import threading
import time


class move_module:
    def __init__(self, app, dt=1, sound_module=None):
        self.dt = float(dt)
        self.rotating = False
        self.forwarding = False
        self.blocking_move = False
        self.session = app.session
        self.motion = self.session.service("ALMotion")
        self.motion.moveInit()
        self.spinning = False
        self.time = time.time()
        self.watchdoging = True
        self.sound_module = sound_module
        if self.sound_module:
            print("[move_module] sound_module initialized: {}".format(self.sound_module))
            print("[move_module] sound_module.external_follow_active = {}".format(getattr(self.sound_module, 'external_follow_active', 'NOT_FOUND')))
        else:
            print("[move_module] WARNING: sound_module is None")
        self.th = threading.Thread(target=self.watchdog)
        self.th.start()

    def watchdog(self):
        while self.watchdoging:
            if (not self.blocking_move) and (self.time + 1 < time.time()):
                self.motion.stopMove()
                self.time = time.time()

    def spin_around(self, times):
        if not self.spinning:
            self.spinning = True
            self.motion.moveToward(0.0, 0.0, 0.5)
            self.spinning = False

    def move(self, data):
        a = data.decode()
        b = str(a)
        print("[move_module] recv: ",b)
        if b[0] == '[':
            if b[1] == ']':
              print("[move_module] STOP")
              # Disable external follow mode in sound_module
              if self.sound_module:
                  try:
                      if self.sound_module.external_follow_active:
                          print("[move_module] Deactivating external follow mode")
                          self.sound_module.external_follow_active = False
                  except AttributeError:
                      print("[move_module] Warning: sound_module has no external_follow_active attribute")
              else:
                  print("[move_module] Warning: sound_module not available")
              self.motion.stopMove()
              self.time = time.time()
            else:
              actions = eval(data.decode())
              print("[move_module] list: ", actions)
              
              is_keyboard = any(action in [ord("w"), ord("a"), ord("s"), ord("d"), ord("q"), ord("e")] for action in actions)
              
              if is_keyboard:
                  print("[move_module] KEYBOARD")
                  x = 0.0
                  y = 0.0
                  theta = 0.0
                  for action in actions:
                      if action == ord("w"):
                          x += 1 / self.dt
                      elif action == ord("a"):
                          y += 1 / self.dt
                      elif action == ord("s"):
                          x -= 1 / self.dt
                      elif action == ord("d"):
                          y -= 1 / self.dt
                      elif action == ord("q"):
                          theta += 1 / self.dt
                      elif action == ord("e"):
                          theta -= 1 / self.dt
                  print("[move_module] KEYBOARD moveToward x={:.2f} y={:.2f} theta={:.2f}".format(x, y, theta))
                  self.motion.moveToward(x, y, theta)
                  self.time = time.time()
              else:
                  print("[move_module] PID_FOLLOW")
                  # Enable external follow mode in sound_module
                  if self.sound_module:
                      try:
                          if not self.sound_module.external_follow_active:
                              print("[move_module] Activating external follow mode")
                              self.sound_module.external_follow_active = True
                      except AttributeError:
                          print("[move_module] Warning: sound_module has no external_follow_active attribute")
                  else:
                      print("[move_module] Warning: sound_module not available")
                  if len(actions) >= 3:
                      x = actions[0] / 100.0
                      y = actions[1] / 100.0
                      theta = actions[2] / 100.0
                  else:
                      x = actions[0] / 100.0 if len(actions) > 0 else 0.0
                      y = actions[1] / 100.0 if len(actions) > 1 else 0.0
                      theta = actions[2] / 100.0 if len(actions) > 2 else 0.0
                  print("[move_module] PID_FOLLOW moveToward x={:.2f} y={:.2f} theta={:.2f}".format(x, y, theta))
                  self.motion.moveToward(x, y, theta)
                  self.time = time.time()

        else:
            command = json.loads(data)
            print(command)
            intent = command.get("intent")
            slots = command.get("params", {})
            print(intent)
            if intent == u'spin_around':
                times = slots.get("times", 1)
                self.spin_rotate(times)
            elif intent == u'left_spin_rotate':
                degrees = slots.get("degrees", 90)
                self.left_spin_rotate(degrees)
            elif intent == u'right_spin_rotate':
                degrees = slots.get("degrees", 90)
                self.right_spin_rotate(degrees)
            elif intent == u'forward':
                distance = slots.get("distance", 1.0)
                self.forward(distance)
            elif intent == u'retreat':
                distance = slots.get("distance", 1.0)
                self.retreat(distance)
            

    def spin_rotate(self,times = 1):
        if not self.rotating:
            self.rotating = True
            print("spin_rotate")
            # moveTo is limited to theta in [-pi, pi]. For full turns, split into pi segments.
            try:
                self.blocking_move = True
                segments = int(round(float(times) * 2.0))
                if segments <= 0:
                    segments = 2
                for _ in range(segments):
                    self.time = time.time()
                    ok = self.motion.moveTo(0.0, 0.0, -math.pi)
                    if not ok:
                        break
            finally:
                self.blocking_move = False
            self.rotating = False

    def left_spin_rotate(self, degrees=90):
        """
        Turn left by a given angle.

        :param degrees: rotation angle (degrees)
        """
        if not self.rotating:
            self.rotating = True
            print("left_spin_rotate {}degrees".format(degrees))
            theta = math.radians(abs(float(degrees)))
            # moveTo expects theta in radians within [-pi, pi]
            theta = min(theta, math.pi)
            try:
                self.blocking_move = True
                self.time = time.time()
                self.motion.moveTo(0.0, 0.0, theta)
            finally:
                self.blocking_move = False
            self.rotating = False

    def right_spin_rotate(self, degrees=90):
        """
        Turn right by a given angle.

        :param degrees: rotation angle (degrees)
        """
        if not self.rotating:
            self.rotating = True
            print("right_spin_rotate {}degrees".format(degrees))
            theta = math.radians(abs(float(degrees)))
            theta = min(theta, math.pi)
            try:
                self.blocking_move = True
                self.time = time.time()
                self.motion.moveTo(0.0, 0.0, -theta)
            finally:
                self.blocking_move = False
            self.rotating = False

    def forward(self, m=1.0):
        """
        Move forward by a given distance.

        :param m: distance (meters). Internal speed uses 1.0 m/s.
        """
        if not self.forwarding:
            self.forwarding = True
            m = abs(float(m))
            print("forward {}m".format(m))
            try:
                self.blocking_move = True
                self.time = time.time()
                self.motion.moveTo(m, 0.0, 0.0)
            finally:
                self.blocking_move = False
            self.forwarding = False

    def retreat(self, m=1.0):
        """
        Move backward by a given distance.

        :param m: distance (meters). Internal speed uses 0.5 m/s.
        """
        if not self.forwarding:
            self.forwarding = True
            m = abs(float(m))
            print("retreat {}m".format(m))
            try:
                self.blocking_move = True
                self.time = time.time()
                self.motion.moveTo(-m, 0.0, 0.0)
            finally:
                self.blocking_move = False
            self.forwarding = False

    def stop(self):
        self.motion.stopMove()
        self.watchdoging = False