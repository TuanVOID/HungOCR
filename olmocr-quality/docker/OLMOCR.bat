@echo off
cd /d "%~dp0"
echo 1. Install offline image and start
echo 2. Start
echo 3. Status
echo 4. Stop
echo 5. Logs
set /p choice=Choose:
if "%choice%"=="1" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if "%choice%"=="2" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" start
if "%choice%"=="3" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" status
if "%choice%"=="4" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" stop
if "%choice%"=="5" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" logs
pause
