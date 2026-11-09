@echo off
setlocal
cd /d "%~dp0"
set "BILLTRACK_PYTHON=.venv\Scripts\python.exe"
if not exist "%BILLTRACK_PYTHON%" set "BILLTRACK_PYTHON=venv\Scripts\python.exe"
if not exist "%BILLTRACK_PYTHON%" (
  echo Python environment not found. Follow docs\SETUP-WINDOWS.md first.
  exit /b 1
)
if not exist logs mkdir logs
"%BILLTRACK_PYTHON%" "%~dp0scripts\serve.py" >> logs\server.log 2>&1
exit /b %errorlevel%
