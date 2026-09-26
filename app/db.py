"""Telemetry storage.

- If TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are set (e.g. on Render), data goes
  to the Turso cloud database and survives restarts.
- Otherwise (local Docker / bare-metal), it falls back to a local SQLite file at
  DB_PATH (default: smartcool.db).
Same schema and `?` placeholders either way.
"""
import os
import sqlite3
import threading
import time

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
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    if url and token:
        import turso_serverless
        _conn = turso_serverless.connect(url, auth_token=token)
        print("[db] using Turso cloud database")
    else:
        path = os.getenv("DB_PATH", "smartcool.db")
        _conn = sqlite3.connect(path, check_same_thread=False)
        print(f"[db] Turso not configured - using local SQLite at {path}")
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


def stats(days=None):
    """Aggregate telemetry. If `days` is given, only rows newer than now-days.

    `ts` is stored as an ISO-8601 UTC string, so a lexicographic >= against an
    ISO cutoff selects the correct window.
    """
    if _conn is None:
        return {"count": 0, "days": days}

    where, params = "", ()
    if days:
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        where, params = "WHERE ts >= ?", (cutoff,)

    with _lock:
        r = list(_conn.execute(
            f"""SELECT COUNT(*), AVG(room_temp), MIN(room_temp), MAX(room_temp),
                       AVG(humidity),
                       SUM(CASE WHEN ac_on=1 THEN 1 ELSE 0 END)
                FROM telemetry {where}""",
            params,
        ))[0]
        dist = list(_conn.execute(
            f"SELECT comfort, COUNT(*) FROM telemetry {where} "
            "GROUP BY comfort ORDER BY COUNT(*) DESC",
            params,
        ))

    total = r[0] or 0

    def rnd(v):
        return round(v, 1) if v is not None else None

    return {
        "days": days,
        "count": total,
        "avg_temp": rnd(r[1]), "min_temp": r[2], "max_temp": r[3],
        "avg_humidity": rnd(r[4]),
        "ac_on_pct": round(100 * (r[5] or 0) / total, 1) if total else 0,
        "comfort_distribution": [{"comfort": c, "count": n} for c, n in dist],
    }
