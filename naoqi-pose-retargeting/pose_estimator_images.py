#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""从图片序列估计人体姿态，并导出：

1) 每张图片的骨架叠加图（用于人工核对动作是否正确）
2) 与 pose_estimator_video.py 相同结构的 pose_results.json
3) 自动转换为 Unitree H1 上半身关节轨迹 JSONL（converted_outputs/unitree_h1_upper_body_trajectory.jsonl）

默认会读取仓库根目录的 picture/ 下所有图片（按文件名排序）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List

import cv2 as cv


def _ensure_paths() -> None:
    # Make imports like `from utils import ...` work consistently.
    this_dir = Path(__file__).resolve().parent
    if str(this_dir) not in sys.path:
        sys.path.insert(0, str(this_dir))
    tools_dir = this_dir / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))


_ensure_paths()

# Reuse the same estimator + output schema as the video pipeline.
from pose_estimator_video import VideoPoseEstimator  # noqa: E402
import convert_pose_results  # noqa: E402


def _is_image_file(p: Path) -> bool:
    return p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _collect_images(input_dir: Path, inputs: List[str] | None) -> List[Path]:
    if inputs:
        paths = [Path(x).expanduser() for x in inputs]
        return [p if p.is_absolute() else (Path.cwd() / p) for p in paths]

    if not input_dir.exists():
        raise FileNotFoundError(f"input-dir not found: {input_dir}")

    imgs = [p for p in sorted(input_dir.iterdir()) if p.is_file() and _is_image_file(p)]
    return imgs


