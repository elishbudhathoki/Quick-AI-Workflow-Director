@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo First run: py -3 setup.py
  pause
  exit /b 1
)
echo Starting AI Canvas. If it is already running, close its existing server window first.
"%ROOT%.venv\Scripts\python.exe" "%ROOT%start.py"
