import os
import math
import threading
import time
from typing import Any, Dict, Optional, Set


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    return value not in {"0", "false", "no", "off", ""}


class _GenericStubService:
    def __init__(self, service_name: str):
        self._service_name = service_name
        self._warned: Set[str] = set()

    def __getattr__(self, attr: str):
        if attr not in self._warned:
            print(f"[sim][stub] {self._service_name}.{attr}() ignored")
            self._warned.add(attr)

        def _noop(*_args: Any, **_kwargs: Any):
            if attr.startswith("is"):
                return False
            if attr in {"getState"}:
                return "safeguard"
            return None

        return _noop


class StubAutonomousLife:
    def getState(self):
        return "safeguard"

    def setState(self, _state: str):
        return None

    def setSafeguardEnabled(self, _name: str, _enabled: bool):
        return None

    def setAutonomousAbilityEnabled(self, _name: str, _enabled: bool):
        return None


class StubToggleService:
    def isEnabled(self):
        return False

    def setEnabled(self, _enabled: bool):
        return None


class StubLaser:
    def laserOFF(self):
        return None


class StubBehaviorManager:
    def isBehaviorInstalled(self, _name: str):
        return False

    def isBehaviorRunning(self, _name: str):
        return False

    def runBehavior(self, _name: str, _async: bool = False):
        print(f"[sim][stub] ALBehaviorManager.runBehavior({_name}) ignored")
        return True

    def stopBehavior(self, _name: str):
        return True

    def getInstalledBehaviors(self):
        return []


class StubAudioRecorder:
    def stopMicrophonesRecording(self):
        return None

    def startMicrophonesRecording(self, *_args: Any, **_kwargs: Any):
        return None


class StubTextToSpeech:
    def say(self, text: str):
        print(f"[sim][tts] {text}")
        return None


class StubAudioPlayer:
    def loadFile(self, _path: str):
        return 0

    def play(self, _file_id: int):
        return None


class StubMemory:
    def getData(self, _key: str):
        return None

    def insertData(self, _key: str, _value: Any):
        return None


class StubSubscribable:
    def subscribe(self, _name: str):
        return None

    def unsubscribe(self, _name: str):
        return None


class StubPhotoCapture:
    def takePicture(self, *_args: Any, **_kwargs: Any):
        return None


class StubVideoDevice:
    def unsubscribe(self, _name: str):
        return None

    def subscribeCamera(self, *_args: Any, **_kwargs: Any):
        raise RuntimeError("ALVideoDevice is not supported in sim mode")

    def getImageRemote(self, _handle: str):
        return None


