"""Utility functions to clamp and smooth Pepper joint control points."""
from __future__ import annotations

from typing import Dict, List, Sequence

# Default safety parameters (can be overridden per call)
MAX_SINGLE_OFFSET = 0.8  # maximum deviation from initial angle (radians)
MAX_STEP_DELTA = 0.35    # maximum delta allowed between consecutive frames (at 0.1s)
SMOOTH_ALPHA = 0.45      # smoothing coefficient (0-1, smaller -> smoother)

BASE_STEP = 0.1          # reference time step in seconds


def _clamp_angle(base: float, value: float, max_offset: float) -> float:
    """Limit *value* so it does not deviate from *base* by more than *max_offset*."""
    upper = base + max_offset
    lower = base - max_offset
    if value > upper:
        return upper
    if value < lower:
        return lower
    return value


def _sanitize_series(
    base: float,
    series: Sequence[float | None],
    max_offset: float,
    *,
    time_gaps: Sequence[float] | None = None,
) -> List[float]:
    """Clamp series near base while filling None and scaling by time gaps."""
    cleaned: List[float] = []
    last_valid = base
    for idx, value in enumerate(series):
        if value is None:
            value = last_valid
        else:
            last_valid = value
        scale = 1.0
        if time_gaps and idx < len(time_gaps):
            gap = max(time_gaps[idx], BASE_STEP)
            scale = max(1.0, gap / BASE_STEP)
        cleaned.append(_clamp_angle(base, value, max_offset * scale))
    return cleaned


def _smooth_sequence(
    sequence: Sequence[float],
    max_step_delta: float,
    smooth_alpha: float,
    *,
    time_gaps: Sequence[float] | None = None,
) -> List[float]:
    """Apply step limiting and exponential smoothing to the sequence."""
    if not sequence:
        return []

    smoothed: List[float] = [float(sequence[0])]
    for idx, raw in enumerate(sequence[1:]):
        prev = smoothed[-1]
        # Limit jump size first
        scale = 1.0
        if time_gaps and idx < len(time_gaps):
            gap = max(time_gaps[idx], BASE_STEP)
            scale = max(1.0, gap / BASE_STEP)
        allowed = max_step_delta * scale
        limited = raw
        if raw - prev > allowed:
            limited = prev + allowed
        elif prev - raw > allowed:
            limited = prev - allowed
        # Exponential smoothing towards the limited value
        fused = prev + smooth_alpha * (limited - prev)
        smoothed.append(fused)
    return smoothed


def _compute_time_arrays(
    times: Sequence[float] | None,
    series_length: int,
) -> tuple[list[float] | None, list[float] | None]:
    """Return per-value and per-transition time gaps based on provided timeline."""
    if not times or len(times) < series_length + 1:
        return None, None

    sampled = list(times[1:series_length + 1])
    value_gaps: list[float] = []
    prev = times[0]
    for t in sampled:
        value_gaps.append(max(t - prev, BASE_STEP))
        prev = t

    transition_gaps: list[float] = []
    for i in range(1, len(sampled)):
        transition_gaps.append(max(sampled[i] - sampled[i - 1], BASE_STEP))

    return value_gaps, transition_gaps


def build_control_points(
    joint_names: Sequence[str],
    joint_series: Dict[str, Sequence[float | None]],
    initial_angles: Dict[str, float],
    *,
    max_single_offset: float = MAX_SINGLE_OFFSET,
    max_step_delta: float = MAX_STEP_DELTA,
    smooth_alpha: float = SMOOTH_ALPHA,
    joint_times: Dict[str, Sequence[float]] | None = None,
) -> List[List[float]]:
    """Construct smoothed control points for each joint.

    The resulting control points include the initial angle at the start/end to
    keep trajectories bounded.
    """
    control_points: List[List[float]] = []
    for name in joint_names:
        base = initial_angles.get(name, 0.0)
        series = joint_series.get(name, [])
        value_gaps, transition_gaps = _compute_time_arrays(
            joint_times.get(name) if joint_times else None,
            len(series),
        )
        clamped = _sanitize_series(
            base,
            series,
            max_single_offset,
            time_gaps=value_gaps,
        )
        smoothed = _smooth_sequence(
            clamped,
            max_step_delta,
            smooth_alpha,
            time_gaps=transition_gaps,
        )
        control_points.append([base] + smoothed + [base])
    return control_points


def smooth_control_points_for_joint(
    joint_name: str,
    control_point: Sequence[float],
    initial_angles: Dict[str, float],
    *,
    max_single_offset: float = MAX_SINGLE_OFFSET,
    max_step_delta: float = MAX_STEP_DELTA,
    smooth_alpha: float = SMOOTH_ALPHA,
    time_sequence: Sequence[float] | None = None,
) -> List[float]:
    """Re-smooth an existing control point list (keeps the endpoints fixed)."""
    if len(control_point) <= 2:
        return list(control_point)

    base = initial_angles.get(joint_name, 0.0)
    series = control_point[1:-1]
    value_gaps, transition_gaps = _compute_time_arrays(time_sequence, len(series))
    inner = _sanitize_series(
        base,
        series,
        max_single_offset,
        time_gaps=value_gaps,
    )
    smoothed = _smooth_sequence(
        inner,
        max_step_delta,
        smooth_alpha,
        time_gaps=transition_gaps,
    )
    return [base] + smoothed + [base]
