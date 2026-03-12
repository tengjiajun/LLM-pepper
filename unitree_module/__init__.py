import os
import time
from dataclasses import dataclass
from typing import Optional

from communication.Client import Client
from unitree_module.intent_module import UnitreeIntentModule
from unitree_module.move_module import UnitreeMoveModule
from unitree_module.sound_module import UnitreeSoundModule


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip().lower()
    return v not in {"0", "false", "no", "off", ""}


SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5556"))


@dataclass
class UnitreeExecutorContext:
    move_module: UnitreeMoveModule
    move_socket: Client
    sound_module: UnitreeSoundModule
    sound_socket: Client
    body_module: UnitreeIntentModule
    body_socket: Client
    head_module: UnitreeIntentModule
    head_socket: Client
    active1_module: UnitreeIntentModule
    active1_socket: Client
    active2_module: UnitreeIntentModule
    active2_socket: Client

    def stop(self) -> None:
        for sock in (
            self.move_socket,
            self.sound_socket,
            self.body_socket,
            self.head_socket,
            self.active1_socket,
            self.active2_socket,
        ):
            try:
                sock.stop()
            except Exception:
                pass

        try:
            self.move_module.close()
        except Exception:
            pass


_DEFAULT_CONTEXT: Optional[UnitreeExecutorContext] = None


def start_executor(server_ip: Optional[str] = None, server_port: Optional[int] = None) -> UnitreeExecutorContext:
    """Start the Unitree(sim) executor.

    Important: This function has side effects (connect sockets).
    The package no longer auto-starts on import to avoid blocking other scripts.
    """
    global _DEFAULT_CONTEXT
    if _DEFAULT_CONTEXT is not None:
        return _DEFAULT_CONTEXT

    ip = server_ip or SERVER_IP
    port = int(server_port or SERVER_PORT)

    move_module = UnitreeMoveModule()
    move_socket = Client(ip, port, "move", "unitree_receiver", move_module.handle)

    sound_module = UnitreeSoundModule()
    sound_socket = Client(ip, port, "sound", "unitree_receiver", sound_module.handle)

    # Placeholder intent modules for Pepper-compatible actions.
    body_module = UnitreeIntentModule("body")
    body_socket = Client(ip, port, "body", "unitree_receiver", body_module.handle)

    head_module = UnitreeIntentModule("head")
    head_socket = Client(ip, port, "head", "unitree_receiver", head_module.handle)

    active1_module = UnitreeIntentModule("active_1")
    active1_socket = Client(ip, port, "active_1", "unitree_receiver", active1_module.handle)

    active2_module = UnitreeIntentModule("active_2")
    active2_socket = Client(ip, port, "active_2", "unitree_receiver", active2_module.handle)

    _DEFAULT_CONTEXT = UnitreeExecutorContext(
        move_module=move_module,
        move_socket=move_socket,
        sound_module=sound_module,
        sound_socket=sound_socket,
        body_module=body_module,
        body_socket=body_socket,
        head_module=head_module,
        head_socket=head_socket,
        active1_module=active1_module,
        active1_socket=active1_socket,
        active2_module=active2_module,
        active2_socket=active2_socket,
    )
    return _DEFAULT_CONTEXT


def main() -> None:
    """CLI entry: keep executor alive until Ctrl+C."""
    ctx = start_executor()
    _keepalive = _env_flag("UNITREE_KEEPALIVE", True)
    if not _keepalive:
        return

    print("[LLM-pepper] Unitree executor started. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        ctx.stop()


if __name__ == "__main__":
    main()
