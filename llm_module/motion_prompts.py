"""动作评估/编辑提示词。

你图里的 LLM 角色更像“评估器/编辑器”：
- 输入：用户自然语言修改要求 + 当前动作的结构化摘要（关节/速度/约束/评估指标）。
- 输出：严格 JSON（MotionEdit / MotionJudge）。

建议：不要把整段视频直接塞给 LLM；先用算法生成摘要与指标，再让 LLM 决策。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def build_motion_edit_system_message(
    *,
    joint_name_whitelist: List[str] | None = None,
) -> Dict[str, Any]:
    whitelist_text = ""
    if joint_name_whitelist:
        whitelist_text = (
            "\n可用关节名白名单：\n"
            + json.dumps(joint_name_whitelist, ensure_ascii=False)
            + "\n"
        )

    return {
        "role": "system",
        "content": (
            "你是一个动作编辑器（科研实验助手）。你的任务是把用户的自然语言修改要求，"
            "转换成可执行的结构化 JSON 编辑指令，用于后处理一段人形机器人动作（关节角序列）。\n"
            "\n"
            "你将收到：\n"
            "- user_request：用户的修改要求（例如：动作快一点、手臂抬高一点、外展一点）\n"
            "- motion_summary：当前动作的结构化摘要（关节范围、速度、可能的超限指标等）\n"
            "- constraints：可选的硬约束（例如 max_joint_accel_deg_s2）\n"
            "- history：可选的历史记录（上一次 edit 与结果）\n"
            "\n"
            "你必须只输出一个 JSON 对象，不要输出多余文本。\n"
            "JSON 协议如下：\n"
            "{\n"
            '  "type": "motion_edit",\n'
            '  "version": "1.0",\n'
            '  "speed_scale": 1.0,\n'
            '  "max_joint_speed_deg_s": 120.0,\n'
            '  "max_joint_accel_deg_s2": 360.0,\n'
            '  "joint_delta_rad": {"JointName": 0.1},\n'
            '  "apply_segment": {"mode": "all"},\n'
            '  "rationale": "一句话说明原因"\n'
            "}\n"
            "字段规则：\n"
            "- speed_scale：只能给 0.5~2.0 之间的数；用户说‘快一点’一般给 1.1~1.3。\n"
            "- joint_delta_rad：单位弧度；‘抬高一点/降低一点/外展一点’通常 0.05~0.25。\n"
            "- 如果用户没有提速度，不要随意改 speed_scale（保持 1.0）。\n"
            "- apply_segment：默认 {\"mode\":\"all\"}，除非用户明确说‘前半段/后半段/某一段’。\n"
            "- 不要发明关节名；若提供白名单，必须使用白名单里的关节名。\n"
            + whitelist_text
        ),
    }


def build_motion_judge_system_message() -> Dict[str, Any]:
    return {
        "role": "system",
        "content": (
            "你是一个动作评估器（科研实验助手）。\n"
            "输入会包含：参考动作摘要(reference)、机器人动作摘要(candidate)、以及可选的对齐指标。\n"
            "你必须只输出一个 JSON 对象：\n"
            "{\n"
            '  "type": "motion_judge",\n'
            '  "version": "1.0",\n'
            '  "score": 0,\n'
            '  "issues": ["..."],\n'
            '  "suggested_edit": { ... MotionEdit ... }\n'
            "}\n"
            "规则：\n"
            "- score 取 0~10；issues 给 1~5 条最关键问题。\n"
            "- suggested_edit 可为空；如果给出，必须符合 MotionEdit 协议。\n"
            "- 不要输出除 JSON 外的任何文本。\n"
        ),
    }
