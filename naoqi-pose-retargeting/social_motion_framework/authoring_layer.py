import json
import time
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import DEFAULT_LIBRARY_PATH
from .motion_layer import MotionDecoder, MotionEncoder
from .types import (
    MotionParameters,
    MotionPrimitive,
    MotionRepresentation,
    PoseFrame,
    motion_from_dict,
    motion_to_dict,
)


class MotionLibrary:
    """In-memory social motion library with simple JSON persistence."""

    def __init__(self, storage_path: Path = DEFAULT_LIBRARY_PATH):
        self.storage_path = Path(storage_path)
        self._items: Dict[str, MotionPrimitive] = {}

    def add_motion(self, motion: MotionPrimitive) -> None:
        self._items[motion.id] = motion

    def get_motion(self, motion_id: str) -> Optional[MotionPrimitive]:
        return self._items.get(motion_id)

    def list_by_tag(self, tag: str) -> List[MotionPrimitive]:
        return [m for m in self._items.values() if tag in m.tags]

    def all(self) -> List[MotionPrimitive]:
        return list(self._items.values())

    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path or self.storage_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = [motion_to_dict(motion) for motion in self._items.values()]
        with target.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
        return target

    @classmethod
    def load(cls, path: Path = DEFAULT_LIBRARY_PATH) -> "MotionLibrary":
        lib = cls(path)
        target = Path(path)
        if not target.exists():
            return lib
        with target.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            lib.add_motion(motion_from_dict(entry))
        return lib

    def __len__(self) -> int:
        return len(self._items)


class PreviewAdapter:
    """Stub for sending decoded trajectories to Pepper or a simulator."""

    def send(self, trajectory: Iterable[PoseFrame]) -> None:
        # Implement with your transport of choice (Naoqi, REST, WebSocket, etc.).
        raise NotImplementedError("PreviewAdapter.send must be implemented for your setup.")


class TeachSession:
    """Teach + DIY workflow for creating social motions."""

    def __init__(
        self,
        encoder: Optional[MotionEncoder] = None,
        decoder: Optional[MotionDecoder] = None,
        library: Optional[MotionLibrary] = None,
        preview_adapter: Optional[PreviewAdapter] = None,
    ):
        self.encoder = encoder or MotionEncoder()
        self.decoder = decoder or MotionDecoder()
        self.library = library or MotionLibrary()
        self.preview_adapter = preview_adapter

    def record_demo(
        self,
        pepper_frames: List[PoseFrame],
        label: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
        constraints: Optional[Dict[str, float]] = None,
        parameters: Optional[MotionParameters] = None,
    ) -> MotionPrimitive:
        representation: MotionRepresentation = self.encoder.encode(
            pepper_frames,
            label=label,
            constraints=constraints,
            metadata=metadata,
            parameters=parameters,
        )
        primitive = MotionPrimitive(
            id=str(uuid.uuid4())[:8],
            representation=representation,
            tags=tags or [],
            created_by=metadata.get("created_by") if metadata else None,
            scene=metadata.get("scene") if metadata else None,
            created_at=time.time(),
        )
        self.library.add_motion(primitive)
        return primitive

    def preview(self, primitive: MotionPrimitive, overrides: Optional[Dict[str, float]] = None) -> List[PoseFrame]:
        decoded = self.decoder.decode(primitive.representation, overrides=overrides)
        if self.preview_adapter:
            self.preview_adapter.send(decoded)
        return decoded
