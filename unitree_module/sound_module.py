from __future__ import annotations

import json


class UnitreeSoundModule:
    """最小 sound 适配：

    控制端会发两类：
    - 纯文本："SOUND..." 或 "DINGDONG" / "reply_action"
    - JSON：{"intent":..., "module":"sound", "params":...}

    Unitree 仿真端默认只打印（科研仿真常用）。
    """

    def handle(self, data: bytes):
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            return

        if not text:
            return

        if text.startswith("SOUND"):
            print("[unitree][sound]", text[5:])
            return

        if text in {"DINGDONG", "reply_action"}:
            print("[unitree][sound]", text)
            return

        try:
            payload = json.loads(text)
        except Exception:
            print("[unitree][sound] raw=", text)
            return

        if isinstance(payload, dict):
            intent = payload.get("intent")
            params = payload.get("params") or {}
            print("[unitree][sound] intent=", intent, "params=", params)
