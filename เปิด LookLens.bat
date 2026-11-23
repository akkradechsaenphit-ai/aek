@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "http://localhost:8090/family.html"
start "" "http://localhost:8090/index.html"
py server.py
if errorlevel 1 python server.py
pause
