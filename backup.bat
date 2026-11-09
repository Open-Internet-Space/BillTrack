@echo off
setlocal
cd /d "%~dp0"
set "BILLTRACK_PYTHON=.venv\Scripts\python.exe"
if not exist "%BILLTRACK_PYTHON%" set "BILLTRACK_PYTHON=venv\Scripts\python.exe"
if not exist "%BILLTRACK_PYTHON%" (
  echo Python environment not found. Follow docs\SETUP-WINDOWS.md first.
  exit /b 1
)
"%BILLTRACK_PYTHON%" scripts\backup.py %*
exit /b %errorlevel%