def estimate_images(
    image_paths: List[Path],
    fps: float,
    out_json: Path,
    skeleton_dir: Path,
    model_complexity: int = 1,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> List[dict]:
    if fps <= 0:
        raise ValueError("fps must be > 0")

    skeleton_dir.mkdir(parents=True, exist_ok=True)

    estimator = VideoPoseEstimator(
        model_complexity=model_complexity,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )

    results_list: List[dict] = []
    t_start = time.time()

    for i, img_path in enumerate(image_paths):
        img_path = img_path.resolve()
        image = cv.imread(str(img_path))
        t_video = float(i) / float(fps)

        if image is None:
            frame_result = {
                "success": False,
                "frame_number": i,
                "video_timestamp": t_video,
                "process_timestamp": time.time() - t_start,
                "image_w": 0,
                "image_h": 0,
                "pose_landmarks2d": [],
                "pose_world_landmarks3d": [],
                "quality": {
                    "mean_visibility": 0.0,
                    "landmark_count_2d": 0,
                    "landmark_count_3d": 0,
                },
                "message": f"无法读取图片: {img_path}",
            }
            results_list.append(frame_result)
            continue

        success, pose_results = estimator.process_image(image)
        if success:
            angle_result = estimator.calculate_angles(pose_results.pose_world_landmarks)
            limit_result = estimator.check_limits(angle_result["angles_rad"])
            landmarks_2d = estimator.serialize_landmarks_2d(pose_results.pose_landmarks)
            landmarks_3d = estimator.serialize_landmarks_3d(pose_results.pose_world_landmarks)

            visibility_values = [p.get("visibility", 0.0) for p in landmarks_2d]
            mean_visibility = float(sum(visibility_values) / len(visibility_values)) if visibility_values else 0.0

            frame_result = {
                "success": True,
                "frame_number": i,
                "video_timestamp": t_video,
                "process_timestamp": time.time() - t_start,
                "image_w": int(image.shape[1]),
                "image_h": int(image.shape[0]),
                "pose_landmarks2d": landmarks_2d,
                "pose_world_landmarks3d": landmarks_3d,
                "quality": {
                    "mean_visibility": mean_visibility,
                    "landmark_count_2d": len(landmarks_2d),
                    "landmark_count_3d": len(landmarks_3d),
                },
                "angles": angle_result,
                "safety_check": limit_result,
                "source_image": str(img_path),
            }
            results_list.append(frame_result)

            # Save skeleton overlay image
            draw_frame = image.copy()
            try:
                if pose_results and pose_results.pose_landmarks:
                    estimator.mp_drawing.draw_landmarks(
                        draw_frame,
                        pose_results.pose_landmarks,
                        estimator.mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=estimator.mp_drawing_styles.get_default_pose_landmarks_style(),
                    )
            except Exception:
                # Keep going even if drawing fails.
                pass

            cv.putText(
                draw_frame,
                f"t={t_video:.2f}s",
                (20, 30),
                cv.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            cv.putText(
                draw_frame,
                "POSE: OK",
                (20, 65),
                cv.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

            out_img = skeleton_dir / f"{i:04d}_{img_path.stem}_skeleton.jpg"
            cv.imwrite(str(out_img), draw_frame)
        else:
            frame_result = {
                "success": False,
                "frame_number": i,
                "video_timestamp": t_video,
                "process_timestamp": time.time() - t_start,
                "image_w": int(image.shape[1]),
                "image_h": int(image.shape[0]),
                "pose_landmarks2d": [],
                "pose_world_landmarks3d": [],
                "quality": {
                    "mean_visibility": 0.0,
                    "landmark_count_2d": 0,
                    "landmark_count_3d": 0,
                },
                "message": "未检测到人体姿态",
                "source_image": str(img_path),
            }
            results_list.append(frame_result)

            draw_frame = image.copy()
            cv.putText(
                draw_frame,
                f"t={t_video:.2f}s",
                (20, 30),
                cv.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )
            cv.putText(
                draw_frame,
                "POSE: MISS",
                (20, 65),
                cv.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )
            out_img = skeleton_dir / f"{i:04d}_{img_path.stem}_skeleton.jpg"
            cv.imwrite(str(out_img), draw_frame)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(results_list, f, indent=2, ensure_ascii=False)

    return results_list


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    default_input_dir = repo_root / "picture"
    default_out_dir = Path(__file__).resolve().parent / "converted_outputs"

    parser = argparse.ArgumentParser(description="从图片序列生成骨架图与 Unitree H1 轨迹(JSONL)")
    parser.add_argument("--input-dir", default=str(default_input_dir), help="图片目录（默认: repo_root/picture）")
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=None,
        help="显式指定图片路径列表（优先于 --input-dir）",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="只处理前 N 张图片（0 表示不限制）。用于只保留第一张等场景。",
    )
    parser.add_argument("--fps", type=float, default=10.0, help="把图片序列当作视频的帧率，用于生成 video_timestamp")
    parser.add_argument("--out-dir", default=str(default_out_dir), help="输出目录（默认: naoqi-pose-retargeting/converted_outputs）")
    parser.add_argument(
        "--pose-json",
        default="images_pose_results.json",
        help="输出 pose_results.json 文件名（写入到 out-dir 下）",
    )
    parser.add_argument(
        "--skeleton-dir",
        default="skeleton_images",
        help="骨架叠加图片输出子目录（写入到 out-dir 下）",
    )
    parser.add_argument("--model-complexity", type=int, default=1, choices=[0, 1, 2])
    parser.add_argument("--min-det", type=float, default=0.5, help="min_detection_confidence")
    parser.add_argument("--min-track", type=float, default=0.5, help="min_tracking_confidence")
    parser.add_argument(
        "--no-convert",
        action="store_true",
        help="只导出骨架图与 pose_results.json，不生成 Unitree JSONL",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    pose_json = out_dir / str(args.pose_json)
    skeleton_dir = out_dir / str(args.skeleton_dir)

    images = _collect_images(input_dir, args.inputs)
    if not images:
        raise SystemExit(f"未找到图片: {input_dir} (or --inputs)")

    max_frames = int(args.max_frames)
    if max_frames > 0:
        images = images[:max_frames]

    print("[pose_estimator_images] input images:")
    for p in images:
        print(f"  - {p}")
    print(f"[pose_estimator_images] out_dir: {out_dir}")
    print(f"[pose_estimator_images] pose_json: {pose_json}")
    print(f"[pose_estimator_images] skeleton_dir: {skeleton_dir}")

    estimate_images(
        image_paths=images,
        fps=float(args.fps),
        out_json=pose_json,
        skeleton_dir=skeleton_dir,
        model_complexity=int(args.model_complexity),
        min_detection_confidence=float(args.min_det),
        min_tracking_confidence=float(args.min_track),
    )

    if bool(args.no_convert):
        print("[pose_estimator_images] done (no convert)")
        return

    meta = convert_pose_results.convert(pose_json, out_dir, sample_fps=float(args.fps))
    print("[pose_estimator_images] converted:")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
