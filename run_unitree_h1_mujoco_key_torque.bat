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

echo [LLM-pepper] NOTE: This mode reads keys from server.py groups.
echo   Please start these first (in separate terminals):
echo     1) run_server.bat
echo     2) run_controller.bat
echo   Then toggle controller modes:
echo     F3=单手(肩)  F6=手腕(映射到肘)  F5=身体(映射到躯干)  F2=双手(方向键)

pushd "%H1_DIR%"
"%PY_EXE%" ..\..\tools\mujoco_sim_view.py --model "%MODEL%" --keyframe home --freeze-base --viewer launch --key-torque --key-torque-hold --hold-kp 220 --hold-kd 10
popd

pause
