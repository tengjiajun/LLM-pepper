#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可视化 Pepper 关节滤波角度的辅助脚本。

该工具读取由 ``/open_external_video`` 流式接口导出的 JSON 行数据（NDJSON），
并绘制每个关节在时间轴上的角度曲线，同时给出帧间差值统计，帮助快速判断
Butterworth 滤波后是否仍存在明显波动。

使用方式示例::

    # 将实时流保存到本地文件
    curl -X POST http://localhost:5000/open_external_video \
        -H "Content-Type: application/json" \
        -d '{"show_window": false}' \
        --no-buffer > samples.jsonl

    # 在图形界面中查看角度走势
    python tools/visualize_filtered_angles.py --input samples.jsonl --fps 10

运行脚本后，将弹出一个 Matplotlib 窗口展示每个关节的角度与波动标记。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import codecs
import io
from typing import Dict, Iterable, List, Optional, Sequence

try:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]
except ImportError as exc:  # pragma: no cover - graceful fallback for missing deps
    raise SystemExit(
        "运行该脚本需要安装 matplotlib 和 numpy，请执行 `pip install matplotlib numpy`."
    ) from exc

FrameAngles = List[Optional[float]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="可视化滤波后的 Pepper 关节角度，并标记异常波动",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--input",
        type=str,
        default="-",
        help="输入文件路径（JSON 行格式），使用 '-' 表示从标准输入读取",
    )
    parser.add_argument(
        "--field",
        type=str,
        choices=["angles", "angles_deg"],
        default="angles_deg",
        help="读取的角度字段；若选择 'angles' 则视为弧度并转换为角度制",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="输出帧率（用于将横轴转换为秒）；未提供时使用帧编号",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="波动阈值（单位：度）。超过该阈值的帧将被高亮标记",
    )
    parser.add_argument(
        "--smooth",
        dest="smooth",
        action="store_true",
        help="启用基于中值 + 阈值保持的信号平滑（默认开启）",
    )
    parser.add_argument(
        "--no-smooth",
        dest="smooth",
        action="store_false",
        help="禁用平滑，仅展示原始曲线",
    )
    parser.set_defaults(smooth=True)
    parser.add_argument(
        "--smooth-threshold",
        type=float,
        default=8.0,
        help="平滑步骤中用于判定抖动与动作的阈值（单位：度）",
    )
    parser.add_argument(
        "--smooth-median-window",
        type=int,
        default=5,
        help="中值滤波窗口大小（奇数）。用于消除尖峰噪声",
    )
    parser.add_argument(
        "--smooth-rate-limit",
        type=float,
        default=None,
        help="每帧允许的最大变化量（单位：度）。未设置时与 smooth_threshold 相同",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="可选的输出图像路径（PNG/SVG 等）。若提供则在保存后仍会弹窗展示",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="仅分析最新的 N 帧数据，便于聚焦近期波动",
    )

    return parser.parse_args()


def _detect_encoding(raw: io.BufferedReader) -> str:
    """根据 BOM 猜测文本编码。默认为 UTF-8。"""

    sample = raw.peek(4)[:4]
    if sample.startswith(codecs.BOM_UTF16_LE) or sample.startswith(codecs.BOM_UTF16_BE):
        return "utf-16"
    if sample.startswith(codecs.BOM_UTF32_LE) or sample.startswith(codecs.BOM_UTF32_BE):
        return "utf-32"
    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    return "utf-8"


def load_stream(path: str) -> Iterable[Dict]:
    """逐行读取 JSON 数据，忽略无法解析的行，并处理常见 BOM。"""

    stdin = __import__("sys").stdin
    if path == "-":
        source: Iterable[str] = stdin
        handle = None
    else:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"未找到输入文件: {file_path}")

        raw = file_path.open("rb")
        encoding = _detect_encoding(raw)
        text_handle = io.TextIOWrapper(raw, encoding=encoding, errors="replace")
        source = text_handle
        handle = text_handle

    try:
        for raw_line in source:
            line = raw_line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    finally:
        if handle is not None:
            handle.close()


def ensure_joint_names(record: Dict, current: Optional[Sequence[str]]) -> Optional[List[str]]:
    """获取或校验 joint_names。"""

    joint_names = record.get("joint_names")
    if joint_names is None:
        return list(current) if current is not None else None

    if current is not None and list(current) != list(joint_names):
        raise ValueError(
            "检测到 joint_names 与前一帧不一致，无法继续绘图"
        )

    return list(joint_names)


