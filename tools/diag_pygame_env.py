from __future__ import annotations

import os
import sys
import traceback


def main() -> None:
    print("=== Python ===")
    print("executable:", sys.executable)
    print("version:", sys.version.replace("\n", " "))
    print("platform:", sys.platform)
    print("cwd:", os.getcwd())

    print("\n=== Env Vars (subset) ===")
    for key in [
        "CONDA_DEFAULT_ENV",
        "CONDA_PREFIX",
        "VIRTUAL_ENV",
        "PYTHONHOME",
        "PYTHONPATH",
        "PATH",
    ]:
        val = os.environ.get(key)
        if val is None:
            continue
        if key == "PATH":
            print("PATH (first 5):")
            parts = val.split(os.pathsep)
            for p in parts[:5]:
                print("  ", p)
        else:
            print(f"{key}: {val}")

    print("\n=== Import pygame ===")
    try:
        import pygame  # type: ignore

        print("pygame version:", pygame.version.ver)
        try:
            print("pygame base:", getattr(pygame, "__file__", ""))
        except Exception:
            pass
        print("pygame import: OK")
    except Exception as e:
        print("pygame import: FAILED")
        print("exception:", repr(e))
        traceback.print_exc()


if __name__ == "__main__":
    main()
