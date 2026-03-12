"""MuJoCo viewer: play a JSONL joint-angle trajectory on Unitree H1.

This is meant for quick visualization/debugging.

Typical usage (Windows):
  cd mujoco_menagerie/unitree_h1
    F:/anaconda/envs/pepper_env/python.exe ../../tools/mujoco_play_trajectory.py --model scene.xml \
        --jsonl ../../naoqi-pose-retargeting/converted_outputs/unitree_h1_upper_body_trajectory.jsonl \
    --keyframe home --freeze-base
"""

from __future__ import annotations

import argparse
import faulthandler
import ast
import json
import os
import sys
import time
import traceback
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure repo root is on sys.path (consistent with tools/mujoco_sim_view.py)
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Best-effort crash diagnostics (helps when the MuJoCo window "flashes" then the process dies).
_CRASH_LOG = Path(_REPO_ROOT) / "mujoco_play_trajectory_crash.log"
try:
    _CRASH_FH = _CRASH_LOG.open("a", encoding="utf-8")
    faulthandler.enable(file=_CRASH_FH, all_threads=True)
except Exception:
    try:
        faulthandler.enable(all_threads=True)
    except Exception:
        pass

try:
    import mujoco  # type: ignore[import-not-found]
    import mujoco.viewer as mj_viewer  # type: ignore[import-not-found]
except Exception as e:  # pragma: no cover
    raise SystemExit(
        "无法导入 mujoco/mujoco.viewer。\n"
        "如果你在 Windows 上，建议使用已安装 mujoco 的解释器运行，例如：\n"
        "  F:\\anaconda\\envs\\pepper_env\\python.exe tools\\mujoco_play_trajectory.py --model <model.xml> --jsonl <traj.jsonl>\n"
        f"原始错误: {e!r}"
    )


@dataclass
class Frame:
    t: float
    angles: Dict[str, float]


def load_jsonl(path: Path) -> List[Frame]:
    frames: List[Frame] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            t = float(obj["video_timestamp"])
            names = list(obj["joint_names"])
            angles = list(obj["angles"])
            frames.append(Frame(t=t, angles={n: float(a) for n, a in zip(names, angles)}))
    frames.sort(key=lambda x: x.t)
    return frames


def _reset_to_keyframe(model: mujoco.MjModel, data: mujoco.MjData, keyframe: str) -> None:
    if not keyframe:
        return
    key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, str(keyframe))
    if int(key_id) < 0:
        print(f"[mujoco_play_trajectory] keyframe not found: {keyframe}")
        return
    mujoco.mj_resetDataKeyframe(model, data, int(key_id))
    mujoco.mj_forward(model, data)
    print(f"[mujoco_play_trajectory] reset to keyframe: {keyframe}")