def extract_angles(
    record: Dict,
    joint_names: Sequence[str],
    field: str,
) -> FrameAngles:
    """提取单帧角度，缺失数据会返回 None。"""

    if field in record:
        values = record[field]
    elif field == "angles_deg" and "angles" in record:
        # 自动从弧度转换
        values = [
            (math.degrees(v) if v is not None else None) for v in record["angles"]
        ]
    else:
        values = None

    if values is None or len(values) != len(joint_names):
        return [None] * len(joint_names)

    frame_angles: FrameAngles = []
    for value in values:
        if value is None:
            frame_angles.append(None)
        else:
            try:
                frame_angles.append(float(value))
            except (TypeError, ValueError):
                frame_angles.append(None)
    return frame_angles


def to_nan_array(frames: Sequence[FrameAngles]) -> np.ndarray:
    """将角度列表转换为以 NaN 表示缺失值的 numpy 数组。"""

    if not frames:
        return np.empty((0, 0))

    data = np.empty((len(frames), len(frames[0])), dtype=float)
    data[:] = np.nan
    for idx, frame in enumerate(frames):
        for jdx, value in enumerate(frame):
            if value is not None:
                data[idx, jdx] = value
    return data


def finite_differences(series: np.ndarray) -> np.ndarray:
    """计算帧间差值，对缺失值保留 NaN。"""

    diffs = np.empty_like(series)
    diffs[:] = np.nan
    prev = np.nan
    for idx, value in enumerate(series):
        if idx == 0:
            prev = value
            continue
        if np.isnan(value) or np.isnan(prev):
            diffs[idx] = np.nan
        else:
            diffs[idx] = value - prev
        prev = value
    return diffs


def nanmedian_filter(series: np.ndarray, window: int) -> np.ndarray:
    """对包含 NaN 的序列做中值滤波。"""

    window = max(int(window), 1)
    if window % 2 == 0:
        window += 1
    if window == 1:
        return series.copy()

    half = window // 2
    result = np.full_like(series, np.nan)
    for idx in range(series.shape[0]):
        start = max(0, idx - half)
        end = min(series.shape[0], idx + half + 1)
        window_values = series[start:end]
        finite_values = window_values[~np.isnan(window_values)]
        if finite_values.size:
            result[idx] = float(np.median(finite_values))
    return result


def rate_limited_plateau(
    series: np.ndarray,
    hold_threshold: float,
    rate_limit: float,
) -> np.ndarray:
    """将小幅抖动保持为平台，大幅动作按最大速率渐进。"""

    result = np.full_like(series, np.nan)
    prev = np.nan
    pending = 0.0
    for idx, value in enumerate(series):
        if np.isnan(value):
            result[idx] = prev
            continue

        if np.isnan(prev):
            result[idx] = value
            prev = result[idx]
            pending = 0.0
            continue

        delta = value - prev
        if np.isnan(delta):
            result[idx] = prev
            continue

        if abs(delta) <= hold_threshold:
            pending += delta
            if abs(pending) >= hold_threshold:
                step = math.copysign(min(rate_limit, abs(pending)), pending)
                result[idx] = prev + step
                pending -= step
            else:
                result[idx] = prev
        else:
            step = math.copysign(min(rate_limit, abs(delta)), delta)
            result[idx] = prev + step
            pending = 0.0

        prev = result[idx]

    return result


def smooth_series(
    series: np.ndarray,
    hold_threshold: float,
    median_window: int,
    rate_limit: float,
) -> np.ndarray:
    """组合中值滤波与平台保持/速率限制的平滑。"""

    base = nanmedian_filter(series, median_window)
    # 对开头尚未得到中值的元素退回原值
    fallback_mask = np.isnan(base) & ~np.isnan(series)
    base[fallback_mask] = series[fallback_mask]
    smoothed = rate_limited_plateau(base, hold_threshold, rate_limit)
    return smoothed


def smooth_dataset(
    data_deg: np.ndarray,
    hold_threshold: float,
    median_window: int,
    rate_limit: float,
) -> np.ndarray:
    """对每个关节序列应用平滑。"""

    smoothed = np.empty_like(data_deg)
    smoothed[:] = np.nan
    for idx in range(data_deg.shape[1]):
        smoothed[:, idx] = smooth_series(
            data_deg[:, idx], hold_threshold, median_window, rate_limit
        )
    return smoothed


