import statistics
from typing import Dict, List, Optional

from .authoring_layer import MotionLibrary
from .types import MotionPrimitive, PolicyOutput, TrajectoryContext


class TrajectoryFeatureExtractor:
    """Extracts lightweight features from recent Pepper trajectories."""

    def extract(self, trajectory: List) -> Dict[str, float]:
        if len(trajectory) < 2:
            return {"tempo": 1.0, "amplitude": 1.0, "symmetry": 1.0, "energy": 1.0}
        durations = trajectory[-1].timestamp - trajectory[0].timestamp
        tempo = len(trajectory) / max(durations, 1e-3)
        # Rough amplitude proxy: mean absolute joint angle.
        amplitudes: List[float] = []
        symmetry_scores: List[float] = []
        for frame in trajectory:
            angles = list(frame.joint_angles.values())
            if angles:
                amplitudes.append(sum(abs(a) for a in angles) / len(angles))
            l = frame.joint_angles.get("LShoulderPitch")
            r = frame.joint_angles.get("RShoulderPitch")
            if l is not None and r is not None:
                symmetry_scores.append(1.0 - abs(l - r) / max(abs(l) + abs(r), 1e-6))
        amplitude = statistics.mean(amplitudes) if amplitudes else 1.0
        symmetry = statistics.mean(symmetry_scores) if symmetry_scores else 1.0
        energy = amplitude * tempo
        return {
            "tempo": max(0.2, min(3.0, tempo)),
            "amplitude": max(0.5, min(2.0, amplitude)),
            "symmetry": max(0.0, min(1.0, symmetry)),
            "energy": max(0.2, min(3.0, energy)),
        }


class SocialPolicy:
    """Placeholder policy head that maps features + context to motion selection."""

    def __init__(self, feature_extractor: Optional[TrajectoryFeatureExtractor] = None):
        self.feature_extractor = feature_extractor or TrajectoryFeatureExtractor()

    def decide(self, context: TrajectoryContext, library: MotionLibrary) -> PolicyOutput:
        features = self.feature_extractor.extract(context.trajectory)
        intent = self._infer_intent(context, features)
        affect = context.affect_hint or ("positive" if features["energy"] > 1.0 else "neutral")
        motion = self._choose_motion(library, intent=intent, scene=context.scene)
        overrides = {
            "amplitude": features["amplitude"],
            "tempo": features["tempo"],
            "symmetry": features["symmetry"],
            "energy": features["energy"],
        }
        return PolicyOutput(
            intent=intent,
            affect=affect,
            imitation_gain=min(1.0, features["energy"] / 2.0),
            expressiveness=features["energy"],
            respond_mode="gesture_and_speech",
            selected_motion_id=motion.id if motion else None,
            parameter_overrides=overrides,
            speech_text=self._craft_response(context, intent, affect),
        )

    def _infer_intent(self, context: TrajectoryContext, features: Dict[str, float]) -> str:
        if context.scene:
            return f"scene::{context.scene}"
        if features["energy"] > 1.5:
            return "engage"
        if features["tempo"] < 0.8:
            return "calm"
        return "neutral"

    def _choose_motion(
        self,
        library: MotionLibrary,
        intent: str,
        scene: Optional[str] = None,
    ) -> Optional[MotionPrimitive]:
        candidates = library.all()
        if scene:
            scene_matches = [m for m in candidates if scene in m.tags or m.scene == scene]
            if scene_matches:
                return scene_matches[0]
        intent_matches = [m for m in candidates if intent in m.tags or intent == m.representation.label]
        if intent_matches:
            return intent_matches[0]
        return candidates[0] if candidates else None

    def _craft_response(self, context: TrajectoryContext, intent: str, affect: str) -> str:
        last_utterance = context.conversation[-1] if context.conversation else ""
        return f"[policy] intent={intent}, affect={affect}, echo='{last_utterance}'"
