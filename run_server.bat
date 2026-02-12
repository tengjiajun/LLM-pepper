@echo off
cd /d %~dp0
set SERVER_IP=127.0.0.1
set SERVER_PORT=5556
echo [LLM-pepper] Starting server...
python server.py
pause
