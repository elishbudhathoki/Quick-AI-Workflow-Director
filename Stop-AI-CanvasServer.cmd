@echo off
setlocal
set "PORT=4173"

echo Stopping AI Canvas server on port %PORT%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$connections = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue; if ($connections) { $connections | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force; Write-Host ('Stopped process ' + $_) } } else { Write-Host 'No AI Canvas server is listening on port %PORT%.' }"
echo.
pause
