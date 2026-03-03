"""最小演示：LLM 把自然语言编辑请求转成结构化 MotionEdit JSON。

用法（需要配置环境变量）：
- Windows PowerShell:
  $env:LLM_API_KEY="..."; $env:LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
  python tools/motion_llm_demo.py

注意：这是 demo，不会控制仿真，只展示 LLM 输出协议。
"""

from __future__ import annotations

import json
import os

from llm_module.motion_editor import MotionLLM


def main():
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL", "qwen-turbo")

    if not api_key or not base_url:
        raise SystemExit("需要设置 LLM_API_KEY 和 LLM_BASE_URL")

    llm = MotionLLM(api_key=api_key, base_url=base_url, model=model)

    user_request = "动作快一点，右臂抬高一点，外展一点"
    motion_summary = {
        "fps": 30,
        "duration_s": 4.0,
        "joints": {
            "RShoulderPitch": {"min": 0.1, "max": 1.2},
            "RShoulderRoll": {"min": -0.5, "max": 0.2},
        },
        "current": {"speed_scale": 1.0, "max_joint_speed_deg_s": 120.0},
        "issues": ["右臂抬手不足", "动作略慢"],
    }

    edit = llm.propose_edit(
        user_request=user_request,
        motion_summary=motion_summary,
        constraints={"speed_scale_range": [0.5, 2.0]},
        history=[],
    )

    print(json.dumps(edit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
