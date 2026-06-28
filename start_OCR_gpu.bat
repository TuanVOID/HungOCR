@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv_vl15\Scripts\python.exe"
set "APP_URL=http://127.0.0.1:5000"
set "HEALTH_URL=http://127.0.0.1:5000/health"

if not exist "%PYTHON_EXE%" (
  echo [HungOCR] GPU Python environment was not found:
  echo %PYTHON_EXE%
  echo.
  echo Keep .venv_vl15 in this project folder, then run this file again.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $r = Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }"

if "%ERRORLEVEL%"=="0" (
  echo [HungOCR] Service is already running. Opening UI...
  start "" "%APP_URL%"
  exit /b 0
)

echo [HungOCR] Starting GPU full service...
echo [HungOCR] UI will open automatically when backend is ready.
echo [HungOCR] Close this window or press Ctrl+C to stop the service.
echo.

"%PYTHON_EXE%" "%~dp0app.py" full

echo.
echo [HungOCR] Service stopped.
pause
