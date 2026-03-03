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

rem Ensure a windowed OpenGL backend on Windows
set MUJOCO_GL=glfw

pushd "%H1_DIR%"
echo [LLM-pepper] Launching Unitree H1 MuJoCo scene...
echo   cwd: %CD%
echo   model: %MODEL%
rem Tip: add --hold-add-ui if you want UI sliders to add torque on top of PD hold.
"%PY_EXE%" ..\..\tools\mujoco_sim_view.py --model "%MODEL%" --keyframe home --hold --freeze-base --viewer launch
popd

pause
