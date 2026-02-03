@echo off
echo.
echo ===============================================
echo   NEXUS HQ - THE MOTHERSHIP
echo   Starting Command Center...
echo ===============================================
echo.

cd /d "%~dp0"

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting NEXUS HQ Server on port 5050...
echo Dashboard: http://localhost:5050
echo.

python hq_server.py

pause
