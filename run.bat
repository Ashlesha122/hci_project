@echo off
cd /d "%~dp0"
echo ========================================================
echo   STARTING MOODPULSE WEB APPLICATION
echo   Opening: http://localhost:5000
echo ========================================================
start "" "http://localhost:5000"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe app.py
) else (
    python app.py
)
pause
