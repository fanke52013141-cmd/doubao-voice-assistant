@echo off
cd /d "%~dp0"

if exist "%~dp0start_hidden.vbs" (
    start "" wscript.exe //B //Nologo "%~dp0start_hidden.vbs"
    exit /b
)

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launcher.py"
    exit /b
)

where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw "%~dp0launcher.py"
    exit /b
)

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

start "" python "%~dp0launcher.py"
exit /b
