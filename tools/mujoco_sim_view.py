"""MuJoCo 最小仿真查看器。

用途：
- 验证模型能加载、能步进、能打开窗口。
- 不绑定 Unitree/H1 的具体模型文件；你只要提供 MJCF(xml) 路径即可。

运行：
  python tools/mujoco_sim_view.py --model path/to/model.xml
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import math
import threading
import ast
from pathlib import Path

# Ensure repo root is on sys.path so we can import `communication.*` even when
# the working directory is `mujoco_menagerie/unitree_h1`.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    import mujoco  # type: ignore[import-not-found]
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "无法导入 mujoco。\n"
        "如果你在 Windows 上，建议使用已安装 mujoco 的解释器运行，例如：\n"
        "  F:\\anaconda\\envs\\pepper_env\\python.exe tools\\mujoco_sim_view.py --model <model.xml>\n"
        f"原始错误: {e!r}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="MuJoCo minimal viewer")
    parser.add_argument("--model", required=True, help="MJCF .xml path")
    parser.add_argument(
        "--keyframe",
        default="",
        help="Reset to keyframe name after load (e.g. home). Empty to skip.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Do not open a viewer window; only load and step simulation.",
    )
    parser.add_argument(
        "--viewer",
        choices=["launch", "passive"],
        default="launch",
        help="Viewer backend: 'launch' is more robust on Windows; 'passive' lets this script drive stepping.",
    )
    parser.add_argument(
        "--hold",
        action="store_true",
        help="Hold the initial pose with a simple joint-space PD controller (torque motors).",
    )
    parser.add_argument(
        "--hold-add-ui",
        action="store_true",
        help="When --hold is enabled, add UI slider ctrl as extra torque bias instead of overriding it.",
    )
    parser.add_argument(
        "--ui-angle",
        action="store_true",
        help=(
            "Interpret viewer Control sliders as target joint angle offsets (radians, scaled), "
            "and move target at a fixed speed. In this mode, actuators are disabled (gear=0) "
            "so sliders won't directly apply torque."
        ),
    )
    parser.add_argument(
        "--ui-angle-mode",
        choices=["joint-range", "offset"],
        default="joint-range",
        help=(
            "Mapping from slider to desired joint angle when --ui-angle is enabled: "
            "'joint-range' maps slider min/max to joint min/max (recommended); "
            "'offset' uses desired_offset = ctrl * ui_angle_scale relative to initial pose."
        ),
    )
    parser.add_argument(
        "--ui-angle-scale",
        type=float,
        default=0.01,
        help="Slider unit -> radians scale when --ui-angle is enabled. (offset = ctrl * scale)",
    )
    parser.add_argument(
        "--ui-angle-unlimited-range",
        type=float,
        default=1.6,
        help=(
            "For joints without limits (or if joint range is unavailable), use this symmetric range (radians) "
            "around the initial pose when --ui-angle-mode=joint-range."
        ),
    )
    parser.add_argument(
        "--ui-angle-speed",
        type=float,
        default=1.0,
        help="Max target angle change speed (rad/s) when --ui-angle is enabled.",
    )
    parser.add_argument(
        "--freeze-base",
        action="store_true",
        help="Freeze the root freejoint pose (qpos[0:7]) to the initial state to prevent falling.",
    )
    parser.add_argument(
        "--demo",
        choices=["none", "wave", "squat"],
        default="none",
        help="Optional demo motion to apply on top of --hold.",
    )
    parser.add_argument(
        "--demo-amp",
        type=float,
        default=0.35,
        help="Demo joint amplitude (radians) for --demo.",
    )
    parser.add_argument(
        "--demo-freq",
        type=float,
        default=0.6,
        help="Demo frequency (Hz) for --demo.",
    )
    parser.add_argument(
        "--demo-trigger",
        action="store_true",
        help=(
            "Only play --demo when triggered by a key from controller.py; can be retriggered without closing the viewer. "
            "Works when --key-torque or --teleop is enabled (so we receive key lists)."
        ),
    )
    parser.add_argument(
        "--demo-duration",
        type=float,
        default=2.5,
        help="Seconds to play the demo after each trigger when --demo-trigger is enabled.",
    )
    parser.add_argument(
        "--demo-trigger-key",
        type=str,
        default="r",
        help="Trigger key (single character) used by --demo-trigger. Default: r",
    )
    parser.add_argument(
        "--teleop",
        action="store_true",
        help="Teleop from controller.py via server.py move group (WASD/QE).",
    )
    parser.add_argument(
        "--key-torque",
        action="store_true",
        help=(
            "Subscribe to Pepper-style keyboard groups (head/wrist/body/active_1/active_2) and apply constant "
            "actuator torques while keys are held; release -> torque=0."
        ),
    )
    parser.add_argument(
        "--key-torque-hold",
        action="store_true",
        help=(
            "When --key-torque is enabled, also hold the initial pose with a joint-space PD controller, and add "
            "key torques as bias. This makes joints feel stiff instead of floppy."
        ),
    )
    parser.add_argument(
        "--key-torque-mag",
        type=float,
        default=12.0,
        help="Constant torque magnitude used by --key-torque (will be clamped by actuator ctrlrange).",
    )
    parser.add_argument("--server-ip", default="127.0.0.1", help="server.py IP")
    parser.add_argument("--server-port", type=int, default=5556, help="server.py port")
    parser.add_argument(
        "--teleop-speed",
        type=float,
        default=0.5,
        help="Teleop speed in local XY (m/s).",
    )
    parser.add_argument(
        "--teleop-yaw-rate",
        type=float,
        default=1.0,
        help="Teleop yaw rate (rad/s).",
    )
    parser.add_argument(
        "--hold-kp",
        type=float,
        default=120.0,
        help="PD proportional gain for --hold.",
    )
    parser.add_argument(
        "--hold-kd",
        type=float,
        default=6.0,
        help="PD derivative gain for --hold.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Run seconds; 0 means run until window closed (headless defaults to 1s)",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.0,
        help="Override timestep; 0 means use model option timestep",
    )
    parser.add_argument(
        "--list-actuators",
        action="store_true",
        help="Print full actuator names (and mapping) then exit. Useful because the viewer UI truncates long names.",
    )
    args = parser.parse_args()

    if args.ui_angle and args.hold:
        print("[mujoco_sim_view] warning: --ui-angle enabled; --hold will be ignored")
        args.hold = False

    if args.key_torque and args.ui_angle:
        raise SystemExit("--key-torque is incompatible with --ui-angle")

    if args.key_torque and args.hold:
        print("[mujoco_sim_view] warning: --hold with --key-torque -> enabling --key-torque-hold and disabling --hold")
        args.key_torque_hold = True
        args.hold = False

    model_path = os.path.abspath(args.model)
    if not os.path.exists(model_path):
        raise SystemExit(f"Model not found: {model_path}")

    print(f"[mujoco_sim_view] loading model: {model_path}")
    model = mujoco.MjModel.from_xml_path(model_path)
    data = mujoco.MjData(model)
    print("[mujoco_sim_view] model loaded")

    if args.ui_angle and int(model.nu) > 0:
        # Disable actuators so UI sliders no longer apply direct torque via data.ctrl.
        # We will read slider values from data.ctrl and apply our own torques via qfrc_applied.
        try:
            model.actuator_gear[:] = 0
            print("[mujoco_sim_view] ui-angle: disabled actuators (actuator_gear = 0)")
        except Exception as e:
            print(f"[mujoco_sim_view] ui-angle: failed to disable actuators via gear (will continue): {e!r}")

    if args.key_torque and int(model.nu) <= 0:
        raise SystemExit("--key-torque requires model.nu > 0 (no actuators found)")

    if args.list_actuators:
        print("\n=== Actuators (index -> name | ctrlrange | joint) ===")
        for act_id in range(int(model.nu)):
            act_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, act_id) or ""
            jnt_id = int(model.actuator_trnid[act_id, 0])
            jnt_name = (
                mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jnt_id)
                if jnt_id >= 0
                else None
            )
            ctrl_min = float(model.actuator_ctrlrange[act_id, 0])
            ctrl_max = float(model.actuator_ctrlrange[act_id, 1])
            print(f"{act_id:2d}: {act_name:24s} | [{ctrl_min:g}, {ctrl_max:g}] | {jnt_name or ''}")
        return

    if args.dt and args.dt > 0:
        model.opt.timestep = float(args.dt)

    if args.keyframe:
        name = str(args.keyframe)
        key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, name)
        if int(key_id) >= 0:
            mujoco.mj_resetDataKeyframe(model, data, int(key_id))
            mujoco.mj_forward(model, data)
            print(f"[mujoco_sim_view] reset to keyframe: {name}")
        else:
            print(f"[mujoco_sim_view] keyframe not found: {name}")

    # Prepare a minimal pose-hold controller for torque motors.
    # (act_id, joint_id, qpos_adr, dof_adr)
    actuator_joint_map: list[tuple[int, int, int, int]] = []
    key_torque_hold_enabled = bool(args.key_torque and args.key_torque_hold)
    if args.hold or args.ui_angle or key_torque_hold_enabled:
        if int(model.nu) <= 0:
            print("[mujoco_sim_view] --hold requested but model.nu == 0 (no actuators)")
        else:
            for act_id in range(int(model.nu)):
                joint_id = int(model.actuator_trnid[act_id, 0])
                if joint_id < 0:
                    continue
                qpos_adr = int(model.jnt_qposadr[joint_id])
                dof_adr = int(model.jnt_dofadr[joint_id])
                actuator_joint_map.append((act_id, joint_id, qpos_adr, dof_adr))

            if not actuator_joint_map:
                print("[mujoco_sim_view] --hold requested but no joint actuators were found")

    # Base target pose for hold/ui-angle.
    hold_target_qpos = data.qpos.copy() if (args.hold or args.ui_angle or key_torque_hold_enabled) else None
    ui_angle_target_qpos = hold_target_qpos.copy() if args.ui_angle and hold_target_qpos is not None else None
    last_time_for_ui = float(data.time)

    # key-torque-hold state: target pose updates when keys are released.
    key_hold_target_qpos = (
        hold_target_qpos.copy() if (key_torque_hold_enabled and hold_target_qpos is not None) else None
    )
    prev_driven_actuators: set[int] = set()
    act_to_qpos_dof: dict[int, tuple[int, int]] = {
        int(act_id): (int(qpos_adr), int(dof_adr)) for act_id, _j, qpos_adr, dof_adr in actuator_joint_map
    }

    def init_ui_angle_sliders_from_pose() -> None:
        """Initialize UI slider values so the initial target equals the current pose.

        Without this, the viewer's default slider values (often 0) can immediately pull the
        robot away from the keyframe/home pose when --ui-angle is enabled.
        """

        if (not args.ui_angle) or hold_target_qpos is None:
            return

        mode = str(args.ui_angle_mode)
        unlimited_range = float(args.ui_angle_unlimited_range)

        for act_id, joint_id, qpos_adr, _dof_adr in actuator_joint_map:
            ctrl_min = float(model.actuator_ctrlrange[act_id, 0])
            ctrl_max = float(model.actuator_ctrlrange[act_id, 1])
            if not (ctrl_min < ctrl_max):
                # If no ctrlrange, leave as-is.
                continue

            if mode == "offset":
                # Offset mode: zero means "no offset".
                u01 = (0.0 - ctrl_min) / (ctrl_max - ctrl_min)
            else:
                # joint-range mode: choose u01 so desired_q equals the current (home) qpos.
                desired_q = float(hold_target_qpos[qpos_adr])
                u01 = None
                try:
                    if int(model.jnt_limited[joint_id]) == 1:
                        q_min = float(model.jnt_range[joint_id, 0])
                        q_max = float(model.jnt_range[joint_id, 1])
                        if q_min < q_max:
                            u01 = (desired_q - q_min) / (q_max - q_min)
                except Exception:
                    u01 = None
                if u01 is None:
                    # Unlimited joint: center slider corresponds to initial pose.
                    _ = unlimited_range
                    u01 = 0.5

            if u01 < 0.0:
                u01 = 0.0
            elif u01 > 1.0:
                u01 = 1.0
            data.ctrl[act_id] = ctrl_min + u01 * (ctrl_max - ctrl_min)

    base_target_qpos = None
    if args.freeze_base or args.teleop:
        # Convention for models with a root freejoint: qpos[0:7] is [x y z qw qx qy qz].
        if int(model.nq) >= 7 and int(model.nv) >= 6:
            base_target_qpos = data.qpos[:7].copy()
            if args.freeze_base:
                print("[mujoco_sim_view] freeze base enabled")
        else:
            if args.freeze_base:
                print("[mujoco_sim_view] --freeze-base requested but model has no root freejoint")
            base_target_qpos = None

    def apply_freeze_base_hard() -> None:
        """Hard-freeze the base by overwriting state.

        Only safe when we control stepping (headless or viewer=passive).
        """

        if (not args.freeze_base) or base_target_qpos is None:
            return
        data.qpos[:7] = base_target_qpos
        data.qvel[:6] = 0
        mujoco.mj_forward(model, data)

    def quat_conjugate(qw: float, qx: float, qy: float, qz: float) -> tuple[float, float, float, float]:
        return (qw, -qx, -qy, -qz)

    def quat_multiply(
        a: tuple[float, float, float, float],
        b: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        aw, ax, ay, az = a
        bw, bx, by, bz = b
        return (
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        )

    def yaw_from_quat(qw: float, qx: float, qy: float, qz: float) -> float:
        # Standard ZYX yaw extraction.
        siny_cosp = 2.0 * (qw * qz + qx * qy)
        cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
        return math.atan2(siny_cosp, cosy_cosp)

    # Keyboard state (controller.py sends a list of pygame key codes like [119, 97] etc)
    key_lock = threading.Lock()
    teleop_keys: set[int] = set()
    head_keys: set[int] = set()
    wrist_keys: set[int] = set()
    body_keys: set[int] = set()
    active1_keys: set[int] = set()
    active2_keys: set[int] = set()
    move_client = None
    key_clients: list[object] = []

    def parse_key_list(payload: bytes) -> set[int]:
        try:
            s = payload.decode(errors="ignore").strip()
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, tuple)):
                return {int(x) for x in parsed}
        except Exception:
            return set()
        return set()

    if args.teleop:
        try:
            from communication.Client import Client

            def on_move(data_bytes: bytes) -> None:
                keys = parse_key_list(data_bytes)
                with key_lock:
                    teleop_keys.clear()
                    teleop_keys.update(keys)

            move_client = Client(args.server_ip, int(args.server_port), "move", "mujoco_h1", on_move)
            print(f"[mujoco_sim_view] teleop enabled: {args.server_ip}:{args.server_port} group=move")
        except Exception as e:
            raise SystemExit(f"teleop init failed: {e!r}")

    if args.demo_trigger and str(args.demo) == "none":
        print("[mujoco_sim_view] warning: --demo-trigger set but --demo is none; trigger will do nothing")

    if args.key_torque or args.demo_trigger:
        try:
            from communication.Client import Client

            def _mk_cb(target: set[int]):
                def _cb(data_bytes: bytes) -> None:
                    keys = parse_key_list(data_bytes)
                    with key_lock:
                        target.clear()
                        target.update(keys)

                return _cb

            # These group names match controller_module/*.py and pepper_module/* receivers.
            key_clients.append(Client(args.server_ip, int(args.server_port), "head", "mujoco_h1", _mk_cb(head_keys)))
            key_clients.append(Client(args.server_ip, int(args.server_port), "wrist", "mujoco_h1", _mk_cb(wrist_keys)))
            key_clients.append(Client(args.server_ip, int(args.server_port), "body", "mujoco_h1", _mk_cb(body_keys)))
            key_clients.append(Client(args.server_ip, int(args.server_port), "active_1", "mujoco_h1", _mk_cb(active1_keys)))
            key_clients.append(Client(args.server_ip, int(args.server_port), "active_2", "mujoco_h1", _mk_cb(active2_keys)))
            if args.key_torque:
                print(
                    f"[mujoco_sim_view] key-torque enabled: {args.server_ip}:{args.server_port} groups=head,wrist,body,active_1,active_2"
                )
            if args.demo_trigger:
                print(
                    f"[mujoco_sim_view] demo-trigger enabled: press '{str(args.demo_trigger_key)}' in controller.py to replay demo"
                )
        except Exception as e:
            raise SystemExit(f"key-torque init failed: {e!r}")

    demo_trigger_enabled = bool(args.demo_trigger) and str(args.demo) != "none"
    demo_trigger_codes: set[int] = set()
    try:
        k = str(args.demo_trigger_key)
        if k:
            demo_trigger_codes.add(ord(k[0].lower()))
            demo_trigger_codes.add(ord(k[0].upper()))
    except Exception:
        demo_trigger_codes = set()
    demo_play_until: float = -1.0
    prev_demo_key_down: bool = False

    def update_demo_trigger(sim_t: float) -> None:
        """Update demo playback window based on controller key lists."""

        nonlocal demo_play_until, prev_demo_key_down
        if not demo_trigger_enabled or not demo_trigger_codes:
            return

        with key_lock:
            keys = set(teleop_keys)
            keys |= set(head_keys)
            keys |= set(wrist_keys)
            keys |= set(body_keys)
            keys |= set(active1_keys)
            keys |= set(active2_keys)

        down = any(int(code) in keys for code in demo_trigger_codes)
        if down and (not prev_demo_key_down):
            dur = float(args.demo_duration)
            if dur <= 0:
                dur = 0.1
            demo_play_until = float(sim_t) + dur
        prev_demo_key_down = bool(down)

    def teleop_desired_local_vel() -> tuple[float, float, float]:
        if not args.teleop:
            return (0.0, 0.0, 0.0)
        with key_lock:
            keys = set(teleop_keys)

        key_w, key_a, key_s, key_d, key_q, key_e = (
            ord("w"),
            ord("a"),
            ord("s"),
            ord("d"),
            ord("q"),
            ord("e"),
        )
        vx = 0.0
        vy = 0.0
        wz = 0.0
        speed = float(args.teleop_speed)
        yaw_rate = float(args.teleop_yaw_rate)
        if key_w in keys:
            vx += speed
        if key_s in keys:
            vx -= speed
        if key_a in keys:
            vy += speed
        if key_d in keys:
            vy -= speed
        if key_q in keys:
            wz += yaw_rate
        if key_e in keys:
            wz -= yaw_rate
        return (vx, vy, wz)

    def _act_id_by_name(name: str) -> int | None:
        act_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
        if int(act_id) >= 0:
            return int(act_id)
        return None

    # Pepper-key -> H1 actuator mapping (best-effort)
    key_torque_map: dict[int, list[tuple[int, float]]] = {}
    if args.key_torque:
        # Helper to add mapping for both +/- directions.
        def _bind(ch: str, act_name: str, sign: float) -> None:
            act_id = _act_id_by_name(act_name)
            if act_id is None:
                return
            key_torque_map.setdefault(ord(ch), []).append((act_id, float(sign)))

        # active_1 (F3 单手) -> shoulders
        _bind("j", "right_shoulder_pitch", -1.0)
        _bind("n", "right_shoulder_pitch", +1.0)
        _bind("h", "left_shoulder_pitch", -1.0)
        _bind("b", "left_shoulder_pitch", +1.0)
        _bind("g", "right_shoulder_roll", -1.0)
        _bind("v", "right_shoulder_roll", +1.0)
        _bind("c", "left_shoulder_roll", -1.0)
        _bind("f", "left_shoulder_roll", +1.0)

        # wrist (F6) -> elbows (H1 has no wrist actuators)
        _bind("k", "left_elbow", -1.0)
        _bind("l", "left_elbow", +1.0)
        _bind("o", "right_elbow", -1.0)
        _bind("p", "right_elbow", +1.0)

        # body (F5) -> torso pitch (Pepper HipPitch)
        _bind(";", "torso", +1.0)
        _bind(".", "torso", -1.0)

        # active_2 (F2 双手) -> both shoulders (arrow keys)
        # pygame arrow key codes as sent by controller: UP/DOWN/LEFT/RIGHT
        K_UP, K_DOWN, K_LEFT, K_RIGHT = 1073741906, 1073741905, 1073741904, 1073741903
        left_sh_pitch = _act_id_by_name("left_shoulder_pitch")
        right_sh_pitch = _act_id_by_name("right_shoulder_pitch")
        left_sh_roll = _act_id_by_name("left_shoulder_roll")
        right_sh_roll = _act_id_by_name("right_shoulder_roll")
        if left_sh_pitch is not None and right_sh_pitch is not None:
            key_torque_map.setdefault(K_UP, []).extend([(left_sh_pitch, -1.0), (right_sh_pitch, -1.0)])
            key_torque_map.setdefault(K_DOWN, []).extend([(left_sh_pitch, +1.0), (right_sh_pitch, +1.0)])
        if left_sh_roll is not None and right_sh_roll is not None:
            key_torque_map.setdefault(K_LEFT, []).extend([(left_sh_roll, -1.0), (right_sh_roll, +1.0)])
            key_torque_map.setdefault(K_RIGHT, []).extend([(left_sh_roll, +1.0), (right_sh_roll, -1.0)])

        if not key_torque_map:
            print("[mujoco_sim_view] key-torque: warning: no actuators matched mapping")
        else:
            print("[mujoco_sim_view] key-torque mapping loaded (press keys in controller modes F2/F3/F5/F6)")

    def apply_key_torque() -> None:
        if not args.key_torque:
            return
        # Compose active keys from all relevant groups.
        with key_lock:
            keys = set()
            keys |= set(head_keys)
            keys |= set(wrist_keys)
            keys |= set(body_keys)
            keys |= set(active1_keys)
            keys |= set(active2_keys)

        mag = float(args.key_torque_mag)
        bias: dict[int, float] = {}
        driven_actuators: set[int] = set()
        for k in keys:
            for act_id, sign in key_torque_map.get(int(k), []):
                driven_actuators.add(int(act_id))
                bias[int(act_id)] = float(bias.get(int(act_id), 0.0)) + mag * float(sign)

        # Clamp bias to each actuator's ctrlrange.
        for act_id, tau in list(bias.items()):
            ctrl_min = float(model.actuator_ctrlrange[int(act_id), 0])
            ctrl_max = float(model.actuator_ctrlrange[int(act_id), 1])
            if ctrl_min < ctrl_max:
                if tau < ctrl_min:
                    tau = ctrl_min
                elif tau > ctrl_max:
                    tau = ctrl_max
            bias[int(act_id)] = float(tau)

        if bool(args.key_torque_hold):
            apply_key_torque_hold(bias, driven_actuators)
            return

        # Pure torque mode.
        data.ctrl[:] = 0
        for act_id, tau in bias.items():
            data.ctrl[int(act_id)] = float(tau)

    def apply_base_stabilization_pd(t: float) -> None:
        """Stabilize the root freejoint using generalized forces (soft freeze).

        This works even when the viewer drives stepping (viewer=launch).
        """

        if base_target_qpos is None:
            return

        # Clear previously applied forces on the base dofs.
        data.qfrc_applied[:6] = 0

        # In teleop mode we do XY velocity tracking (no position hold), but keep Z height.
        vx_local, vy_local, wz_des = teleop_desired_local_vel()
        if int(model.nq) >= 7:
            yaw = yaw_from_quat(float(data.qpos[3]), float(data.qpos[4]), float(data.qpos[5]), float(data.qpos[6]))
        else:
            yaw = 0.0
        cy = math.cos(yaw)
        sy = math.sin(yaw)
        vx_des = cy * vx_local - sy * vy_local
        vy_des = sy * vx_local + cy * vy_local

        kp_pos_xy = 0.0 if args.teleop else 2000.0
        kd_pos_xy = 200.0
        kv_vel_xy = 350.0
        kp_pos_z = 2000.0
        kd_pos_z = 250.0
        ex = float(base_target_qpos[0] - data.qpos[0])
        ey = float(base_target_qpos[1] - data.qpos[1])
        ez = float(base_target_qpos[2] - data.qpos[2])
        vx = float(data.qvel[0])
        vy = float(data.qvel[1])
        vz = float(data.qvel[2])
        data.qfrc_applied[0] = kp_pos_xy * ex - kd_pos_xy * vx + kv_vel_xy * (vx_des - vx)
        data.qfrc_applied[1] = kp_pos_xy * ey - kd_pos_xy * vy + kv_vel_xy * (vy_des - vy)
        data.qfrc_applied[2] = kp_pos_z * ez - kd_pos_z * vz

        # Orientation PD on root quaternion (qpos[3:7] = [w x y z]).
        kp_rot = 900.0
        kd_rot = 80.0
        qw_d, qx_d, qy_d, qz_d = (float(base_target_qpos[3]), float(base_target_qpos[4]), float(base_target_qpos[5]), float(base_target_qpos[6]))
        qw, qx, qy, qz = (float(data.qpos[3]), float(data.qpos[4]), float(data.qpos[5]), float(data.qpos[6]))
        q_err = quat_multiply((qw_d, qx_d, qy_d, qz_d), quat_conjugate(qw, qx, qy, qz))
        ew, ex, ey, ez = q_err
        # Small-angle approximation: angle-axis vector ~= 2 * sign(w) * v
        s = 1.0 if ew >= 0 else -1.0
        ax = 2.0 * s * float(ex)
        ay = 2.0 * s * float(ey)
        az = 2.0 * s * float(ez)
        wx = float(data.qvel[3])
        wy = float(data.qvel[4])
        wz = float(data.qvel[5])
        if args.teleop:
            az = 0.0
        data.qfrc_applied[3] = kp_rot * ax - kd_rot * wx
        data.qfrc_applied[4] = kp_rot * ay - kd_rot * wy
        if args.teleop:
            kw_yaw = 120.0
            data.qfrc_applied[5] = kw_yaw * (wz_des - wz)
        else:
            data.qfrc_applied[5] = kp_rot * az - kd_rot * wz

    def demo_delta_for_actuator(act_id: int, t: float) -> float:
        if args.demo == "none":
            return 0.0

        # Use simulation time as the demo time base for consistent playback.
        t = float(data.time)

        # If demo-trigger is enabled, only play inside the trigger window.
        if demo_trigger_enabled and float(data.time) > float(demo_play_until):
            return 0.0

        act_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, act_id)
        if not act_name:
            return 0.0

        amp = float(args.demo_amp)
        w = 2.0 * math.pi * float(args.demo_freq)

        if args.demo == "wave":
            # Simple arm wave: shoulder pitch +/- and elbow flex.
            if act_name in {"left_shoulder_pitch", "right_shoulder_pitch"}:
                sign = 1.0 if act_name.startswith("left_") else -1.0
                return sign * amp * math.sin(w * t)
            if act_name in {"left_elbow", "right_elbow"}:
                return 0.7 * amp * (0.5 + 0.5 * math.sin(w * t + math.pi / 2.0))
            return 0.0

        if args.demo == "squat":
            # Very rough squat: knees and hips.
            if act_name in {"left_knee", "right_knee"}:
                return 0.9 * amp * (0.5 + 0.5 * math.sin(w * t))
            if act_name in {"left_hip_pitch", "right_hip_pitch"}:
                return -0.6 * amp * (0.5 + 0.5 * math.sin(w * t))
            if act_name in {"left_ankle", "right_ankle"}:
                return 0.4 * amp * (0.5 + 0.5 * math.sin(w * t))
            return 0.0

        return 0.0

    def apply_hold_pd(t: float) -> None:
        if (not args.hold) or hold_target_qpos is None:
            return
        kp = float(args.hold_kp)
        kd = float(args.hold_kd)
        for act_id, _joint_id, qpos_adr, dof_adr in actuator_joint_map:
            ui_bias = float(data.ctrl[act_id]) if args.hold_add_ui else 0.0
            q_des = float(hold_target_qpos[qpos_adr]) + demo_delta_for_actuator(act_id, t)
            q = float(data.qpos[qpos_adr])
            qd = float(data.qvel[dof_adr])
            tau = kp * (q_des - q) - kd * qd + ui_bias

            ctrl_min = float(model.actuator_ctrlrange[act_id, 0])
            ctrl_max = float(model.actuator_ctrlrange[act_id, 1])
            if ctrl_min < ctrl_max:
                if tau < ctrl_min:
                    tau = ctrl_min
                elif tau > ctrl_max:
                    tau = ctrl_max
            data.ctrl[act_id] = tau

    def apply_hold_pd_with_bias(t: float, bias: dict[int, float]) -> None:
        if hold_target_qpos is None:
            return
        kp = float(args.hold_kp)
        kd = float(args.hold_kd)
        for act_id, _joint_id, qpos_adr, dof_adr in actuator_joint_map:
            tau_bias = float(bias.get(int(act_id), 0.0))
            q_des = float(hold_target_qpos[qpos_adr]) + demo_delta_for_actuator(act_id, t)
            q = float(data.qpos[qpos_adr])
            qd = float(data.qvel[dof_adr])
            tau = kp * (q_des - q) - kd * qd + tau_bias

            ctrl_min = float(model.actuator_ctrlrange[act_id, 0])
            ctrl_max = float(model.actuator_ctrlrange[act_id, 1])
            if ctrl_min < ctrl_max:
                if tau < ctrl_min:
                    tau = ctrl_min
                elif tau > ctrl_max:
                    tau = ctrl_max
            data.ctrl[act_id] = tau

    def apply_key_torque_hold(bias: dict[int, float], driven_actuators: set[int]) -> None:
        """Hold all joints stiff except those currently driven by keys.

        Desired semantics:
          - Key held: relax that joint (no PD hold), apply constant torque.
          - Key released: lock the joint at its current angle.
        """

        nonlocal prev_driven_actuators

        if key_hold_target_qpos is None:
            return

        # On release transitions, capture current joint angle as the new target.
        released = set(prev_driven_actuators) - set(driven_actuators)
        for act_id in released:
            idx = act_to_qpos_dof.get(int(act_id))
            if idx is None:
                continue
            qpos_adr, _dof_adr = idx
            key_hold_target_qpos[qpos_adr] = float(data.qpos[qpos_adr])

        prev_driven_actuators = set(driven_actuators)

        kp = float(args.hold_kp)
        kd = float(args.hold_kd)
        t = float(data.time)

        for act_id, _joint_id, qpos_adr, dof_adr in actuator_joint_map:
            if int(act_id) in driven_actuators:
                # Relax this joint: torque only.
                data.ctrl[act_id] = float(bias.get(int(act_id), 0.0))
                continue

            q_des = float(key_hold_target_qpos[qpos_adr]) + demo_delta_for_actuator(act_id, t)
            q = float(data.qpos[qpos_adr])
            qd = float(data.qvel[dof_adr])
            tau = kp * (q_des - q) - kd * qd

            ctrl_min = float(model.actuator_ctrlrange[act_id, 0])
            ctrl_max = float(model.actuator_ctrlrange[act_id, 1])
            if ctrl_min < ctrl_max:
                if tau < ctrl_min:
                    tau = ctrl_min
                elif tau > ctrl_max:
                    tau = ctrl_max
            data.ctrl[act_id] = tau

    def apply_ui_angle_pd(sim_t: float) -> None:
        """UI sliders -> target angle offsets -> PD torques applied via qfrc_applied.

        We intentionally do NOT write torques into data.ctrl, otherwise the sliders would jump.
        Instead, in passive stepping we:
          - read slider values from data.ctrl
          - zero data.ctrl before mj_step (disables actuators)
          - apply torques via data.qfrc_applied
          - restore data.ctrl after mj_step for UI display
        """

        nonlocal last_time_for_ui
        if (not args.ui_angle) or hold_target_qpos is None or ui_angle_target_qpos is None:
            return

        # dt based on simulation time to be stable.
        dt = float(data.time) - float(last_time_for_ui)
        if dt <= 0:
            dt = float(model.opt.timestep)
        last_time_for_ui = float(data.time)

        ctrl_snapshot = data.ctrl.copy()

        # MuJoCo viewer's "Clear all" sets all sliders to 0.
        # In ui-angle mode, we treat this as "reset to the initial (keyframe/home) pose".
        if ctrl_snapshot.size > 0 and bool((abs(ctrl_snapshot) < 1e-12).all()):
            # Reset internal target.
            ui_angle_target_qpos[:] = hold_target_qpos
            # Reset slider display/values back to the initial pose mapping.
            init_ui_angle_sliders_from_pose()
            ctrl_snapshot = data.ctrl.copy()

        speed = float(args.ui_angle_speed)
        scale = float(args.ui_angle_scale)
        mode = str(args.ui_angle_mode)
        unlimited_range = float(args.ui_angle_unlimited_range)

        kp = float(args.hold_kp)
        kd = float(args.hold_kd)

        max_step = max(0.0, speed * dt)
        for act_id, joint_id, qpos_adr, dof_adr in actuator_joint_map:
            # Slider normalization based on actuator ctrlrange.
            ctrl_min = float(model.actuator_ctrlrange[act_id, 0])
            ctrl_max = float(model.actuator_ctrlrange[act_id, 1])
            v = float(ctrl_snapshot[act_id])
            if ctrl_min < ctrl_max:
                u01 = (v - ctrl_min) / (ctrl_max - ctrl_min)
                if u01 < 0.0:
                    u01 = 0.0
                elif u01 > 1.0:
                    u01 = 1.0
            else:
                # Fallback if ctrlrange is not set.
                u01 = 0.5

            if mode == "joint-range":
                # Prefer mapping slider min/max to joint min/max if the joint is limited.
                desired_q = None
                try:
                    if int(model.jnt_limited[joint_id]) == 1:
                        q_min = float(model.jnt_range[joint_id, 0])
                        q_max = float(model.jnt_range[joint_id, 1])
                        if q_min < q_max:
                            desired_q = q_min + u01 * (q_max - q_min)
                except Exception:
                    desired_q = None

                if desired_q is None:
                    # If unlimited / range unavailable: use a symmetric range around initial pose.
                    q0 = float(hold_target_qpos[qpos_adr])
                    s = (u01 - 0.5) * 2.0
                    desired_q = q0 + s * unlimited_range
            else:
                # Legacy: ctrl directly represents an offset scale.
                desired_offset = v * scale
                desired_q = float(hold_target_qpos[qpos_adr]) + desired_offset

            cur_q = float(ui_angle_target_qpos[qpos_adr])
            delta = desired_q - cur_q
            if delta > max_step:
                delta = max_step
            elif delta < -max_step:
                delta = -max_step
            ui_angle_target_qpos[qpos_adr] = cur_q + delta

            q_des = float(ui_angle_target_qpos[qpos_adr])
            q = float(data.qpos[qpos_adr])
            qd = float(data.qvel[dof_adr])
            tau = kp * (q_des - q) - kd * qd

            # Clamp to actuator limits for safety.
            if ctrl_min < ctrl_max:
                if tau < ctrl_min:
                    tau = ctrl_min
                elif tau > ctrl_max:
                    tau = ctrl_max

            # Apply to generalized force at this dof.
            data.qfrc_applied[dof_adr] += tau

    start = time.time()

    if args.headless:
        init_ui_angle_sliders_from_pose()
        duration = float(args.duration) if args.duration and args.duration > 0 else 1.0
        end_t = start + duration
        print(f"[mujoco_sim_view] headless stepping for {duration:.3f}s")
        try:
            while time.time() < end_t:
                t = time.time() - start
                update_demo_trigger(float(data.time))
                data.qfrc_applied[:] = 0
                if args.ui_angle:
                    apply_ui_angle_pd(t)
                else:
                    apply_hold_pd(t)
                apply_key_torque()
                apply_base_stabilization_pd(t)
                mujoco.mj_step(model, data)
                apply_freeze_base_hard()
        except KeyboardInterrupt:
            print("[mujoco_sim_view] interrupted (Ctrl+C)")
        print("[mujoco_sim_view] done")
        if move_client is not None:
            move_client.stop()
        for c in key_clients:
            try:
                c.stop()
            except Exception:
                pass
        return

    try:
        import mujoco.viewer as mj_viewer  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "无法导入 mujoco.viewer（OpenGL/窗口依赖可能缺失）。\n"
            "你可以先用 --headless 验证模型能加载：\n"
            "  ... mujoco_sim_view.py --model <model.xml> --headless --duration 1\n"
            f"原始错误: {e!r}"
        )

    if args.viewer == "passive":
        print("[mujoco_sim_view] launching viewer (passive)...")
        init_ui_angle_sliders_from_pose()
        with mj_viewer.launch_passive(model, data) as viewer:
            print("[mujoco_sim_view] viewer running")
            try:
                # Simple realtime-ish pacing to avoid maxing out CPU in passive mode.
                # We target model.opt.timestep wall-clock per step.
                target_dt = float(model.opt.timestep)
                while viewer.is_running():
                    loop_start = time.time()

                    t = loop_start - start
                    update_demo_trigger(float(data.time))
                    data.qfrc_applied[:] = 0
                    if args.ui_angle:
                        apply_ui_angle_pd(t)
                    else:
                        apply_hold_pd(t)
                    apply_key_torque()
                    apply_base_stabilization_pd(t)
                    mujoco.mj_step(model, data)
                    apply_freeze_base_hard()
                    viewer.sync()

                    if args.duration and args.duration > 0:
                        if loop_start - start >= float(args.duration):
                            break

                    elapsed = time.time() - loop_start
                    remaining = target_dt - elapsed
                    if remaining > 0:
                        time.sleep(min(0.005, remaining))
            except KeyboardInterrupt:
                print("[mujoco_sim_view] interrupted (Ctrl+C)")
        if move_client is not None:
            move_client.stop()
        for c in key_clients:
            try:
                c.stop()
            except Exception:
                pass
        return

    # viewer=launch: the viewer drives stepping, so we attach a control callback.
    def mj_control_callback(m: mujoco.MjModel, d: mujoco.MjData) -> None:  # noqa: ARG001
        t = float(d.time)
        update_demo_trigger(t)
        # In viewer=launch, we can still support ui-angle by applying generalized forces
        # while keeping d.ctrl intact for UI display.
        if args.ui_angle:
            d.qfrc_applied[:] = 0
            apply_ui_angle_pd(t)
            apply_base_stabilization_pd(t)
            return

        if args.key_torque:
            # key-torque writes actuator commands; base stabilization may also apply qfrc.
            apply_key_torque()
            apply_base_stabilization_pd(t)
            return

        apply_hold_pd(t)
        apply_base_stabilization_pd(t)

    old_cb = mujoco.get_mjcb_control()
    mujoco.set_mjcb_control(mj_control_callback)
    try:
        print("[mujoco_sim_view] launching viewer (launch, blocking)...")
        init_ui_angle_sliders_from_pose()
        mj_viewer.launch(model, data)
    finally:
        mujoco.set_mjcb_control(old_cb)
        if move_client is not None:
            move_client.stop()
        for c in key_clients:
            try:
                c.stop()
            except Exception:
                pass


if __name__ == "__main__":
    main()
