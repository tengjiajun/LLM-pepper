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
echo [LLM-pepper] Launching Unitree H1 MuJoCo (UI torque control)...
echo   note: right-panel sliders control ACTUATOR TORQUE (not joint angle)
echo   tip : run `tools\mujoco_sim_view.py --model scene.xml --list-actuators` in this folder to see full names
echo   cwd: %CD%
echo   model: %MODEL%
"%PY_EXE%" ..\..\tools\mujoco_sim_view.py --model "%MODEL%" --keyframe home --freeze-base --viewer launch
popd

pause
