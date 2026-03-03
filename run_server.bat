@echo off
cd /d %~dp0
set SERVER_IP=127.0.0.1
set SERVER_PORT=5556
echo [LLM-pepper] Starting server...

set CONDA_ROOT=F:\anaconda
if exist "%CONDA_ROOT%\Scripts\activate.bat" (
	call "%CONDA_ROOT%\Scripts\activate.bat" pepper_env
)

python server.py
pause
