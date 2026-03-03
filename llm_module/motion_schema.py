"""面向“动作编辑/评估”的结构化协议（LLM 输出）。

目标：
- 让 LLM 不直接输出自然语言操作细节，而是输出可执行/可记录的 JSON。
- 先覆盖你图里常见的编辑指令：速度、加速度限制、关节偏置（抬高/外展等）。

注意：这里是协议定义（约定字段），不绑定具体仿真平台。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


JointDelta = Dict[str, float]


class MotionEdit(TypedDict, total=False):
    # 元信息
    type: Literal["motion_edit"]
    version: str

    # 全局速度缩放，如 1.2 表示快 20%
    speed_scale: float

    # 角加速度/角速度限制（用于后续轨迹重采样或限幅）
    max_joint_speed_deg_s: float
    max_joint_accel_deg_s2: float

    # 关节偏置（弧度）。例如 {"LShoulderPitch": +0.2, "RShoulderRoll": +0.15}
    joint_delta_rad: JointDelta

    # 作用区间（可选）。若省略，默认对整个动作生效。
    # - start/end 使用帧索引或时间戳均可，但要和调用方约定。
    apply_segment: Dict[str, Any]

    # 用于实验记录的解释（不参与执行）
    rationale: str


class MotionJudge(TypedDict, total=False):
    type: Literal["motion_judge"]
    version: str

    # 0-10 分
    score: float

    # 关键问题列表（用于驱动下一轮 edit）
    issues: List[str]

    # 建议的 edit（可选）
    suggested_edit: MotionEdit


def ensure_defaults(edit: MotionEdit) -> MotionEdit:
    if "type" not in edit:
        edit["type"] = "motion_edit"
    if "version" not in edit:
        edit["version"] = "1.0"
    if "joint_delta_rad" not in edit or edit["joint_delta_rad"] is None:
        edit["joint_delta_rad"] = {}
    return edit
