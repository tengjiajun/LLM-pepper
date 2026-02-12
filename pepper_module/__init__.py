# coding=utf-8
# ����Ĵ��벻Ҫ�޸ģ�
import os
import time

from util.Config import *
from communication.Client import Client

import qi

app = qi.Application(url="tcp://" + PEPPER_IP + ":9559")
app.start()

AutonomousLife = app.session.service("ALAutonomousLife")
if AutonomousLife.getState() != "safeguard":
    print("AutonomousLife off")
    AutonomousLife.setState("safeguard")
AutonomousLife.setSafeguardEnabled("RobotPushed", False)
AutonomousLife.setSafeguardEnabled("RobotFell", False)
AutonomousLife.setSafeguardEnabled("RobotMoved", False)
AutonomousLife.setAutonomousAbilityEnabled("All", False)

BasicAwareness = app.session.service("ALBasicAwareness")
if BasicAwareness.isEnabled():
    print("BasicAwareness off")
    BasicAwareness.setEnabled(False)

BackgroundMovement = app.session.service("ALBackgroundMovement")
if BackgroundMovement.isEnabled():
    print("BackgroundMovement off")
    BackgroundMovement.setEnabled(False)

ListeningMovement = app.session.service("ALListeningMovement")
if ListeningMovement.isEnabled():
    print("ListeningMovement off")
    ListeningMovement.setEnabled(False)

SpeakingMovement = app.session.service("ALSpeakingMovement")
if SpeakingMovement.isEnabled():
    print("SpeakingMovement off")
    SpeakingMovement.setEnabled(False)

Motion = app.session.service("ALMotion")
Motion.setExternalCollisionProtectionEnabled("All", False)
Motion.setCollisionProtectionEnabled("Arms", False)
# Motion.setTangentialSecurityDistance(0.01)
# Motion.setOrthogonalSecurityDistance(0.002)
# Motion.setTangentialSecurityDistance(0.002)
Motion.setIdlePostureEnabled("Body", False)
Motion.setIdlePostureEnabled("Legs", False)
Motion.setIdlePostureEnabled("Arms", False)
Motion.setIdlePostureEnabled("Head", False)
Motion.setBreathEnabled("Body", False)
Motion.setMoveArmsEnabled(False, False)
Motion.setSmartStiffnessEnabled(False)
Motion.openHand("RHand")
Motion.openHand("LHand")

Laser = app.session.service("ALLaser")
Laser.laserOFF()

from pepper_module.sound_module import sound_module

soundSocket = Client(SERVER_IP, SERVER_PORT, "sound", "sender", None)
soundModule = sound_module(app, soundSocket, 2)
soundSocket.set_callback(soundModule.say)

from pepper_module.move_module import move_module

moveModule = move_module(app, 1, sound_module=soundModule)
moveSocket = Client(SERVER_IP, SERVER_PORT, "move", "receiver", moveModule.move)

from pepper_module.action_module_both import action_module_both

actionModule_both = action_module_both(app, 50, 1)
actionSocket_both = Client(SERVER_IP, SERVER_PORT, "active_2", "receiver", actionModule_both.action)

from pepper_module.action_module_single import action_module_single

actionModule_single = action_module_single(app, 50, 1)
actionSocket_single = Client(SERVER_IP, SERVER_PORT, "active_1", "receiver", actionModule_single.action)

from pepper_module.head_module import head_module

headModule = head_module(app, 50, 1)
headSocket = Client(SERVER_IP, SERVER_PORT, "head", "receiver", headModule.head)

from pepper_module.body_module import body_module

bodyModule = body_module(app, 50, 1)
bodySocket = Client(SERVER_IP, SERVER_PORT, "body", "receiver", bodyModule.body)

from pepper_module.pose_stream import PoseStreamModule

poseStreamModule = PoseStreamModule(app, interval_sec=0.02, speed=0.1)
poseStreamSocket = Client(SERVER_IP, SERVER_PORT, "pose_stream", "receiver", poseStreamModule.handle)


from pepper_module.wrist_module import wrist_module

wristModule = wrist_module(app, 50, 1)
wristSocket = Client(SERVER_IP, SERVER_PORT, "wrist", "receiver", wristModule.wrist)

from pepper_module.video_module import video_module

videoSocket = Client(SERVER_IP, SERVER_PORT, "video", "sender", None)
try:
    videoModule = video_module(app, videoSocket)
except:
    pass
# try:
#     raw_input()
# except:
#     pass


def _env_flag(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip().lower()
    return v not in {"0", "false", "no", "off", ""}


def _shutdown():
    try:
        moveSocket.stop()
    except Exception:
        pass
    try:
        videoSocket.stop()
    except Exception:
        pass


_keepalive = _env_flag("PEPPER_KEEPALIVE", True)
if _keepalive:
    print("[LLM-pepper] Pepper started. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

_shutdown()
