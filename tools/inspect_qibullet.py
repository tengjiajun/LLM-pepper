from __future__ import annotations

import sys


def main() -> int:
    print("python:", sys.executable)

    from qibullet import SimulationManager

    sim = SimulationManager()
    client_id = sim.launchSimulation(gui=False)
    pepper = sim.spawnPepper(client_id, spawn_ground_plane=True)

    keywords = ("move", "vel", "base", "toward", "position")
    names = [
        n
        for n in dir(pepper)
        if not n.startswith("__") and any(k in n.lower() for k in keywords)
    ]

    print("Pepper type:", type(pepper))
    print("Movement-ish attrs:")
    for n in sorted(names):
        attr = getattr(pepper, n)
        print(" -", n, "(callable)" if callable(attr) else "")

    smoke_calls = [
        ("moveToward", (0.2, 0.0, 0.0), {}),
        ("move", (0.2, 0.0, 0.0), {}),
        ("setBaseVelocity", (0.2, 0.0, 0.0), {}),
        ("setVelocity", (0.2, 0.0, 0.0), {}),
        ("moveTo", (0.1, 0.0, 0.0), {"_async": True}),
    ]

    print("\nSmoke tests:")
    for name, args, kwargs in smoke_calls:
        fn = getattr(pepper, name, None)
        if not callable(fn):
            print(f"{name}: NOT PRESENT")
            continue
        try:
            out = fn(*args, **kwargs)
            print(f"{name}: OK -> {out}")
        except TypeError as e:
            print(f"{name}: TypeError -> {e}")
        except Exception as e:
            print(f"{name}: Exception -> {e}")

    sim.stopSimulation(client_id)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
