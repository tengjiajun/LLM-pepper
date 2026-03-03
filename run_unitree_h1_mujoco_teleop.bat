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
echo [LLM-pepper] Launching Unitree H1 MuJoCo teleop...
echo   server: 127.0.0.1:5556 (group=move)
echo   hint: start server.bat and controller.bat, press F1 then WASD/QE
echo   cwd: %CD%
echo   model: %MODEL%
"%PY_EXE%" ..\..\tools\mujoco_sim_view.py --model "%MODEL%" --keyframe home --hold --teleop --viewer launch
popd

pause
