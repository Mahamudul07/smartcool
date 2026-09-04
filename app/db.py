"""Turso (cloud SQLite) logging — replaces the local sqlite3 file so data
survives restarts/redeploys/sleep cycles on stateless hosts like Render free tier.

Needs two env vars: TURSO_DATABASE_URL, TURSO_AUTH_TOKEN (from the Turso dashboard).
Same table schema and `?` placeholders as before, so the rest of the app is unchanged.
"""
import os
import threading
import time

import turso_serverless

_lock = threading.Lock()
_conn = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, room_id TEXT, sensor_id TEXT,
    room_temp REAL, humidity REAL, body_temp REAL,
    occupancy INTEGER, people INTEGER,
    setpoint REAL, ac_on INTEGER, ac_mode TEXT,
    comfort TEXT, pmv REAL, warning INTEGER, wifi_ok INTEGER
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, event TEXT, status TEXT
);
"""


def init() -> None:
    global _conn
    url = os.environ["TURSO_DATABASE_URL"]
    token = os.environ["TURSO_AUTH_TOKEN"]
    _conn = turso_serverless.connect(url, auth_token=token)
    for stmt in _SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            _conn.execute(stmt)
    _conn.commit()


def log_telemetry(t: dict, comfort: str) -> None:
    if _conn is None:
        return
    with _lock:
        _conn.execute(
            """INSERT INTO telemetry
               (ts, room_id, sensor_id, room_temp, humidity, body_temp,
                occupancy, people, setpoint, ac_on, ac_mode, comfort, pmv,
                warning, wifi_ok)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                t.get("timestamp"), t.get("roomId"), t.get("sensorId"),
                t.get("roomTemp"), t.get("humidity"), t.get("bodyTemp"),
                int(bool(t.get("occupancy"))), t.get("people"),
                t.get("setpoint"), int(bool(t.get("acOn"))), t.get("acMode"),
                comfort, t.get("pmv"),
                int(bool(t.get("warning"))), int(bool(t.get("wifiOk"))),
            ),
        )
        _conn.commit()


def log_event(event: str, status: str = "ok") -> None:
    if _conn is None:
        return
    with _lock:
        _conn.execute(
            "INSERT INTO events (ts, event, status) VALUES (?,?,?)",
            (time.strftime("%H:%M:%S"), event, status),
        )
        _conn.commit()


# --- read queries for the dashboard tabs ------------------------------------
_TELEMETRY_COLS = ["ts", "room_id", "sensor_id", "room_temp", "humidity",
                    "body_temp", "occupancy", "people", "setpoint", "ac_on",
                    "ac_mode", "comfort", "pmv", "warning", "wifi_ok"]
_EVENT_COLS = ["ts", "event", "status"]


def _dicts(rows, cols):
    return [dict(zip(cols, r)) for r in rows]


def recent_telemetry(limit: int = 200):
    if _conn is None:
        return []
    with _lock:
        rows = list(_conn.execute(
            f"""SELECT {','.join(_TELEMETRY_COLS)}
                FROM telemetry ORDER BY id DESC LIMIT ?""",
            (limit,),
        ))
    return _dicts(rows, _TELEMETRY_COLS)


def recent_events(limit: int = 100):
    if _conn is None:
        return []
    with _lock:
        rows = list(_conn.execute(
            "SELECT ts, event, status FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ))
    return _dicts(rows, _EVENT_COLS)


def stats():
    if _conn is None:
        return {"count": 0}
    with _lock:
        r = list(_conn.execute(
            """SELECT COUNT(*), AVG(room_temp), MIN(room_temp), MAX(room_temp),
                      AVG(humidity), AVG(body_temp),
                      SUM(CASE WHEN ac_on=1 THEN 1 ELSE 0 END)
               FROM telemetry"""
        ))[0]
        dist = list(_conn.execute(
            "SELECT comfort, COUNT(*) FROM telemetry GROUP BY comfort ORDER BY COUNT(*) DESC"
        ))

    total = r[0] or 0

    def rnd(v):
        return round(v, 1) if v is not None else None

    return {
        "count": total,
        "avg_temp": rnd(r[1]), "min_temp": r[2], "max_temp": r[3],
        "avg_humidity": rnd(r[4]), "avg_body": rnd(r[5]),
        "ac_on_pct": round(100 * r[6] / total, 1) if total else 0,
        "comfort_distribution": [{"comfort": c, "count": n} for c, n in dist],
    }