def summarise_fluctuations(
    joint_names: Sequence[str],
    data_deg: np.ndarray,
    threshold: Optional[float],
    title: str,
) -> None:
    """在终端输出每个关节的波动统计。"""

    print(f"\n=== {title} ===")
    for idx, joint in enumerate(joint_names):
        series = data_deg[:, idx]
        if np.all(np.isnan(series)):
            print(f"- {joint}: 无有效数据")
            continue

        delta = np.abs(finite_differences(series))
        max_delta = np.nanmax(delta)
        p95 = np.nanpercentile(delta, 95) if np.any(np.isfinite(delta)) else np.nan
        msg = f"- {joint}: 最大波动 {max_delta:.3f}°"
        if np.isfinite(p95):
            msg += f", 95% 分位 {p95:.3f}°"
        if threshold:
            count_exceed = (np.isfinite(delta) & (delta > threshold)).sum()
            msg += f", 超过阈值帧数 {count_exceed}"
        print(msg)


def plot_angles(
    joint_names: Sequence[str],
    data_deg: np.ndarray,
    time_axis: np.ndarray,
    threshold: Optional[float],
    smoothed_deg: Optional[np.ndarray] = None,
) -> None:
    """仅绘制角度曲线，可选标注超阈值的点。"""

    num_joints = len(joint_names)
    if num_joints == 0:
        raise ValueError("没有 joint_names，无法绘制图表")

    cols = 2 if num_joints > 1 else 1
    rows = math.ceil(num_joints / cols)
    fig, axes = plt.subplots(rows, cols, sharex=True, figsize=(cols * 6.0, rows * 3.5))
    axes = np.atleast_1d(axes).reshape(-1)

    for idx, joint in enumerate(joint_names):
        ax = axes[idx]
        series = data_deg[:, idx]
        handle_raw, = ax.plot(time_axis, series, label="原始", color="#1f77b4", linewidth=1.4)
        legend_handles = [handle_raw]
        legend_labels = ["原始"]

        if smoothed_deg is not None:
            smooth_series = smoothed_deg[:, idx]
            handle_smooth, = ax.plot(
                time_axis,
                smooth_series,
                label="平滑",
                color="#d62728",
                linewidth=2.0,
            )
            legend_handles.append(handle_smooth)
            legend_labels.append("平滑")

        ax.set_title(joint)
        ax.set_ylabel("角度 (°)")
        ax.grid(True, linestyle="--", alpha=0.3)

        if threshold is not None:
            delta = np.abs(finite_differences(series))
            exceed_mask = np.isfinite(delta) & (delta > threshold)
            exceed_indices = np.where(exceed_mask)[0]
            if exceed_indices.size:
                scatter = ax.scatter(
                    time_axis[exceed_indices],
                    series[exceed_indices],
                    color="#ff7f0e",
                    s=25,
                    label=f"Δ>{threshold}°",
                    zorder=3,
                )
                legend_handles.append(scatter)
                legend_labels.append(f"Δ>{threshold}°")

        if legend_handles:
            ax.legend(legend_handles, legend_labels, loc="upper right")

    for idx in range(num_joints, len(axes)):
        fig.delaxes(axes[idx])

    xlabel = "时间 (s)" if time_axis.dtype.kind == "f" and np.any(time_axis % 1) else "帧编号"
    axes[min(num_joints - 1, len(axes) - 1)].set_xlabel(xlabel)
    fig.tight_layout()


def main() -> None:
    args = parse_args()
    frames: List[FrameAngles] = []
    joint_names: Optional[List[str]] = None

    for record in load_stream(args.input):
        joint_names = ensure_joint_names(record, joint_names)
        if joint_names is None:
            continue

        frame = extract_angles(record, joint_names, args.field)
        frames.append(frame)

    if not frames or joint_names is None:
        print("未获取到任何有效帧，无法绘制图表。")
        return

    if args.limit is not None and args.limit > 0:
        frames = frames[-args.limit :]

    data_deg = to_nan_array(frames)
    frame_indices = np.arange(data_deg.shape[0], dtype=float)
    if args.fps and args.fps > 0:
        time_axis = frame_indices / args.fps
    else:
        time_axis = frame_indices

    smoothed_deg: Optional[np.ndarray] = None
    if args.smooth:
        threshold_for_smooth = args.smooth_threshold or 8.0
        rate_limit = args.smooth_rate_limit or threshold_for_smooth
        smoothed_deg = smooth_dataset(
            data_deg,
            hold_threshold=threshold_for_smooth,
            median_window=args.smooth_median_window,
            rate_limit=rate_limit,
        )

    summarise_fluctuations(joint_names, data_deg, args.threshold, "关节波动统计（原始，单位：度）")
    if smoothed_deg is not None:
        summarise_fluctuations(
            joint_names,
            smoothed_deg,
            args.threshold,
            "关节波动统计（平滑后，单位：度）",
        )

    plot_angles(joint_names, data_deg, time_axis, args.threshold, smoothed_deg)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150)
        print(f"已保存图像到 {output_path}")

    print("关闭图窗即可结束程序。")
    plt.show()


if __name__ == "__main__":
    main()