class SimALMotion:
    def __init__(self, pepper_robot: Any):
        self._pepper = pepper_robot
        # qiBullet PepperVirtual.moveTo behaves like an absolute target (world frame) in practice.
        # NAOqi ALMotion.moveTo is relative to the current robot pose. We emulate that here.
        self._moveto_absolute_backend = _env_flag("PEPPER_SIM_MOVETO_ABSOLUTE", True)
        self._pose_lock = threading.Lock()
        # World-frame pose relative to spawn origin (x, y, theta)
        self._pose = [0.0, 0.0, 0.0]

    @staticmethod
    def _wrap_pi(theta: float) -> float:
        # Wrap to [-pi, pi] for backends that expect it.
        return (theta + math.pi) % (2.0 * math.pi) - math.pi

    def moveInit(self):
        return None

    def setExternalCollisionProtectionEnabled(self, *_args: Any, **_kwargs: Any):
        return None

    def setCollisionProtectionEnabled(self, *_args: Any, **_kwargs: Any):
        return None

    def setIdlePostureEnabled(self, *_args: Any, **_kwargs: Any):
        return None

    def setBreathEnabled(self, *_args: Any, **_kwargs: Any):
        return None

    def setMoveArmsEnabled(self, *_args: Any, **_kwargs: Any):
        return None

    def setSmartStiffnessEnabled(self, *_args: Any, **_kwargs: Any):
        return None

    def openHand(self, which: str):
        # NAOqi uses [0..1] for hand open/close.
        try:
            return self.setAngles(which, 1.0, 0.2)
        except Exception:
            return None

    def closeHand(self, which: str):
        try:
            return self.setAngles(which, 0.0, 0.2)
        except Exception:
            return None

    def waitUntilMoveIsFinished(self):
        return None

    def stopMove(self):
        fn = getattr(self._pepper, "stopMove", None)
        if callable(fn):
            return fn()

        # Fallbacks for other backends
        fn = getattr(self._pepper, "setBaseVelocity", None)
        if callable(fn):
            return fn(0.0, 0.0, 0.0)
        fn = getattr(self._pepper, "setVelocity", None)
        if callable(fn):
            return fn(0.0, 0.0, 0.0)
        fn = getattr(self._pepper, "move", None)
        if callable(fn):
            return fn(0.0, 0.0, 0.0)

        return None

    def setAngles(self, names: Any, angles: Any, speeds: Any):
        fn = getattr(self._pepper, "setAngles", None)
        if callable(fn):
            try:
                return fn(names, angles, speeds)
            except Exception:
                # Some backends error out on unknown joints. Try per-joint fallback.
                pass

            if isinstance(names, (list, tuple)) and isinstance(angles, (list, tuple)):
                for joint_name, joint_angle in zip(names, angles):
                    try:
                        fn(joint_name, joint_angle, speeds)
                    except Exception:
                        continue
                return None
        return None

    def changeAngles(self, name: str, delta: float, speed: float):
        getter = getattr(self._pepper, "getAngles", None)
        if callable(getter):
            try:
                current = getter(name)
                if isinstance(current, (list, tuple)):
                    current = current[0] if current else 0.0
                return self.setAngles(name, float(current) + float(delta), speed)
            except Exception:
                pass
        return self.setAngles(name, float(delta), speed)

    def angleInterpolation(self, names: Any, angles: Any, *_args: Any, **_kwargs: Any):
        # Minimal: just apply target joint angles.
        return self.setAngles(names, angles, 1.0)

    def angleInterpolationBezier(self, names: Any, times_list: Any, angles_list: Any):
        """Very small subset of NAOqi API used by pepper_module/action.py.

        `names`: list[str]
        `times_list`: list[list[float]] (per joint)
        `angles_list`: list[list[float]] (per joint), radians

        We approximate by stepping through the knot points in time and calling setAngles.
        """

        if not names:
            return None

        # Normalize single joint
        if isinstance(names, str):
            names = [names]
            times_list = [times_list]
            angles_list = [angles_list]

        try:
            num_joints = len(names)
            if num_joints == 0:
                return None
            # Determine number of keyframes (use first joint)
            keyframe_count = len(times_list[0])
            if keyframe_count <= 0:
                return None

            # Defensive: if angles_list shape mismatches, fall back to final pose
            for j in range(num_joints):
                if len(times_list[j]) != keyframe_count or len(angles_list[j]) != keyframe_count:
                    final_angles = [float(seq[-1]) for seq in angles_list]
                    return self.setAngles(names, final_angles, 1.0)

            # Playback keyframes
            start_t = time.time()
            base_times = [float(t) for t in times_list[0]]
            for k in range(keyframe_count):
                target = [float(angles_list[j][k]) for j in range(num_joints)]
                self.setAngles(names, target, 1.0)

                if k + 1 < keyframe_count:
                    # Sleep until next keyframe time (best-effort)
                    next_dt = max(0.0, base_times[k + 1] - base_times[k])
                    # Account for drift roughly
                    elapsed = time.time() - start_t
                    planned = base_times[k + 1]
                    sleep_s = max(0.0, planned - elapsed)
                    time.sleep(min(next_dt, sleep_s) if sleep_s > 0 else next_dt)
            return None
        except Exception:
            # Keep simulation robust: ignore motion errors.
            return None

    def moveTo(
        self,
        x: float,
        y: float,
        theta: float,
        frame: Optional[int] = None,
        _async: bool = False,
        speed: Optional[float] = None,
    ):
        fn = getattr(self._pepper, "moveTo", None)
        if not callable(fn):
            return False

        # If the backend moveTo is absolute, convert NAOqi-style relative moveTo into an absolute goal.
        if self._moveto_absolute_backend:
            with self._pose_lock:
                cur_x, cur_y, cur_theta = self._pose
                dx = float(x)
                dy = float(y)
                dtheta = float(theta)

                world_dx = math.cos(cur_theta) * dx - math.sin(cur_theta) * dy
                world_dy = math.sin(cur_theta) * dx + math.cos(cur_theta) * dy

                goal_x = cur_x + world_dx
                goal_y = cur_y + world_dy
                goal_theta = self._wrap_pi(cur_theta + dtheta)

                # Update internal pose estimate immediately (best-effort).
                self._pose = [goal_x, goal_y, goal_theta]

            x, y, theta = goal_x, goal_y, goal_theta

        try:
            return fn(x, y, theta, frame=frame, _async=_async, speed=speed)
        except TypeError:
            try:
                return fn(x, y, theta)
            except Exception:
                return False

    def moveToward(self, x: float, y: float, theta: float):
        # qiBullet PepperVirtual uses move(x, y, theta) for velocity-like commands.
        fn = getattr(self._pepper, "move", None)
        if callable(fn):
            try:
                return fn(x, y, theta)
            except Exception:
                pass

        # Other backends
        fn = getattr(self._pepper, "moveToward", None)
        if callable(fn):
            try:
                return fn(x, y, theta)
            except Exception:
                pass

        fn = getattr(self._pepper, "setBaseVelocity", None)
        if callable(fn):
            return fn(x, y, theta)

        fn = getattr(self._pepper, "setVelocity", None)
        if callable(fn):
            return fn(x, y, theta)

        return None


