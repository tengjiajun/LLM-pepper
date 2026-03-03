"""LLM 动作编辑器/评估器。

这部分对应你图里的“评估器(LLM)”与“自然语言调整→结构化文本”。

设计要点：
- 输入尽量结构化（motion_summary/metrics），避免直接喂视频。
- 输出严格 JSON，便于实验记录与可复现。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .client import LLMClient
from .motion_prompts import (
    build_motion_edit_system_message,
    build_motion_judge_system_message,
)
from .motion_schema import MotionEdit, MotionJudge, ensure_defaults


def _strip_code_fence(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.replace("```json", "").replace("```", "").strip()


class MotionLLM:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "qwen-turbo",
        joint_name_whitelist: Optional[List[str]] = None,
    ):
        self.client = LLMClient(api_key=api_key, base_url=base_url, model=model)
        self._edit_system = build_motion_edit_system_message(
            joint_name_whitelist=joint_name_whitelist
        )
        self._judge_system = build_motion_judge_system_message()

    def propose_edit(
        self,
        *,
        user_request: str,
        motion_summary: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> MotionEdit:
        payload = {
            "user_request": user_request,
            "motion_summary": motion_summary,
            "constraints": constraints or {},
            "history": history or [],
        }

        messages = [
            self._edit_system,
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        resp = self.client.chat(messages=messages, stream=False)
        text = _strip_code_fence(resp.choices[0].message.content)
        edit = json.loads(text)
        if not isinstance(edit, dict):
            raise ValueError("LLM output is not a JSON object")
        return ensure_defaults(edit)  # type: ignore[arg-type]

    def judge(
        self,
        *,
        reference_summary: Dict[str, Any],
        candidate_summary: Dict[str, Any],
        alignment_metrics: Optional[Dict[str, Any]] = None,
    ) -> MotionJudge:
        payload = {
            "reference": reference_summary,
            "candidate": candidate_summary,
            "alignment_metrics": alignment_metrics or {},
        }
        messages = [
            self._judge_system,
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        resp = self.client.chat(messages=messages, stream=False)
        text = _strip_code_fence(resp.choices[0].message.content)
        judge = json.loads(text)
        if not isinstance(judge, dict):
            raise ValueError("LLM output is not a JSON object")
        if "type" not in judge:
            judge["type"] = "motion_judge"
        if "version" not in judge:
            judge["version"] = "1.0"
        return judge  # type: ignore[return-value]
