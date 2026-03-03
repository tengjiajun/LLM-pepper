@echo off
cd /d %~dp0

set H1_DIR=%~dp0mujoco_menagerie\unitree_h1
set MODEL=scene.xml

set PY_EXE=F:\anaconda\envs\pepper_env\python.exe
if not exist "%PY_EXE%" (
  echo [LLM-pepper] pepper_env python not found: %PY_EXE%
  echo [LLM-pepper] Fallback to `python` on PATH
  set PY_EXE=python
)

set MUJOCO_GL=glfw

pushd "%H1_DIR%"
echo [LLM-pepper] Launching Unitree H1 MuJoCo (UI target-angle control)...
echo   note: Control sliders are re-interpreted as TARGET JOINT ANGLES.
echo         default: slider min/max maps to joint min/max (--ui-angle-mode joint-range)
echo         target moves at 1.0 rad/s max    (tweak with --ui-angle-speed)
echo         for unlimited joints: +/-1.6rad around home (--ui-angle-unlimited-range)
echo   cwd: %CD%
echo   model: %MODEL%
"%PY_EXE%" ..\..\tools\mujoco_sim_view.py --model "%MODEL%" --keyframe home --freeze-base --viewer launch --ui-angle
popd

pause
