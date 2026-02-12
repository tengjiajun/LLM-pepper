@echo off
cd /d %~dp0
set PEPPER_MODE=real
set PEPPER_IP=10.0.0.xx
echo [LLM-pepper] Starting Pepper (REAL) with IP=%PEPPER_IP%...
python pepper.py --mode real --ip %PEPPER_IP%
pause
