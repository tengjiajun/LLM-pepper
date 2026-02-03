from pathlib import Path

# Root directory for persisted artifacts produced by the framework.
DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_LIBRARY_PATH = DATA_DIR / "social_motion_library.json"

# Supported Pepper upper-body joints for social gestures.
PEPPER_JOINTS = (
    "LShoulderPitch",
    "RShoulderPitch",
    "LShoulderRoll",
    "RShoulderRoll",
    "LElbowYaw",
    "RElbowYaw",
    "LElbowRoll",
    "RElbowRoll",
)

# Default endpoints for the existing Flask server; update if your host/port differ.
DEFAULT_ANALYZE_ENDPOINT = "http://localhost:5000/analyze_pose"
DEFAULT_OPEN_VIDEO_ENDPOINT = "http://localhost:5000/open_external_video"
