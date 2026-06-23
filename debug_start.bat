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

echo [2] Cleaning up port 56789...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":56789" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo.

echo [3] Starting server in a visible debug window...
start "Voice Sync Server Debug" cmd /k "python server.py"

echo [4] Starting client.py...
echo If this fails, read the error message below.
timeout /t 2 /nobreak >nul
python client.py

echo.
echo ========================================
echo Program exited.
echo Cleaning up debug server...
taskkill /F /FI "WINDOWTITLE eq Voice Sync Server Debug*" >nul 2>&1
pause
