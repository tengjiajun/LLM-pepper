@echo off
cd /d %~dp0
set PEPPER_MODE=sim
set SERVER_IP=127.0.0.1
set SERVER_PORT=5556
rem Optional: set PEPPER_SIM_GUI=0
rem Optional: set PEPPER_SIM_GROUND=1
echo [LLM-pepper] Starting Pepper (SIM)...

set CONDA_ROOT=F:\anaconda
if exist "%CONDA_ROOT%\Scripts\activate.bat" (
	call "%CONDA_ROOT%\Scripts\activate.bat" pepper_env
)

python pepper.py --mode sim
pause