class SimALRobotPosture:
    def __init__(self, pepper_robot: Any):
        self._pepper = pepper_robot

    def goToPosture(self, name: str, speed: float):
        fn = getattr(self._pepper, "goToPosture", None)
        if callable(fn):
            try:
                return fn(name, speed)
            except Exception:
                return False
        return True


class FakeSession:
    def __init__(self, pepper_robot: Any):
        self._pepper = pepper_robot
        self._services: Dict[str, Any] = {
            "ALMotion": SimALMotion(pepper_robot),
            "ALRobotPosture": SimALRobotPosture(pepper_robot),
            "ALAutonomousLife": StubAutonomousLife(),
            "ALBasicAwareness": StubToggleService(),
            "ALBackgroundMovement": StubToggleService(),
            "ALListeningMovement": StubToggleService(),
            "ALSpeakingMovement": StubToggleService(),
            "ALLaser": StubLaser(),
            "ALBehaviorManager": StubBehaviorManager(),
            "ALAudioRecorder": StubAudioRecorder(),
            "ALTextToSpeech": StubTextToSpeech(),
            "ALAudioPlayer": StubAudioPlayer(),
            "ALMemory": StubMemory(),
            "ALSoundLocalization": StubSubscribable(),
            "ALFaceDetection": StubSubscribable(),
            "ALPeoplePerception": StubSubscribable(),
            "ALPhotoCapture": StubPhotoCapture(),
            "ALVideoDevice": StubVideoDevice(),
        }

    def service(self, name: str):
        if name not in self._services:
            self._services[name] = _GenericStubService(name)
        return self._services[name]


class FakeApplication:
    def __init__(self, session: FakeSession):
        self.session = session

    def start(self):
        return None

    def stop(self):
        return None


def connect_application(
    *,
    mode: str = "real",
    ip: Optional[str] = None,
    port: int = 9559,
    gui: Optional[bool] = None,
    spawn_ground_plane: Optional[bool] = None,
) -> Any:
    """Return an object with `.session` compatible with `qi.Application`.

    - mode=real: returns `qi.Application` (requires NAOqi `qi` installed)
    - mode=sim : returns `FakeApplication` backed by qiBullet

    Configure simulation via env vars:
    - PEPPER_SIM_GUI=1/0
    - PEPPER_SIM_GROUND=1/0
    """

    mode = (mode or "real").strip().lower()
    if mode == "real":
        if not ip:
            raise ValueError("ip is required for mode=real")
        import qi  # type: ignore

        return qi.Application(url=f"tcp://{ip}:{int(port)}")

    if mode == "sim":
        if gui is None:
            gui = _env_flag("PEPPER_SIM_GUI", default=True)
        if spawn_ground_plane is None:
            spawn_ground_plane = _env_flag("PEPPER_SIM_GROUND", default=True)

        try:
            from qibullet import SimulationManager  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "qibullet is required for simulation. Install with: pip install qibullet pybullet numpy"
            ) from e

        sim_manager = SimulationManager()
        client_id = sim_manager.launchSimulation(gui=bool(gui))
        pepper_robot = sim_manager.spawnPepper(
            client_id, spawn_ground_plane=bool(spawn_ground_plane)
        )
        app = FakeApplication(FakeSession(pepper_robot))
        # Keep references so objects don't get GC'd immediately.
        app._sim_manager = sim_manager  # type: ignore[attr-defined]
        app._sim_client_id = client_id  # type: ignore[attr-defined]
        app._sim_pepper = pepper_robot  # type: ignore[attr-defined]
        return app

    raise ValueError("mode must be 'real' or 'sim'")
