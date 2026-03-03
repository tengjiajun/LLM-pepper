from __future__ import annotations

import json


class UnitreeIntentModule:
    """占位适配器：接收 Pepper 侧发来的 JSON intent，并在终端打印。

    目的：
    - 让你现有 controller/LLM 的 intent 不用改，就能先在 H1 仿真侧验证“消息到了”。
    - 等你们确定仿真平台后，再把这里替换为真实的关节控制（Isaac/MuJoCo/ROS2 SDK）。

    说明：
    - group 名称来自 server 的路由：active_1/active_2/head/body
    - 数据格式一般为 {"module":..., "intent":..., "params":{...}}
    """

    def __init__(self, group: str):
        self.group = group

    def handle(self, data: bytes):
        try:
            text = data.decode("utf-8", errors="ignore").strip()
        except Exception:
            return

        if not text:
            return

        # 有些 group 可能会收到键盘 list（如 active_1/2），先兜底打印
        if text.startswith("[") and text.endswith("]"):
            print(f"[unitree][{self.group}] keylist=", text)
            return

        if text in {"reply_action", "DINGDONG"}:
            print(f"[unitree][{self.group}]", text)
            return

        try:
            payload = json.loads(text)
        except Exception:
            print(f"[unitree][{self.group}] raw=", text)
            return

        if not isinstance(payload, dict):
            print(f"[unitree][{self.group}] payload=", payload)
            return

        intent = payload.get("intent")
        params = payload.get("params") or {}
        print(f"[unitree][{self.group}] intent=", intent, "params=", params)
