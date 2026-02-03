from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PoseFrame:
    """Single timestamped Pepper joint state."""

    timestamp: float
    joint_angles: Dict[str, float]
    confidence: float = 1.0
    source: str = "pepper"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MotionParameters:
    """Interpretable controls for a social motion."""

    amplitude: float = 1.0
    tempo: float = 1.0
    symmetry: float = 1.0
    energy: float = 1.0


@dataclass
class MotionRepresentation:
    """Keyframes + parameters learned from demonstration."""

    keyframes: List[PoseFrame]
    parameters: MotionParameters
    label: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MotionPrimitive:
    """Stored motion in the social library."""

    id: str
    representation: MotionRepresentation
    tags: List[str] = field(default_factory=list)
    created_by: Optional[str] = None
    scene: Optional[str] = None
    created_at: Optional[float] = None


@dataclass
class TrajectoryContext:
    """Runtime perception bundle for the policy layer."""

    trajectory: List[PoseFrame]
    conversation: List[str] = field(default_factory=list)
    scene: Optional[str] = None
    personality: Optional[str] = None
    affect_hint: Optional[str] = None


@dataclass
class PolicyOutput:
    """Decision from the social policy layer."""

    intent: str
    affect: str
    imitation_gain: float
    expressiveness: float
    respond_mode: str
    selected_motion_id: Optional[str]
    parameter_overrides: Dict[str, float] = field(default_factory=dict)
    speech_text: Optional[str] = None


def pose_frame_to_dict(frame: PoseFrame) -> Dict[str, Any]:
    return {
        "timestamp": frame.timestamp,
        "joint_angles": frame.joint_angles,
        "confidence": frame.confidence,
        "source": frame.source,
        "meta": frame.meta,
    }


def pose_frame_from_dict(data: Dict[str, Any]) -> PoseFrame:
    return PoseFrame(
        timestamp=data["timestamp"],
        joint_angles=data["joint_angles"],
        confidence=data.get("confidence", 1.0),
        source=data.get("source", "pepper"),
        meta=data.get("meta", {}),
    )


def motion_to_dict(motion: MotionPrimitive) -> Dict[str, Any]:
    rep = motion.representation
    return {
        "id": motion.id,
        "representation": {
            "keyframes": [pose_frame_to_dict(kf) for kf in rep.keyframes],
            "parameters": rep.parameters.__dict__,
            "label": rep.label,
            "constraints": rep.constraints,
            "metadata": rep.metadata,
        },
        "tags": motion.tags,
        "created_by": motion.created_by,
        "scene": motion.scene,
        "created_at": motion.created_at,
    }


def motion_from_dict(data: Dict[str, Any]) -> MotionPrimitive:
    rep_data = data["representation"]
    params = MotionParameters(**rep_data["parameters"])
    rep = MotionRepresentation(
        keyframes=[pose_frame_from_dict(kf) for kf in rep_data["keyframes"]],
        parameters=params,
        label=rep_data.get("label", ""),
        constraints=rep_data.get("constraints", {}),
        metadata=rep_data.get("metadata", {}),
    )
    return MotionPrimitive(
        id=data["id"],
        representation=rep,
        tags=data.get("tags", []),
        created_by=data.get("created_by"),
        scene=data.get("scene"),
        created_at=data.get("created_at"),
    )
