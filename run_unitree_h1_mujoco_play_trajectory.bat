@echo off
cd /d %~dp0

set H1_DIR=%~dp0mujoco_menagerie\unitree_h1
set MODEL=scene.xml
set TRAJ=%~dp0naoqi-pose-retargeting\converted_outputs\unitree_h1_upper_body_trajectory.jsonl

set PY_EXE=F:\anaconda\envs\pepper_env\python.exe
if exist "%PY_EXE%" goto PY_OK
echo [LLM-pepper] pepper_env python not found: %PY_EXE%
echo [LLM-pepper] Fallback to `python` on PATH
set PY_EXE=python
:PY_OK

set MUJOCO_GL=glfw
set PYTHONFAULTHANDLER=1

if not exist "%~dp0logs" mkdir "%~dp0logs"
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fff"') do set TS=%%i
set LOG_ERR=%~dp0logs\mujoco_play_trajectory_%TS%_%RANDOM%_stderr.txt

rem Set to 1 to try viewer=passive first (native MuJoCo UI + in-window replay hotkey).
rem On some Windows/driver setups passive may hang; we'll auto-fallback to viewer=launch.
set TRY_PASSIVE=0

pushd "%H1_DIR%"
echo [LLM-pepper] Launching Unitree H1 MuJoCo (play JSONL trajectory)...
echo   cwd: %CD%
echo   model: %MODEL%
echo   jsonl: %TRAJ%
echo [LLM-pepper] stderr log: %LOG_ERR%
echo [LLM-pepper] NOTE: Use ESC to close the MuJoCo window. Avoid Ctrl+C in this console (it will interrupt Python).
echo [LLM-pepper] NOTE: Default uses viewer=launch (stable native UI). Replay via controller (F3 then '1').
echo [LLM-pepper] NOTE: If you want in-window replay hotkey, set TRY_PASSIVE=1 in this .bat, then press 'R' in the MuJoCo window to replay.
echo [LLM-pepper] NOTE [fallback replay]: start run_server.bat + run_controller.bat; in controller toggle F3 (单手) then press key '1' to replay.
echo [LLM-pepper] NOTE [UI edit]: If you want to tweak joints in the native MuJoCo UI (right panel) without being overridden,
echo   add one of these flags to the python command: --ui-editable-after-finish  (plays then becomes editable)
echo   or: --apply-once (apply first pose once then editable; good for single-frame JSONL)

set ERR=0

if "%TRY_PASSIVE%"=="1" goto DO_PASSIVE
goto DO_LAUNCH

:DO_PASSIVE
echo [LLM-pepper] CMD [try passive]: "%PY_EXE%" -X faulthandler ..\..\tools\mujoco_play_trajectory.py --model "%MODEL%" --jsonl "%TRAJ%" --keyframe home --freeze-base --viewer passive --replay-key r --passive-timeout 8 --replay-controller --replay-controller-key 1
"%PY_EXE%" -X faulthandler ..\..\tools\mujoco_play_trajectory.py --model "%MODEL%" --jsonl "%TRAJ%" --keyframe home --freeze-base --viewer passive --replay-key r --passive-timeout 8 --replay-controller --replay-controller-key 1 2> "%LOG_ERR%"
set ERR=%ERRORLEVEL%
if "%ERR%"=="0" goto AFTER_RUN
echo [LLM-pepper] ERRORLEVEL=%ERR%
echo [LLM-pepper] ---- stderr begin ----
type "%LOG_ERR%"
echo [LLM-pepper] ---- stderr end ----
echo [LLM-pepper] Falling back to viewer=launch (native UI). Replay via controller (F3 then '1').
goto DO_LAUNCH

:DO_LAUNCH
echo [LLM-pepper] CMD [launch]: "%PY_EXE%" -X faulthandler ..\..\tools\mujoco_play_trajectory.py --model "%MODEL%" --jsonl "%TRAJ%" --keyframe home --freeze-base --viewer launch --replay-controller --replay-controller-key 1 --replay-key r
"%PY_EXE%" -X faulthandler ..\..\tools\mujoco_play_trajectory.py --model "%MODEL%" --jsonl "%TRAJ%" --keyframe home --freeze-base --viewer launch --replay-controller --replay-controller-key 1 --replay-key r 2> "%LOG_ERR%"
set ERR=%ERRORLEVEL%
goto AFTER_RUN

:AFTER_RUN
if "%ERR%"=="0" goto DONE_RUN
echo [LLM-pepper] ERRORLEVEL=%ERR%
echo [LLM-pepper] ---- stderr begin ----
type "%LOG_ERR%"
echo [LLM-pepper] ---- stderr end ----

:DONE_RUN
popd

pause

exit /b %ERR%
