@echo off
cd /d %~dp0

set H1_DIR=%~dp0mujoco_menagerie\unitree_h1
set MODEL=scene.xml
set TRAJ=%~dp0naoqi-pose-retargeting\converted_outputs\unitree_h1_upper_body_trajectory.jsonl

set PY_EXE=F:\anaconda\envs\pepper_env\python.exe
if not exist "%PY_EXE%" (
  echo [LLM-pepper] pepper_env python not found: %PY_EXE%
  echo [LLM-pepper] Fallback to `python` on PATH
  set PY_EXE=python
)

set MUJOCO_GL=glfw

pushd "%H1_DIR%"
echo [LLM-pepper] Launching Unitree H1 MuJoCo (trajectory playback)...
echo   cwd: %CD%
echo   model: %MODEL%
echo   traj: %TRAJ%
echo   note: Close the MuJoCo window to exit.
echo   note: For native UI joint tweaking (right panel), add: --ui-editable-after-finish  or  --apply-once
"%PY_EXE%" ..\..\tools\mujoco_play_trajectory.py --model "%MODEL%" --jsonl "%TRAJ%" --keyframe home --freeze-base --stop-at 5
popd

pause
