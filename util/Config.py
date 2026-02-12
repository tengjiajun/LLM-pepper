import threading
import sys
import os
import time
python_version = sys.version_info[0]
# SERVER_IP = "zhangjinhong.top"
# SERVER_IP = "192.168.43.185"

# Allow runtime override via environment variables (no code changes needed elsewhere).
#SERVER_IP = os.getenv("SERVER_IP", "172.20.10.7")
SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5556"))
PEPPER_IP = os.getenv("PEPPER_IP", "127.0.0.1")
