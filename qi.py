"""Local qi shim to support real Pepper (NAOqi) and qiBullet simulation.

Goal: keep existing code unchanged:

    import qi
    app = qi.Application(url="tcp://IP:9559")

Switch with env var:
    PEPPER_MODE=real|sim

Simulation options:
    PEPPER_SIM_GUI=1/0
    PEPPER_SIM_GROUND=1/0
"""

from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType
from typing import Any, Optional


def _mode() -> str:
    return (os.getenv("PEPPER_MODE", "real") or "real").strip().lower()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    return value not in {"0", "false", "no", "off", ""}


def _load_real_qi() -> ModuleType:
    """Load the *real* NAOqi `qi` module if installed.

    This file is also named `qi.py`, so we temporarily remove this directory
    from sys.path to avoid importing ourselves.
    """

    this_dir = os.path.dirname(os.path.abspath(__file__))
    original_sys_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if os.path.abspath(p) != this_dir]
        spec = importlib.util.find_spec("qi")
        if spec is None or spec.loader is None:
            raise ImportError(
                "NAOqi 'qi' module not found. Install NAOqi SDK, or set PEPPER_MODE=sim."
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path = original_sys_path


class Application:
    """Drop-in replacement for qi.Application.

    - real: delegates to NAOqi qi.Application
    - sim : delegates to pepper_module.connection.connect_application(...)
    """

    def __init__(self, *args: Any, **kwargs: Any):
        mode = _mode()
        self._impl: Any

        if mode == "sim":
            from pepper_module.connection import connect_application

            gui: Optional[bool] = kwargs.pop("gui", None)
            spawn_ground_plane: Optional[bool] = kwargs.pop("spawn_ground_plane", None)
            if gui is None:
                gui = _env_flag("PEPPER_SIM_GUI", default=True)
            if spawn_ground_plane is None:
                spawn_ground_plane = _env_flag("PEPPER_SIM_GROUND", default=True)

            self._impl = connect_application(
                mode="sim",
                gui=bool(gui),
                spawn_ground_plane=bool(spawn_ground_plane),
            )
            return

        real_qi = _load_real_qi()
        self._impl = real_qi.Application(*args, **kwargs)

    def start(self):
        return self._impl.start()

    def stop(self):
        stop = getattr(self._impl, "stop", None)
        if callable(stop):
            return stop()
        return None

    @property
    def session(self):
        return self._impl.session

    def __getattr__(self, item: str):
        return getattr(self._impl, item)


class Session:
    """Optional: qi.Session shim (only if your code ever uses it)."""

    def __init__(self, *args: Any, **kwargs: Any):
        mode = _mode()
        if mode == "sim":
            raise RuntimeError(
                "qi.Session is not implemented for sim mode in this project. "
                "Use qi.Application-based flow (already used by pepper_module)."
            )
        real_qi = _load_real_qi()
        self._impl = real_qi.Session(*args, **kwargs)

    def __getattr__(self, item: str):
        return getattr(self._impl, item)
