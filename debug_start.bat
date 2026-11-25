@echo off
echo Debug Mode - Voice Sync
echo.

cd /d "%~dp0"

echo [1] Checking Python...
python --version
if %errorlevel% neq 0 (
    echo Python not found.
    pause
    exit
)
echo.

echo [2] Starting server in a visible debug window...
echo If port 56789 is occupied, close the owning application manually.
start "Voice Sync Server Debug" cmd /k "python server.py"

echo [3] Starting client.py...
echo If this fails, read the error message below.
timeout /t 2 /nobreak >nul
python client.py

echo.
echo ========================================
echo Program exited.
echo Cleaning up debug server...
taskkill /F /FI "WINDOWTITLE eq Voice Sync Server Debug*" >nul 2>&1
pause
