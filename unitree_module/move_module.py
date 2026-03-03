from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CmdVel:
    linear_x: float
    linear_y: float
    angular_z: float


class _BackendBase:
    def send_cmd_vel(self, cmd: CmdVel):
        raise NotImplementedError

    def stop(self):
        self.send_cmd_vel(CmdVel(0.0, 0.0, 0.0))

    def close(self):
        return None


class MockBackend(_BackendBase):
    def send_cmd_vel(self, cmd: CmdVel):
        print(
            "[unitree][mock] cmd_vel linear_x={:.3f} linear_y={:.3f} angular_z={:.3f}".format(
                cmd.linear_x, cmd.linear_y, cmd.angular_z
            )
        )


class Ros2CmdVelBackend(_BackendBase):
    def __init__(self, topic: str = "/cmd_vel"):
        try:
            import rclpy  # type: ignore[import-not-found]
            from rclpy.node import Node  # type: ignore[import-not-found]
            from geometry_msgs.msg import Twist  # type: ignore[import-not-found]
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "backend=ros2 需要 ROS2 Python 环境 (rclpy + geometry_msgs)。"
            ) from e

        self._rclpy = rclpy
        self._twist_cls = Twist
        if not self._rclpy.ok():
            self._rclpy.init()

        class _CmdVelNode(Node):
            pass

        self._node = _CmdVelNode("llm_pepper_unitree_cmdvel")
        self._pub = self._node.create_publisher(Twist, topic, 10)

    def send_cmd_vel(self, cmd: CmdVel):
        msg = self._twist_cls()
        msg.linear.x = float(cmd.linear_x)
        msg.linear.y = float(cmd.linear_y)
        msg.angular.z = float(cmd.angular_z)
        self._pub.publish(msg)
        self._rclpy.spin_once(self._node, timeout_sec=0.0)

    def close(self):
        try:
            self._node.destroy_node()
        except Exception:
            pass
        try:
            if self._rclpy.ok():
                self._rclpy.shutdown()
        except Exception:
            pass


class UnitreeMoveModule:
    """适配 controller_module/移动.py 与 LLM JSON 动作到 Unitree 仿真。

    - 键盘/跟随模式：收到形如 b"[119,97]" 的列表（w/a/s/d/q/e）
    - LLM 动作模式：收到 JSON {"intent":..., "params":...}

    当前默认：
    - mock 后端：仅打印
    - ros2 后端：发布 /cmd_vel（需要在 ROS2 环境运行）
    """

    def __init__(self):
        backend = (os.getenv("UNITREE_BACKEND", "mock") or "mock").strip().lower()
        topic = os.getenv("UNITREE_CMD_VEL_TOPIC", "/cmd_vel")
        if backend == "ros2":
            self._backend: _BackendBase = Ros2CmdVelBackend(topic=topic)
        else:
            self._backend = MockBackend()

        # 可用 env 调整速度
        self._key_linear = float(os.getenv("UNITREE_KEY_LINEAR", "0.6"))
        self._key_angular = float(os.getenv("UNITREE_KEY_ANGULAR", "0.8"))
        self._action_linear = float(os.getenv("UNITREE_ACTION_LINEAR", "0.5"))
        self._action_angular = float(os.getenv("UNITREE_ACTION_ANGULAR", "0.8"))

    def close(self):
        return self._backend.close()

    def _send_for_duration(self, cmd: CmdVel, duration_s: float, hz: float = 20.0):
        end_t = time.time() + max(0.0, float(duration_s))
        period = 1.0 / max(1.0, float(hz))
        while time.time() < end_t:
            self._backend.send_cmd_vel(cmd)
            time.sleep(period)
        self._backend.stop()

    @staticmethod
    def _try_parse_list(text: str) -> Optional[list[int]]:
        text = (text or "").strip()
        if not (text.startswith("[") and text.endswith("]")):
            return None
        if text == "[]":
            return []
        try:
            # controller 侧就是 str(list) 发过来，这里用 json 不稳；用 eval 但做最小防护
            value = eval(text, {"__builtins__": {}}, {})
            if isinstance(value, list) and all(isinstance(i, int) for i in value):
                return value
        except Exception:
            return None
        return None

    def _handle_keyboard(self, actions: list[int]):
        if not actions:
            self._backend.stop()
            return

        x = 0.0
        y = 0.0
        yaw = 0.0
        for a in actions:
            if a == ord("w"):
                x += self._key_linear
            elif a == ord("s"):
                x -= self._key_linear
            elif a == ord("a"):
                y += self._key_linear
            elif a == ord("d"):
                y -= self._key_linear
            elif a == ord("q"):
                yaw += self._key_angular
            elif a == ord("e"):
                yaw -= self._key_angular

        self._backend.send_cmd_vel(CmdVel(x, y, yaw))

    def _handle_intent(self, payload: dict[str, Any]):
        intent = payload.get("intent")
        params = payload.get("params") or {}

        if intent in {"forward", "retreat"}:
            dist = float(params.get("distance", 1.0))
            dist = max(0.0, abs(dist))
            direction = 1.0 if intent == "forward" else -1.0
            speed = max(0.05, abs(self._action_linear))
            duration = dist / speed
            self._send_for_duration(CmdVel(direction * speed, 0.0, 0.0), duration_s=duration)
            return

        if intent in {"left_spin_rotate", "right_spin_rotate"}:
            deg = float(params.get("degrees", 90))
            deg = max(0.0, abs(deg))
            rad = deg * 3.141592653589793 / 180.0
            direction = 1.0 if intent == "left_spin_rotate" else -1.0
            yaw_rate = max(0.1, abs(self._action_angular))
            duration = rad / yaw_rate
            self._send_for_duration(CmdVel(0.0, 0.0, direction * yaw_rate), duration_s=duration)
            return

        if intent == "spin_around":
            times = float(params.get("times", 1))
            times = max(0.0, times)
            yaw_rate = max(0.1, abs(self._action_angular))
            duration = (2.0 * 3.141592653589793 * times) / yaw_rate
            self._send_for_duration(CmdVel(0.0, 0.0, -yaw_rate), duration_s=duration)
            return

        # 未实现的 move intent：先停
        self._backend.stop()

    def handle(self, data: bytes):
        text = None
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

        actions = self._try_parse_list(text)
        if actions is not None:
            self._handle_keyboard(actions)
            return

        try:
            payload = json.loads(text)
        except Exception:
            return

        if isinstance(payload, dict):
            self._handle_intent(payload)

