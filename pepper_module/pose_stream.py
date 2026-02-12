import json
import threading
import time
from datetime import datetime
from pathlib import Path


class PoseStreamExecutor:
    def __init__(self, motion, interval_sec=0.02, speed=0.1):
        self.motion = motion
        self.interval_sec = interval_sec
        self.speed = speed
        self.pose = None
        self.running = True
        self.lock = threading.Lock()
        threading.Thread(target=self.run, daemon=True).start()

    def update_pose(self, pose):
        with self.lock:
            self.pose = pose

    def run(self):
        while self.running:
            pose_snapshot = None
            with self.lock:
                pose_snapshot = self.pose
            if pose_snapshot:
                try:
                    joint_names = pose_snapshot.get("joint_names", [])
                    angles = pose_snapshot.get("angles", [])
                    if pose_snapshot.get("angles") is not None:
                        self.motion.setAngles(joint_names, angles, self.speed)
                    time.sleep(self.interval_sec)
                except Exception as e:
                    print("pose_stream error: " + str(e))
            else:
                time.sleep(0.1)

    def stop(self):
        self.running = False


class PoseStreamModule:
    def __init__(self, app, interval_sec=0.02, speed=0.1):
        self.motion = app.session.service("ALMotion")
        self.executor = PoseStreamExecutor(
            self.motion, interval_sec=interval_sec, speed=speed
        )
        self.record = False
        self.stream_active = False
        self.first_pose_received = False
        self.record_dir = Path(__file__).resolve().parent / "pose_records"
        self.record_dir.mkdir(exist_ok=True)
        self.record_file = None
        self.record_path = None

    def _open_record_file(self):
        if self.record_file is not None:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.record_path = self.record_dir / f"pose_record_{timestamp}.jsonl"
        self.record_file = open(self.record_path, "a", encoding="utf-8")

    def _close_record_file(self):
        if self.record_file is None:
            return
        try:
            self.record_file.close()
        finally:
            self.record_file = None
            self.record_path = None

    def _write_record(self, payload):
        if not self.record or self.record_file is None:
            return
        data = {
            "t": time.time(),
            "joint_names": payload.get("joint_names", []),
            "angles": payload.get("angles", []),
        }
        self.record_file.write(json.dumps(data, ensure_ascii=False) + "\n")
        self.record_file.flush()

    def handle(self, data):
        try:
            if isinstance(data, (bytes, bytearray)):
                payload = json.loads(data.decode())
            elif isinstance(data, str):
                payload = json.loads(data)
            elif isinstance(data, dict):
                payload = data
            else:
                return

            if not isinstance(payload, dict):
                return

            if payload.get("function") == "pose_stream_control":
                self.stream_active = bool(payload.get("stream_active", False))
                self.record = bool(payload.get("record", False))
                self.first_pose_received = False
                if not self.record:
                    self._close_record_file()
                if not self.stream_active:
                    self.executor.update_pose(None)
                return

            if payload.get("function") == "open_external_video" or "joint_names" in payload:
                if not self.stream_active:
                    return
                if not self.first_pose_received:
                    self.record = True
                    self.first_pose_received = True
                    self._open_record_file()
                if self.record:
                    self._write_record(payload)
                self.executor.update_pose(payload)
        except Exception as e:
            print("pose_stream handle error: " + str(e))

    def stop(self):
        self.executor.stop()
        self._close_record_file()
