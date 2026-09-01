# SmartCool Backend (FastAPI + MQTT)

The "brain" of the Smart Room Cooling system. Subscribes to sensor telemetry
over MQTT, runs the R1–R8 decision logic, drives the AC, logs to SQLite, and
streams live telemetry to the dashboard over WebSocket — and serves the
dashboard itself.

## Run with Docker (recommended — universal)

Runs identically on any machine with Docker. Brings up three services:
Mosquitto (your own private broker), the backend, and the virtual sensor.

```bash
docker compose up --build
```

Open **http://localhost:8000**. That's it — broker, backend, sensor, and
dashboard are all running. Stop with `Ctrl-C`; `docker compose down` removes the
containers (the SQLite log persists in the `smartcool-data` volume).

Change the sensor scenario without touching code:

```bash
SCENARIO=toowarm docker compose up      # or edit SCENARIO in docker-compose.yml
```

Bringing a Wokwi ESP32 into the loop later: Wokwi runs in the cloud and can't
reach your laptop's broker, so point everything at a public broker instead —
set `MQTT_HOST=broker.hivemq.com` on the `backend` (and drop the `sensor`
service) and use the same broker in the ESP32 firmware.

## Run without Docker

```bash
pip install -r requirements.txt        # add --break-system-packages on Arch
```

You need an MQTT broker. Two options:

- **Zero setup:** leave `MQTT_HOST=broker.hivemq.com` (public broker).
- **Recommended (private/reliable):** `sudo pacman -S mosquitto`, run `mosquitto`,
  then set `MQTT_HOST=localhost` in `.env`.

Then run two processes:

```bash
# terminal 1 — backend (serves dashboard on http://localhost:8000)
uvicorn app.main:app --reload

# terminal 2 — virtual sensor (stand-in for the ESP32)
python sim/virtual_sensor.py
```

Open **http://localhost:8000** — the dashboard switches to live data
automatically (it detects it's being served rather than opened from disk).
Toggle the manual override buttons and watch the room respond.

## How it flows

```
 virtual_sensor.py ──telemetry──▶  MQTT  ──▶  FastAPI backend ──▶ SQLite
   (owns room state)              broker        (R1–R8 logic,        │
        ▲                                        AC decision)        ▼
        └────────────── AC state ◀── MQTT ◀──────┘            WebSocket /ws
                                                                     │
                                                                     ▼
                                                              dashboard (live)
```

- **Sensor owns the environment** (temp, humidity, body temp, occupancy) and
  reacts to AC state with a closed-loop thermal model.
- **Backend owns control** (acOn / acMode / setpoint), classifies comfort, and
  decides the AC action in auto mode; manual override takes priority.

## Swapping in the real ESP32

The ESP32 firmware just publishes the same telemetry JSON to
`smartcool/<room>/telemetry` and subscribes to `smartcool/<room>/ac`. When it's
running, stop `virtual_sensor.py` — nothing else changes.

## Scenario testing (report E1–E10)

```bash
python sim/virtual_sensor.py --scenario toowarm   # E3
python sim/virtual_sensor.py --scenario empty     # E5
python sim/virtual_sensor.py --scenario faulty    # E6 invalid reading
python sim/virtual_sensor.py --scenario offline   # E7 wifi lost
python sim/virtual_sensor.py --scenario abnormal  # E10 abnormal body temp
```

The pure logic is also tested offline (no broker needed):

```bash
python tests/test_logic.py
```

## Inspect the logged data

```bash
sqlite3 smartcool.db "SELECT ts, room_temp, comfort, ac_on FROM telemetry ORDER BY id DESC LIMIT 10;"
```

## Files

```
app/
├── main.py        FastAPI app: MQTT pipeline, /ws, /health, static dashboard
├── config.py      env config + MQTT topic names
├── logic.py       R1–R8 classify + AC decision + PMV  (pure, tested)
├── control.py     AC control state + telemetry enrichment
├── mqtt_client.py paho bridge to the asyncio loop
├── ws_manager.py  dashboard WebSocket broadcast
└── db.py          SQLite telemetry + event logging
sim/virtual_sensor.py   ESP32 stand-in (closed-loop, scenario presets)
static/index.html       the dashboard (auto mock/live)
tests/test_logic.py     offline scenario tests
```

## Endpoints

- `GET /` — dashboard
- `GET /health` — `{ status, mqtt_connected }`
- `WS /ws` — telemetry stream out; `{ "type":"command", "cmd":"ac_on" }` in