def _build_joint_qpos_map(model: mujoco.MjModel) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for jnt_id in range(int(model.njnt)):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jnt_id) or ""
        if not name:
            continue
        adr = int(model.jnt_qposadr[jnt_id])
        out[name] = adr
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="MuJoCo play JSONL trajectory")
    parser.add_argument("--model", required=True, help="MJCF .xml path (e.g. scene.xml)")
    parser.add_argument("--jsonl", required=True, help="Trajectory JSONL path")
    parser.add_argument("--keyframe", default="home", help="Reset to keyframe name after load")
    parser.add_argument("--freeze-base", action="store_true", help="Freeze root freejoint pose to prevent falling")
    parser.add_argument(
        "--viewer",
        choices=["launch", "passive", "glfw"],
        default="launch",
        help=(
            "Viewer backend. 'launch' is more robust on Windows (blocks until window closed). "
            "'passive' lets this script drive stepping (may hang on some Windows drivers). "
            "'glfw' uses a minimal custom GLFW renderer (supports in-window replay hotkey and avoids passive thread issues)."
        ),
    )
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    parser.add_argument("--start-at", type=float, default=0.0, help="Start at video_timestamp (sec)")
    parser.add_argument("--stop-at", type=float, default=None, help="Stop at video_timestamp (sec)")
    parser.add_argument(
        "--replay-key",
        type=str,
        default="r",
        help=(
            "Replay hotkey inside the MuJoCo window (viewer=passive or viewer=glfw). "
            "Press this key to restart playback without closing the window. Default: r"
        ),
    )
    parser.add_argument(
        "--passive-timeout",
        type=float,
        default=8.0,
        help=(
            "Timeout (sec) for viewer=passive startup. If the window thread fails to start and launch_passive blocks, "
            "we abort with a clear message instead of hanging forever. Use 0 to disable."
        ),
    )
    parser.add_argument(
        "--replay-controller",
        action="store_true",
        help=(
            "Trigger replay from controller.py via server.py (more robust than viewer=passive on Windows). "
            "When enabled, press the trigger key in controller (default: '1' in F3 单手模式) to restart playback."
        ),
    )
    parser.add_argument("--server-ip", default="127.0.0.1", help="server.py IP (for --replay-controller)")
    parser.add_argument("--server-port", type=int, default=5556, help="server.py port (for --replay-controller)")
    parser.add_argument(
        "--replay-controller-key",
        type=str,
        default="1",
        help="Controller trigger key (single character) used by --replay-controller. Default: 1",
    )
    parser.add_argument(
        "--exit-on-finish",
        action="store_true",
        help="Exit immediately when playback finishes (otherwise hold last pose until window closed)",
    )
    parser.add_argument(
        "--ui-editable-after-finish",
        action="store_true",
        help=(
            "After playback finishes, stop overwriting joint qpos so you can edit joints in the MuJoCo UI (right panel). "
            "If --freeze-base is enabled, the root pose will still be enforced."
        ),
    )
    parser.add_argument(
        "--apply-once",
        action="store_true",
        help=(
            "Apply only the first pose once, then stop driving qpos so the pose becomes editable in the MuJoCo UI. "
            "Useful for single-frame preview + manual tweaking."
        ),
    )
    parser.add_argument("--dt", type=float, default=0.0, help="Override timestep; 0 uses model timestep")
    args = parser.parse_args()

    model_path = Path(args.model).resolve()
    traj_path = Path(args.jsonl).resolve()
    if not model_path.exists():
        raise SystemExit(f"Model not found: {model_path}")
    if not traj_path.exists():
        raise SystemExit(f"Trajectory JSONL not found: {traj_path}")

    # Important: meshdir/assets are relative to the MJCF file location.
    # To avoid surprises, change CWD to the model directory.
    os.chdir(str(model_path.parent))

    print(f"[mujoco_play_trajectory] loading model: {model_path.name} (cwd={Path.cwd()})")
    model = mujoco.MjModel.from_xml_path(str(model_path.name))
    data = mujoco.MjData(model)

    if args.dt and args.dt > 0:
        model.opt.timestep = float(args.dt)

    _reset_to_keyframe(model, data, str(args.keyframe))

    frames = load_jsonl(traj_path)
    if not frames:
        raise SystemExit("Trajectory is empty")

    # Find start frame time
    start_at = float(args.start_at)
    start_idx = 0
    while start_idx < len(frames) and frames[start_idx].t < start_at:
        start_idx += 1
    if start_idx >= len(frames):
        raise SystemExit("start-at out of range")

    t0_video = frames[start_idx].t
    t_end = frames[-1].t
    stop_at = float(args.stop_at) if args.stop_at is not None else None

    speed = max(float(args.speed), 1e-6)

    joint_qpos = _build_joint_qpos_map(model)

    # Cache initial pose
    initial_qpos = data.qpos.copy()
    initial_qvel = data.qvel.copy() if hasattr(data, "qvel") else None

    base_qpos: Optional[List[float]] = None
    if bool(args.freeze_base) and int(model.nq) >= 7:
        # Assume the first 7 qpos correspond to freejoint root.
        base_qpos = [float(x) for x in initial_qpos[:7]]
        print("[mujoco_play_trajectory] freeze-base enabled")

    print(
        "[mujoco_play_trajectory] playing:"
        f" jsonl={traj_path} | speed={speed} | start={t0_video:.3f}s | end={t_end:.3f}s"
    )

    err_log = Path(_REPO_ROOT) / "mujoco_play_trajectory_error.txt"
    try:
        if err_log.exists():
            err_log.unlink()
    except Exception:
        pass

    idx = start_idx
    last_qpos = data.qpos.copy()
    finished = False
    drive_pose = True
    last_sim_time: float | None = None
    stalled_sim_steps = 0

    replay_codes: set[int] = set()
    try:
        k = str(args.replay_key)
        if k:
            replay_codes.add(ord(k[0].lower()))
            replay_codes.add(ord(k[0].upper()))
    except Exception:
        replay_codes = set()
    replay_requested = False

    replay_key_label = ""
    try:
        k = str(args.replay_key)
        replay_key_label = k[0] if k else ""
    except Exception:
        replay_key_label = ""

    # Optional replay trigger from controller/server.
    key_lock = threading.Lock()
    controller_keys: set[int] = set()
    controller_trigger_codes: set[int] = set()
    try:
        k = str(args.replay_controller_key)
        if k:
            controller_trigger_codes.add(ord(k[0].lower()))
            controller_trigger_codes.add(ord(k[0].upper()))
    except Exception:
        controller_trigger_codes = set()

    def _parse_key_list(payload: bytes) -> set[int]:
        try:
            s = payload.decode(errors="ignore").strip()
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, tuple)):
                return {int(x) for x in parsed}
        except Exception:
            return set()
        return set()

    if bool(args.replay_controller):
        try:
            from communication.Client import Client  # type: ignore

            def _on_keys(data_bytes: bytes) -> None:
                keys = _parse_key_list(data_bytes)
                with key_lock:
                    controller_keys.clear()
                    controller_keys.update(keys)

            # Listen on active_1 because controller_module/动作单手.py includes '1'/'2'/'3'.
            _client = Client(args.server_ip, int(args.server_port), "active_1", "mujoco_traj", _on_keys)
            print(
                f"[mujoco_play_trajectory] replay-controller enabled: {args.server_ip}:{args.server_port} group=active_1 key='{args.replay_controller_key}'"
            )
        except Exception as e:
            print(f"[mujoco_play_trajectory] replay-controller init failed (ignored): {e!r}")
            _client = None
    else:
        _client = None

    def _apply_freeze_base_only(d: mujoco.MjData) -> None:
        if base_qpos is None:
            return
        d.qpos[:7] = base_qpos
        if int(model.nv) >= 6:
            d.qvel[:6] = 0.0


    def _apply_pose(d: mujoco.MjData, now_video: float) -> None:
        nonlocal idx, finished, last_qpos

        if finished:
            d.qpos[:] = last_qpos
        else:
            if stop_at is not None and now_video > stop_at:
                finished = True
                d.qpos[:] = last_qpos
            elif now_video > t_end:
                finished = True
                d.qpos[:] = last_qpos
            else:
                while idx + 1 < len(frames) and frames[idx + 1].t <= now_video:
                    idx += 1

                fr0 = frames[idx]
                fr1 = frames[idx + 1] if idx + 1 < len(frames) else fr0

                t0 = fr0.t
                t1 = fr1.t
                if t1 - t0 > 1e-9:
                    alpha = (now_video - t0) / (t1 - t0)
                    if alpha < 0.0:
                        alpha = 0.0
                    if alpha > 1.0:
                        alpha = 1.0
                else:
                    alpha = 0.0

                d.qpos[:] = initial_qpos
                if initial_qvel is not None:
                    d.qvel[:] = initial_qvel

                if base_qpos is not None:
                    d.qpos[:7] = base_qpos
                    if int(model.nv) >= 6:
                        d.qvel[:6] = 0.0

                for name, a0 in fr0.angles.items():
                    adr = joint_qpos.get(name)
                    if adr is None:
                        continue
                    a1 = fr1.angles.get(name, a0)
                    d.qpos[adr] = (1.0 - alpha) * float(a0) + alpha * float(a1)

                last_qpos[:] = d.qpos

        if base_qpos is not None:
            d.qpos[:7] = base_qpos
            if int(model.nv) >= 6:
                d.qvel[:6] = 0.0

    if args.viewer == "glfw":
        try:
            import glfw  # type: ignore[import-not-found]
        except Exception as e:
            raise SystemExit(f"glfw not available: {e!r}")

        if not glfw.init():
            raise SystemExit("glfw.init() failed")

        try:
            glfw.window_hint(glfw.VISIBLE, glfw.TRUE)
            glfw.window_hint(glfw.SAMPLES, 4)
        except Exception:
            pass

        width, height = 1280, 720
        window = glfw.create_window(width, height, "MuJoCo Trajectory Player", None, None)
        if not window:
            glfw.terminate()
            raise SystemExit("glfw.create_window() failed")

        glfw.make_context_current(window)
        glfw.swap_interval(1)
        try:
            glfw.show_window(window)
        except Exception:
            pass
        try:
            glfw.set_window_should_close(window, False)
        except Exception:
            pass

        if replay_key_label:
            print(
                f"[mujoco_play_trajectory] glfw viewer running: press '{replay_key_label.upper()}' to replay, 'ESC' to exit"
            )
        else:
            print("[mujoco_play_trajectory] glfw viewer running: press replay key to replay, 'ESC' to exit")

        # Replay on character input (so it matches --replay-key).
        def _on_char(_window, codepoint: int) -> None:  # noqa: ANN001
            nonlocal replay_requested
            if replay_codes and int(codepoint) in replay_codes:
                replay_requested = True

        def _on_key(_window, key: int, _scancode: int, action: int, _mods: int) -> None:  # noqa: ANN001
            if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
                glfw.set_window_should_close(window, True)

        glfw.set_char_callback(window, _on_char)
        glfw.set_key_callback(window, _on_key)

        cam = mujoco.MjvCamera()
        opt = mujoco.MjvOption()
        scn = mujoco.MjvScene(model, maxgeom=10000)
        ctx = mujoco.MjrContext(model, mujoco.mjtFontScale.mjFONTSCALE_150)
        mujoco.mjv_defaultCamera(cam)
        mujoco.mjv_defaultOption(opt)

        t0_wall = time.perf_counter()
        try:
            first_iter = True
            while first_iter or (not glfw.window_should_close(window)):
                first_iter = False
                glfw.poll_events()

                now_video = t0_video

                if replay_requested:
                    replay_requested = False
                    finished = False
                    idx = start_idx
                    t0_wall = time.perf_counter()
                    drive_pose = True

                if drive_pose:
                    if bool(args.apply_once):
                        _apply_pose(data, t0_video)
                        finished = True
                        drive_pose = False
                    else:
                        now_wall = time.perf_counter()
                        now_video = t0_video + (now_wall - t0_wall) * speed
                        _apply_pose(data, now_video)
                        if finished and bool(args.ui_editable_after_finish):
                            drive_pose = False
                else:
                    _apply_freeze_base_only(data)
                mujoco.mj_forward(model, data)
                mujoco.mj_step(model, data)

                fb_w, fb_h = glfw.get_framebuffer_size(window)
                viewport = mujoco.MjrRect(0, 0, int(fb_w), int(fb_h))
                mujoco.mjv_updateScene(
                    model,
                    data,
                    opt,
                    None,
                    cam,
                    mujoco.mjtCatBit.mjCAT_ALL,
                    scn,
                )
                mujoco.mjr_render(viewport, scn, ctx)

                # Minimal on-screen UI hint.
                try:
                    mujoco.mjr_overlay(
                        mujoco.mjtFontScale.mjFONTSCALE_150,
                        mujoco.mjtGridPos.mjGRID_TOPLEFT,
                        viewport,
                        f"{replay_key_label.upper() or '?'}: replay   ESC: exit",
                        f"t={now_video:.2f}s  speed={speed:g}",
                        ctx,
                    )
                except Exception:
                    pass
                glfw.swap_buffers(window)

                # Simple pacing.
                time.sleep(min(float(model.opt.timestep) / speed, 0.01))
        except KeyboardInterrupt:
            print("[mujoco_play_trajectory] interrupted by Ctrl+C (use ESC inside the window to exit cleanly)")
        finally:
            try:
                glfw.destroy_window(window)
            except Exception:
                pass
            glfw.terminate()

    elif args.viewer == "passive":
        def _launch_passive_with_timeout():
            timeout = float(args.passive_timeout)
            if timeout <= 0:
                return mj_viewer.launch_passive(model, data, key_callback=_on_key)

            box: dict[str, object] = {}
            err: dict[str, BaseException] = {}

            def _worker() -> None:
                try:
                    box["handle"] = mj_viewer.launch_passive(model, data, key_callback=_on_key)
                except BaseException as e:
                    err["e"] = e

            th = threading.Thread(target=_worker, daemon=True)
            th.start()
            th.join(timeout=timeout)
            if th.is_alive():
                raise TimeoutError(
                    "viewer=passive 启动超时（MuJoCo 窗口线程未能启动）。\n"
                    "这在部分 Windows/显卡驱动环境下会偶发。可选方案：\n"
                    "  1) 重新运行；\n"
                    "  2) 改用 --viewer launch（更稳，但窗口内按键回调不可用）；\n"
                    "  3) 试试设置/更换 MUJOCO_GL（如 glfw/egl/osmesa）或更新显卡驱动。"
                )
            if "e" in err:
                raise err["e"]
            h = box.get("handle")
            if h is None:
                raise RuntimeError("viewer=passive 启动失败：未返回 handle")
            return h

        def _on_key(key: int) -> None:
            nonlocal replay_requested
            if replay_codes and int(key) in replay_codes:
                replay_requested = True

        try:
            _handle = _launch_passive_with_timeout()
        except Exception as e:
            print(f"[mujoco_play_trajectory] viewer=passive failed: {e}")
            raise

        with _handle as viewer:
            t0_wall = time.perf_counter()
            while viewer.is_running():
                now_video = t0_video
                if args.replay_controller and controller_trigger_codes:
                    with key_lock:
                        down = any(int(code) in controller_keys for code in controller_trigger_codes)
                    if down:
                        replay_requested = True

                if replay_requested:
                    replay_requested = False
                    finished = False
                    idx = start_idx
                    t0_wall = time.perf_counter()
                    drive_pose = True

                if drive_pose:
                    if bool(args.apply_once):
                        _apply_pose(data, t0_video)
                        finished = True
                        drive_pose = False
                    else:
                        now_wall = time.perf_counter()
                        now_video = t0_video + (now_wall - t0_wall) * speed
                        _apply_pose(data, now_video)
                        if finished and bool(args.ui_editable_after_finish):
                            drive_pose = False
                else:
                    _apply_freeze_base_only(data)
                mujoco.mj_forward(model, data)
                mujoco.mj_step(model, data)
                viewer.sync()
                time.sleep(min(float(model.opt.timestep) / speed, 0.01))

            if not args.exit_on_finish and finished and (not bool(args.ui_editable_after_finish)) and (not bool(args.apply_once)):
                print(
                    "[mujoco_play_trajectory] playback finished; holding last pose (close window to exit)"
                )
                while viewer.is_running():
                    data.qpos[:] = last_qpos
                    _apply_freeze_base_only(data)
                    mujoco.mj_forward(model, data)
                    mujoco.mj_step(model, data)
                    viewer.sync()
                    time.sleep(min(float(model.opt.timestep), 0.01))
    else:
        if replay_codes:
            print("[mujoco_play_trajectory] note: --replay-key only works with --viewer passive/--viewer glfw")
        if bool(args.apply_once):
            print("[mujoco_play_trajectory] apply-once enabled: pose will be editable in the MuJoCo UI")
        # In viewer=launch, the viewer drives stepping. We use a control callback to
        # update qpos each step for kinematic playback.
        old_cb = mujoco.get_mjcb_control()
        cb_failed = False
        t0_sim = float(data.time)
        prev_ctrl_down = False

        def _control_cb(m: mujoco.MjModel, d: mujoco.MjData) -> None:  # noqa: ARG001
            nonlocal cb_failed
            nonlocal t0_sim, idx, finished, prev_ctrl_down, replay_requested
            nonlocal drive_pose
            nonlocal last_sim_time, stalled_sim_steps
            if cb_failed:
                return
            try:
                # In viewer=launch, even when the UI is paused, the control callback may
                # still run while `d.time` no longer advances. If we keep writing qpos,
                # any manual edits in the right-side Joint UI will instantly snap back.
                cur_sim_time = float(d.time)
                if last_sim_time is None:
                    last_sim_time = cur_sim_time
                    stalled_sim_steps = 0
                else:
                    if abs(cur_sim_time - last_sim_time) < 1e-12:
                        stalled_sim_steps += 1
                    else:
                        stalled_sim_steps = 0
                        last_sim_time = cur_sim_time

                # If time is stalled, treat as paused: allow UI edits by not overwriting qpos.
                if stalled_sim_steps >= 1:
                    _apply_freeze_base_only(d)
                    return
                # Poll controller-triggered replay.
                if args.replay_controller and controller_trigger_codes:
                    with key_lock:
                        down = any(int(code) in controller_keys for code in controller_trigger_codes)
                    if down and (not prev_ctrl_down):
                        replay_requested = True
                    prev_ctrl_down = bool(down)

                if replay_requested:
                    replay_requested = False
                    finished = False
                    idx = start_idx
                    t0_sim = float(d.time)
                    drive_pose = True

                if (not drive_pose) and bool(args.ui_editable_after_finish):
                    _apply_freeze_base_only(d)
                    return

                if bool(args.apply_once) and drive_pose:
                    _apply_pose(d, t0_video)
                    finished = True
                    drive_pose = False
                    _apply_freeze_base_only(d)
                    return

                now_video = t0_video + (float(d.time) - t0_sim) * speed
                _apply_pose(d, now_video)

                if finished and bool(args.ui_editable_after_finish):
                    drive_pose = False
            except Exception:
                cb_failed = True
                msg = traceback.format_exc()
                try:
                    err_log.write_text(msg, encoding="utf-8")
                except Exception:
                    pass
                print("[mujoco_play_trajectory] ERROR inside control callback; see mujoco_play_trajectory_error.txt")

        mujoco.set_mjcb_control(_control_cb)
        try:
            if not args.exit_on_finish:
                print("[mujoco_play_trajectory] close the window to exit")
            try:
                mj_viewer.launch(model, data)
            except KeyboardInterrupt:
                print("[mujoco_play_trajectory] interrupted while closing viewer")
        finally:
            mujoco.set_mjcb_control(old_cb)
            try:
                if _client is not None:
                    _client.stop()
            except Exception:
                pass

    print("[mujoco_play_trajectory] done")

    try:
        if _client is not None:
            _client.stop()
    except Exception:
        pass


if __name__ == "__main__":
    main()
