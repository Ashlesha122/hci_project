# MoodPulse Simple Launcher
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  STARTING MOODPULSE WEB APPLICATION" -ForegroundColor Green
Write-Host "  Opening in browser: http://localhost:5000" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

Start-Process "http://localhost:5000"

if (Test-Path ".\venv\Scripts\python.exe") {
    & ".\venv\Scripts\python.exe" app.py
} else {
    python app.py
}
