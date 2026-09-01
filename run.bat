@echo off
REM ============================================================
REM  SmartCool - launch backend (ESP32 / live mode)
REM  Put this file in the project root (next to app\ and
REM  requirements.txt) and double-click it.
REM ============================================================
cd /d "%~dp0"

REM --- config: must match your Wokwi ESP32 ---
set MQTT_HOST=broker.hivemq.com
set MQTT_PORT=1883
set ROOM_ID=room-101
set DB_PATH=smartcool.db

echo ============================================================
echo  SmartCool backend starting...
echo  Dashboard:  http://localhost:8000
echo  Broker:     %MQTT_HOST%   Room: %ROOM_ID%
echo  Make sure your Wokwi ESP32 is running (same room + broker).
echo  The database (smartcool.db) is created in THIS folder.
echo ============================================================
echo.

REM open the dashboard in the browser a few seconds after start
start "" /min cmd /c "timeout /t 4 >nul & start http://localhost:8000"

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo Backend stopped. Press any key to close.
pause >nul
