import importlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class TrajectoryFrame:
    frame_number: int
    video_timestamp: float
    joint_names: List[str]
    angles: List[float]
    source: Optional[str] = None


def load_jsonl_trajectory(path: Union[str, Path]) -> List[TrajectoryFrame]:
    """Load a JSONL trajectory.

    Expected per-line JSON fields:
      - video_timestamp: float (seconds)
      - joint_names: list[str]
      - angles: list[float] (radians)
    Optional:
      - frame_number: int
      - source: str
    """
    path = Path(path)
    frames: List[TrajectoryFrame] = []
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            frames.append(
                TrajectoryFrame(
                    frame_number=int(obj.get("frame_number", ln - 1)),
                    video_timestamp=float(obj["video_timestamp"]),
                    joint_names=list(obj["joint_names"]),
                    angles=list(obj["angles"]),
                    source=obj.get("source"),
                )
            )
    frames.sort(key=lambda x: x.video_timestamp)
    return frames


def load_name_map(path: Optional[Union[str, Path]]) -> Optional[Dict[str, str]]:
    """Load an optional joint name mapping JSON file.

    File format:
      {"left_shoulder_pitch": "LShoulderPitch", ...}

    If not provided, returns None.
    """
    if not path:
        return None
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def apply_name_map(joint_names: List[str], name_map: Optional[Dict[str, str]]) -> List[str]:
    if not name_map:
        return joint_names
    return [name_map.get(n, n) for n in joint_names]


class JointCommandSink:
    """Adapter that sends (joint_names, angles) to a target executor.

    Your simulator/executor only needs to implement ONE of these methods:
      - send(joint_names, angles)
      - set_joint_positions(joint_names, angles)
      - apply(joint_names, angles)
      - handle({"joint_names": [...], "angles": [...]})
      - setAngles(joint_names, angles, speed)
    """

    def __init__(self, target: Any, speed: float = 1.0, dry_run: bool = False):
        self.target = target
        self.speed = float(speed)
        self.dry_run = bool(dry_run)

    def send(self, joint_names: List[str], angles: List[float]) -> None:
        if self.dry_run:
            print({"joint_names": joint_names, "angles": angles})
            return

        t = self.target
        if hasattr(t, "send") and callable(getattr(t, "send")):
            t.send(joint_names, angles)
            return
        if hasattr(t, "set_joint_positions") and callable(getattr(t, "set_joint_positions")):
            t.set_joint_positions(joint_names, angles)
            return
        if hasattr(t, "apply") and callable(getattr(t, "apply")):
            t.apply(joint_names, angles)
            return
        if hasattr(t, "handle") and callable(getattr(t, "handle")):
            t.handle({"joint_names": joint_names, "angles": angles})
            return
        if hasattr(t, "setAngles") and callable(getattr(t, "setAngles")):
            t.setAngles(joint_names, angles, self.speed)
            return

        raise TypeError(
            "Executor does not support joint command sending. "
            "Implement one of: send / set_joint_positions / apply / handle / setAngles"
        )


class TrajectoryPlayer:
    """Plays a trajectory according to the frames' video_timestamp."""

    def __init__(self, sink: JointCommandSink):
        self.sink = sink

    def play(
        self,
        frames: List[TrajectoryFrame],
        speed: float = 1.0,
        start_at: float = 0.0,
        stop_at: Optional[float] = None,
        name_map: Optional[Dict[str, str]] = None,
    ) -> None:
        if not frames:
            print("Trajectory is empty.")
            return

        speed = max(float(speed), 1e-6)

        # Find start frame
        i0 = 0
        while i0 < len(frames) and frames[i0].video_timestamp < start_at:
            i0 += 1
        if i0 >= len(frames):
            print("start_at is out of range.")
            return

        t0_video = frames[i0].video_timestamp
        t0_wall = time.perf_counter()

        for i in range(i0, len(frames)):
            fr = frames[i]
            if stop_at is not None and fr.video_timestamp > stop_at:
                break

            target_wall = t0_wall + (fr.video_timestamp - t0_video) / speed
            while True:
                now = time.perf_counter()
                dt = target_wall - now
                if dt <= 0:
                    break
                time.sleep(min(dt, 0.002))

            joint_names = apply_name_map(fr.joint_names, name_map)
            self.sink.send(joint_names, fr.angles)


def _import_attr(spec: str) -> Any:
    """Import an attribute from 'module.submodule:attr'."""
    if ":" not in spec:
        raise ValueError("Spec must be 'module.submodule:attr'")
    mod_name, attr_name = spec.split(":", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, attr_name)


def build_sink_from_executor_spec(
    executor_spec: str,
    speed: float = 1.0,
    dry_run: bool = False,
) -> JointCommandSink:
    """Build a JointCommandSink from executor spec.

    executor_spec: 'module:attr'
      - if attr is an object instance -> used directly
      - if attr is a class or factory -> called with no args

    If your executor needs parameters, wrap it with a no-arg factory.
    """
    attr = _import_attr(executor_spec)

    if callable(attr):
        try:
            target = attr()
        except TypeError as e:
            raise TypeError(
                f"Cannot instantiate executor from {executor_spec} with no args. "
                f"Provide a no-arg factory function instead. Original error: {e}"
            )
    else:
        target = attr

    return JointCommandSink(target=target, speed=speed, dry_run=dry_run)
