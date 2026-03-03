import os
import time

from communication.Client import Client
from unitree_module.move_module import UnitreeMoveModule
from unitree_module.sound_module import UnitreeSoundModule
from unitree_module.intent_module import UnitreeIntentModule


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip().lower()
    return v not in {"0", "false", "no", "off", ""}


SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5556"))

move_module = UnitreeMoveModule()
move_socket = Client(SERVER_IP, SERVER_PORT, "move", "unitree_receiver", move_module.handle)

sound_module = UnitreeSoundModule()
sound_socket = Client(SERVER_IP, SERVER_PORT, "sound", "unitree_receiver", sound_module.handle)

# Placeholder intent modules for Pepper-compatible actions.
body_module = UnitreeIntentModule("body")
body_socket = Client(SERVER_IP, SERVER_PORT, "body", "unitree_receiver", body_module.handle)

head_module = UnitreeIntentModule("head")
head_socket = Client(SERVER_IP, SERVER_PORT, "head", "unitree_receiver", head_module.handle)

active1_module = UnitreeIntentModule("active_1")
active1_socket = Client(SERVER_IP, SERVER_PORT, "active_1", "unitree_receiver", active1_module.handle)

active2_module = UnitreeIntentModule("active_2")
active2_socket = Client(SERVER_IP, SERVER_PORT, "active_2", "unitree_receiver", active2_module.handle)

_keepalive = _env_flag("UNITREE_KEEPALIVE", True)
if _keepalive:
    print("[LLM-pepper] Unitree executor started. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

try:
    move_socket.stop()
except Exception:
    pass
try:
    sound_socket.stop()
except Exception:
    pass
try:
    body_socket.stop()
except Exception:
    pass
try:
    head_socket.stop()
except Exception:
    pass
try:
    active1_socket.stop()
except Exception:
    pass
try:
    active2_socket.stop()
except Exception:
    pass
try:
    move_module.close()
except Exception:
    pass
