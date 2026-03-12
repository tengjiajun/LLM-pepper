#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

PEPPER_JOINT_ORDER = [
    "LShoulderPitch",
    "LShoulderRoll",
    "LElbowYaw",
    "LElbowRoll",
    "RShoulderPitch",
    "RShoulderRoll",
    "RElbowYaw",
    "RElbowRoll",
    "HipPitch",
]

PEPPER_NEUTRAL_FOR_UNITREE_ZERO_DEG: Dict[str, float] = {
    "LShoulderPitch": 90.0,
    "LShoulderRoll": 0.0,
    "LElbowYaw": -90.0,
    "LElbowRoll": -90.0,
    "RShoulderPitch": 90.0,
    "RShoulderRoll": 0.0,
    "RElbowYaw": 90.0,
    "RElbowRoll": 90.0,
    "HipPitch": 0.0,
}

PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD: Dict[str, float] = {
    name: math.radians(value_deg) for name, value_deg in PEPPER_NEUTRAL_FOR_UNITREE_ZERO_DEG.items()
}

# Unitree H1 (MuJoCo actuator names used in tools/mujoco_sim_view.py)
# Mapping format: dst_name -> (src_pepper_joint, scale, offset)
UNITREE_H1_UPPER_BODY_MAP: Dict[str, Tuple[str, float, float]] = {
    # Unitree all-zero pose corresponds to the following discretized Pepper pose:
    # near 0deg -> 0deg, near +/-90deg -> +/-90deg.
    "left_shoulder_pitch": ("LShoulderPitch", 1.0, -PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["LShoulderPitch"]),
    "left_shoulder_roll": ("LShoulderRoll", 1.0, -PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["LShoulderRoll"]),
        "left_shoulder_yaw": ("LElbowYaw", -1.0, -PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["LElbowYaw"]),
    "right_shoulder_pitch": ("RShoulderPitch", 1.0, -PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["RShoulderPitch"]),
    "right_shoulder_roll": ("RShoulderRoll", 1.0, -PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["RShoulderRoll"]),
    "right_shoulder_yaw": ("RElbowYaw", -1.0, PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["RElbowYaw"]),
    # Pepper elbow roll neutral is also around +/-90deg in the matched Unitree zero pose.
    "left_elbow": ("LElbowRoll", -1.0, -PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["LElbowRoll"]),
    "right_elbow": ("RElbowRoll", -1.0, PEPPER_NEUTRAL_FOR_UNITREE_ZERO_RAD["RElbowRoll"]),
    "torso": ("HipPitch", 1.0, 0.0),
}


def _load_frames(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("输入文件格式错误：期望最外层为数组(list)")
    return data


def _extract_pepper_angles(frame: dict) -> Dict[str, float]:
    angles = frame.get("angles") or {}
    angle_dict = angles.get("angle_dict_rad") or {}
    if not isinstance(angle_dict, dict):
        return {}
    out: Dict[str, float] = {}
    for name in PEPPER_JOINT_ORDER:
        val = angle_dict.get(name)
        if isinstance(val, (int, float)):
            out[name] = float(val)
    return out


def convert(input_json: Path, output_dir: Path, sample_fps: float) -> dict:
    frames = _load_frames(input_json)
    output_dir.mkdir(parents=True, exist_ok=True)

    pepper_jsonl = output_dir / "pepper_pose_stream.jsonl"
    unitree_jsonl = output_dir / "unitree_h1_upper_body_trajectory.jsonl"

    sample_dt = 1.0 / sample_fps if sample_fps > 0 else 0.0
    next_t = 0.0

    processed = 0
    pepper_written = 0
    unitree_written = 0

    with pepper_jsonl.open("w", encoding="utf-8") as f_pepper, unitree_jsonl.open("w", encoding="utf-8") as f_unitree:
        for frame in frames:
            processed += 1
            if not frame.get("success", False):
                continue

            t = float(frame.get("video_timestamp", 0.0))
            if sample_dt > 0 and t + 1e-9 < next_t:
                continue
            if sample_dt > 0:
                next_t += sample_dt

            pepper_map = _extract_pepper_angles(frame)
            if len(pepper_map) < len(PEPPER_JOINT_ORDER):
                continue

            pepper_msg = {
                "function": "open_external_video",
                "frame_number": int(frame.get("frame_number", -1)),
                "video_timestamp": t,
                "joint_names": PEPPER_JOINT_ORDER,
                "angles": [pepper_map[name] for name in PEPPER_JOINT_ORDER],
            }
            f_pepper.write(json.dumps(pepper_msg, ensure_ascii=False) + "\n")
            pepper_written += 1

            unitree_names: List[str] = []
            unitree_angles: List[float] = []
            for dst_name, (src_name, scale, offset) in UNITREE_H1_UPPER_BODY_MAP.items():
                src_val = pepper_map.get(src_name)
                if src_val is None:
                    continue
                unitree_names.append(dst_name)
                unitree_angles.append(scale * src_val + offset)

            unitree_msg = {
                "frame_number": int(frame.get("frame_number", -1)),
                "video_timestamp": t,
                "joint_names": unitree_names,
                "angles": unitree_angles,
                "source": "pepper_angle_map",
            }
            f_unitree.write(json.dumps(unitree_msg, ensure_ascii=False) + "\n")
            unitree_written += 1

    meta = {
        "input": str(input_json),
        "processed_frames": processed,
        "pepper_written": pepper_written,
        "unitree_written": unitree_written,
        "pepper_output": str(pepper_jsonl),
        "unitree_output": str(unitree_jsonl),
        "joint_order_pepper": PEPPER_JOINT_ORDER,
        "unitree_map": UNITREE_H1_UPPER_BODY_MAP,
    }

    meta_path = output_dir / "conversion_meta.json"
    with meta_path.open("w", encoding="utf-8") as f_meta:
        json.dump(meta, f_meta, indent=2, ensure_ascii=False)

    meta["meta_output"] = str(meta_path)
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="将 video_pose_results.json 转换为 Pepper/Unitree 可用关节轨迹")
    parser.add_argument("input", help="输入 JSON 文件路径（如 video_pose_results.json）")
    parser.add_argument("--out-dir", default="converted_outputs", help="输出目录")
    parser.add_argument("--fps", type=float, default=10.0, help="输出采样频率（默认 10Hz）")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    if not input_path.exists():
        raise SystemExit(f"输入文件不存在: {input_path}")

    result = convert(input_path, out_dir, sample_fps=args.fps)
    print("转换完成:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
