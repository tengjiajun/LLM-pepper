# Social Motion Framework

This folder scaffolds the three-layer system described for Pepper: a motion layer with parameterized representation, an authoring layer for DIY social motions, and a social policy layer that selects and tunes motions in context. The code here is intentionally light so you can extend each module while keeping the interfaces clear.

## Goals
- Teach Mode: capture human upper-body motion, retarget to Pepper, encode into a compact parameter space, let users edit parameters, preview, and save into the library.
- Social Mode: perceive ongoing interaction (trajectory + dialog context), estimate intent/affect, and drive Pepper with library motions modulated by interpretable controls instead of raw mirroring.
- Keep the parameterized representation as the shared “language” across capture, DIY, and policy.

## Layout
- `config.py` — paths and Pepper joint configuration.
- `types.py` — shared dataclasses for trajectories, parameters, library items, and policy outputs.
- `motion_layer.py` — encoder/decoder for the parameterized representation plus retargeting stubs.
- `authoring_layer.py` — DIY flow: sessions, previews, and the social motion library store.
- `policy_layer.py` — trajectory feature extractor and a pluggable social policy head.
- `pipelines.py` — orchestrates Teach Mode and Social Mode using the above components.
- `integration_adapter.py` — hooks you can wire to `pose_analysis_server.py` endpoints (e.g., `/open_external_video`, `/analyze_pose`) or other capture stacks.
- `data/` — placeholder for persisted libraries (git-kept empty).

## Data flow
1) Teach Mode (Innovation 1 + 2):
   - Capture: camera -> pose estimator -> Pepper joint trajectory.
   - Encode: `MotionEncoder` compresses to keyframes + parameters (amplitude, tempo, symmetry, energy).
   - DIY: user edits parameters, previews via Pepper or simulator.
   - Save: `MotionLibrary` stores `{semantic label, parameterized representation, constraints, metadata}`.
2) Social Mode (Innovation 3):
   - Perception: trajectory + conversation context -> `TrajectoryFeatureExtractor`.
   - Policy: `SocialPolicy` outputs intent/affect/imitation_gain/expressiveness/respond_mode + motion choice.
   - Realization: `MotionDecoder` applies parameter overrides -> Pepper trajectory; optional speech from LLM/TTS.

## How to extend
- Wire capture: implement `PoseServerAdapter.open_external_video()` to consume `/open_external_video` or call `PoseAnalysisServer` directly.
- Retargeting: complete `PepperRetargeting.from_human_pose()` using `PoseEstimator` outputs you already have.
- Representation learning: swap the placeholder encoder/decoder with your learned model; keep the interfaces stable.
- DIY UI: bind `TeachSession.preview()` to your frontend sliders; save via `MotionLibrary.save()`.
- Policy: replace the heuristic `SocialPolicy` with your trajectory-aware + LLM reasoning stack; keep the output contract in `PolicyOutput`.

## Suggested next steps
- Connect live capture: plug `PoseServerAdapter` into the existing Flask server endpoints.
- Implement the true motion encoder/decoder (Innovation 1) and align parameter ranges with your UI.
- Build a minimal DIY front-end to drive `TeachSession` (Innovation 2).
- Train or prompt the social policy head with real trajectories + dialog context (Innovation 3).
