@echo off
setlocal
set "ROOT=%~dp0"
set "PORT=4173"

echo Restarting AI Canvas server on port %PORT%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$connections = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if ($connections) { $connections | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force; Write-Host ('Stopped process ' + $_) } }"

if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo.
  echo Could not find the project Python environment at .venv\Scripts\python.exe.
  pause
  exit /b 1
)

echo.
echo Starting AI Canvas at http://127.0.0.1:%PORT% ...
cd /d "%ROOT%"
"%ROOT%.venv\Scripts\python.exe" prototype\server.py --mock-ai
