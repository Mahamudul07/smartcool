@echo off
REM ============================================================
REM  SmartCool - first-time setup (installs Python packages)
REM  Run this ONCE on a new machine before run.bat.
REM ============================================================
cd /d "%~dp0"

echo Checking Python...
python --version
if errorlevel 1 (
  echo.
  echo Python not found. Install Python 3.12 from python.org
  echo and tick "Add Python to PATH" during install, then re-run this.
  pause
  exit /b 1
)

echo.
echo Installing dependencies...
python -m pip install -r requirements.txt

echo.
echo Setup complete. Double-click run.bat to start the app.
pause
