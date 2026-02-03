from typing import Dict, List, Optional

from .authoring_layer import MotionLibrary, TeachSession
from .motion_layer import MotionDecoder, MotionEncoder
from .policy_layer import SocialPolicy
from .types import MotionParameters, MotionPrimitive, PoseFrame, TrajectoryContext


def teach_mode_pipeline(
    pepper_frames: List[PoseFrame],
    label: str,
    tags: Optional[List[str]] = None,
    library: Optional[MotionLibrary] = None,
    metadata: Optional[Dict[str, str]] = None,
    constraints: Optional[Dict[str, float]] = None,
    parameters: Optional[MotionParameters] = None,
) -> MotionPrimitive:
    """Runs the Teach Mode flow end-to-end."""
    session = TeachSession(
        encoder=MotionEncoder(),
        decoder=MotionDecoder(),
        library=library or MotionLibrary(),
        preview_adapter=None,
    )
    return session.record_demo(
        pepper_frames=pepper_frames,
        label=label,
        tags=tags,
        metadata=metadata,
        constraints=constraints,
        parameters=parameters,
    )


def social_mode_step(
    context: TrajectoryContext,
    library: MotionLibrary,
    policy: Optional[SocialPolicy] = None,
    decoder: Optional[MotionDecoder] = None,
) -> Dict[str, object]:
    """Single decision + realization step for Social Mode."""
    if len(library) == 0:
        raise RuntimeError("Motion library is empty; teach motions before running Social Mode.")
    policy = policy or SocialPolicy()
    decoder = decoder or MotionDecoder()
    decision = policy.decide(context, library)
    primitive = library.get_motion(decision.selected_motion_id) if decision.selected_motion_id else None
    if not primitive:
        raise RuntimeError("Policy did not select a valid motion.")
    decoded = decoder.decode(primitive.representation, overrides=decision.parameter_overrides)
    return {"decision": decision, "decoded_trajectory": decoded, "motion": primitive}
