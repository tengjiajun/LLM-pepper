from dataclasses import replace
from typing import Dict, List, Optional

from .config import PEPPER_JOINTS
from .types import MotionParameters, MotionRepresentation, PoseFrame


class PepperRetargeting:
    """Maps human upper-body pose to Pepper joint space."""

    def __init__(self, safety_limits: Optional[Dict[str, float]] = None):
        self.safety_limits = safety_limits or {}

    def from_human_pose(self, human_angles: Dict[str, float], timestamp: float, meta: Optional[Dict[str, float]] = None) -> PoseFrame:
        """Placeholder retargeter: filter to Pepper joints and clip to limits."""
        angles = {}
        for joint in PEPPER_JOINTS:
            value = human_angles.get(joint, 0.0)
            limit = self.safety_limits.get(joint)
            if limit is not None:
                value = max(-limit, min(limit, value))
            angles[joint] = value
        return PoseFrame(timestamp=timestamp, joint_angles=angles, source="retargeted", meta=meta or {})


class MotionEncoder:
    """Compresses Pepper trajectories into keyframes + semantic parameters."""

    def __init__(self, keyframe_stride: int = 5):
        self.keyframe_stride = max(1, keyframe_stride)

    def encode(
        self,
        pepper_trajectory: List[PoseFrame],
        label: str = "",
        constraints: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, str]] = None,
        parameters: Optional[MotionParameters] = None,
    ) -> MotionRepresentation:
        if not pepper_trajectory:
            raise ValueError("Cannot encode an empty trajectory.")
        keyframes = pepper_trajectory[:: self.keyframe_stride] or [pepper_trajectory[-1]]
        params = parameters or MotionParameters()
        return MotionRepresentation(
            keyframes=keyframes,
            parameters=params,
            label=label,
            constraints=constraints or {},
            metadata=metadata or {},
        )


class MotionDecoder:
    """Expands the parameterized representation back to an executable trajectory."""

    def __init__(self, default_dt: float = 0.04):
        self.default_dt = default_dt

    def decode(
        self,
        representation: MotionRepresentation,
        overrides: Optional[Dict[str, float]] = None,
    ) -> List[PoseFrame]:
        params = self._merge_parameters(representation.parameters, overrides)
        decoded: List[PoseFrame] = []
        for idx, frame in enumerate(representation.keyframes):
            scaled_angles = {
                joint: angle * params.amplitude for joint, angle in frame.joint_angles.items()
            }
            timestamp = idx * self.default_dt / max(params.tempo, 1e-3)
            decoded_frame = PoseFrame(
                timestamp=timestamp,
                joint_angles=scaled_angles,
                confidence=frame.confidence,
                source=frame.source,
                meta={**frame.meta, "tempo": params.tempo, "amplitude": params.amplitude},
            )
            decoded.append(self._apply_symmetry(decoded_frame, params.symmetry))
        return decoded

    def _merge_parameters(
        self,
        base: MotionParameters,
        overrides: Optional[Dict[str, float]],
    ) -> MotionParameters:
        if not overrides:
            return base
        merged = base
        for key, value in overrides.items():
            if hasattr(merged, key):
                merged = replace(merged, **{key: value})
        return merged

    def _apply_symmetry(self, frame: PoseFrame, symmetry: float) -> PoseFrame:
        if symmetry == 1.0:
            return frame
        mirrored = dict(frame.joint_angles)
        pairs = [
            ("LShoulderPitch", "RShoulderPitch"),
            ("LShoulderRoll", "RShoulderRoll"),
            ("LElbowYaw", "RElbowYaw"),
            ("LElbowRoll", "RElbowRoll"),
        ]
        for left, right in pairs:
            l_val = frame.joint_angles.get(left)
            r_val = frame.joint_angles.get(right)
            if l_val is None or r_val is None:
                continue
            mirrored[left] = l_val * symmetry + r_val * (1 - symmetry)
            mirrored[right] = r_val * symmetry + l_val * (1 - symmetry)
        return PoseFrame(
            timestamp=frame.timestamp,
            joint_angles=mirrored,
            confidence=frame.confidence,
            source=frame.source,
            meta={**frame.meta, "symmetry": symmetry},
        )
