from pathlib import Path
from typing import Dict, Optional

from .config import DEFAULT_ANALYZE_ENDPOINT, DEFAULT_OPEN_VIDEO_ENDPOINT


class PoseServerAdapter:
    """
    Helper for calling endpoints in pose_analysis_server.py.
    If the requests package is unavailable, calls are not executed but return descriptors so you can wire them later.
    """

    def __init__(
        self,
        analyze_endpoint: str = DEFAULT_ANALYZE_ENDPOINT,
        open_video_endpoint: str = DEFAULT_OPEN_VIDEO_ENDPOINT,
    ):
        self.analyze_endpoint = analyze_endpoint
        self.open_video_endpoint = open_video_endpoint
        self._client = self._maybe_init_client()

    def open_external_video(self, payload: Optional[Dict[str, object]] = None):
        body = payload or {"source": "camera"}
        if not self._client:
            return {"endpoint": self.open_video_endpoint, "payload": body, "note": "requests not installed"}
        response = self._client.post(self.open_video_endpoint, json=body, timeout=5)
        response.raise_for_status()
        return response.json()

    def analyze_image(self, image_path: Path):
        if not self._client:
            return {"endpoint": self.analyze_endpoint, "file": str(image_path), "note": "requests not installed"}
        with open(image_path, "rb") as f:
            response = self._client.post(self.analyze_endpoint, files={"image": f}, timeout=5)
        response.raise_for_status()
        return response.json()

    def send_preview(self, trajectory_payload: Dict[str, object]):
        """Placeholder for streaming decoded Pepper trajectories."""
        if not self._client:
            return {"endpoint": "pepper-motion-channel", "payload": trajectory_payload, "note": "requests not installed"}
        # Implement transport to your robot stack here (Naoqi, websocket, etc.).
        raise NotImplementedError("Implement send_preview with your robot transport.")

    def _maybe_init_client(self):
        try:
            import requests
        except ImportError:
            return None
        return requests.Session()
