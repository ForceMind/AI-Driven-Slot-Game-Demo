@echo off
echo Starting Slot Simulator Web Interface...
echo Please ensure Python environment is set up.

REM Check if venv exists and use it
if exist "%~dp0\..\.venv\Scripts\python.exe" (
    set PYTHON_CMD="%~dp0\..\.venv\Scripts\python.exe"
) else (
    set PYTHON_CMD=python
)

%PYTHON_CMD% "%~dp0\src\app.py"
pause
