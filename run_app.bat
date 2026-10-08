@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Python environment is missing. Install requirements.txt in .venv first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip show PySide6 >nul 2>&1
if errorlevel 1 (
    echo PySide6 is missing. Run .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
if not exist "logs" mkdir "logs"
start "PPT Merge" ".venv\Scripts\pythonw.exe" -m src.main %* >> "logs\launcher.log" 2>&1
endlocal
