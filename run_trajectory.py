import argparse
import importlib
from pathlib import Path

from unitree_module.trajectory_player import (
    JointCommandSink,
    TrajectoryPlayer,
    build_sink_from_executor_spec,
    load_jsonl_trajectory,
    load_name_map,
)


def _default_jsonl_path() -> str:
    """Pick a reasonable default JSONL path regardless of where this script lives."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "naoqi-pose-retargeting" / "converted_outputs" / "unitree_h1_upper_body_trajectory.jsonl",
        here.parent
        / "naoqi-pose-retargeting"
        / "converted_outputs"
        / "unitree_h1_upper_body_trajectory.jsonl",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return str(candidates[0])


def main() -> int:
    ap = argparse.ArgumentParser(description="Play a Unitree H1(sim) joint trajectory from JSONL")
    ap.add_argument(
        "--jsonl",
        type=str,
        default=_default_jsonl_path(),
        help="Path to trajectory JSONL",
    )
    ap.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    ap.add_argument("--start-at", type=float, default=0.0, help="Start at video_timestamp (sec)")
    ap.add_argument("--stop-at", type=float, default=None, help="Stop at video_timestamp (sec)")
    ap.add_argument(
        "--executor",
        type=str,
        default=None,
        help=(
            "Executor spec. Two formats are supported: "
            "(1) 'module:attr' (legacy): attr can be an object, a no-arg class, or a no-arg factory; "
            "(2) 'module' (no suffix): we will auto-pick one of create_executor/build_executor/Executor/executor."
        ),
    )
    ap.add_argument(
        "--map",
        type=str,
        default=None,
        help="Optional joint name mapping JSON file",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print frames instead of sending")

    args = ap.parse_args()

    def _build_sink_from_executor_no_suffix(module_name: str, speed: float, dry_run: bool) -> JointCommandSink:
        mod = importlib.import_module(module_name)

        # Try common conventions (ordered by preference).
        candidates = [
            ("create_executor", True),
            ("build_executor", True),
            ("Executor", True),
            ("executor", False),
        ]

        picked_name = None
        picked_obj = None
        for name, _is_factory in candidates:
            if hasattr(mod, name):
                picked_name = name
                picked_obj = getattr(mod, name)
                break

        if picked_obj is None:
            raise ValueError(
                f"Executor module '{module_name}' does not expose any of: "
                f"create_executor / build_executor / Executor / executor. "
                f"Use --executor module:attr to specify an attribute explicitly."
            )

        target = picked_obj
        if callable(target):
            try:
                target = target()
            except TypeError as e:
                raise TypeError(
                    f"Cannot instantiate executor from module '{module_name}' (picked '{picked_name}') with no args. "
                    f"Provide a no-arg factory or use --executor module:attr. Original error: {e}"
                )

        return JointCommandSink(target=target, speed=speed, dry_run=dry_run)

    jsonl_path = Path(args.jsonl)
    if not jsonl_path.exists():
        raise FileNotFoundError(
            f"Trajectory JSONL not found: {jsonl_path}. "
            f"Please pass --jsonl with the correct path."
        )

    frames = load_jsonl_trajectory(jsonl_path)
    name_map = load_name_map(args.map) if args.map else None

    if args.executor is None:
        # Safe default: print only
        sink = JointCommandSink(target=None, speed=args.speed, dry_run=True)
    else:
        spec = str(args.executor).strip()
        if not spec:
            sink = JointCommandSink(target=None, speed=args.speed, dry_run=True)
        elif ":" in spec:
            sink = build_sink_from_executor_spec(spec, speed=args.speed, dry_run=bool(args.dry_run))
        else:
            sink = _build_sink_from_executor_no_suffix(spec, speed=args.speed, dry_run=bool(args.dry_run))

    player = TrajectoryPlayer(sink)
    player.play(
        frames,
        speed=args.speed,
        start_at=args.start_at,
        stop_at=args.stop_at,
        name_map=name_map,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
