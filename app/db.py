"""Thread-safe SQLite logging. Writes happen from the MQTT background thread,
so the connection is opened with check_same_thread=False and guarded by a lock.
"""
import sqlite3
import threading
import time

from .config import CONFIG

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def init() -> None:
    global _conn
    _conn = sqlite3.connect(CONFIG.db_path, check_same_thread=False)
    _conn.executescript(
        """
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
    )
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
def _rows(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def recent_telemetry(limit: int = 200):
    if _conn is None:
        return []
    with _lock:
        cur = _conn.execute(
            """SELECT ts, room_id, sensor_id, room_temp, humidity, body_temp,
                      occupancy, people, setpoint, ac_on, ac_mode, comfort,
                      pmv, warning, wifi_ok
               FROM telemetry ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        return _rows(cur)


def recent_events(limit: int = 100):
    if _conn is None:
        return []
    with _lock:
        cur = _conn.execute(
            "SELECT ts, event, status FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return _rows(cur)


def stats():
    if _conn is None:
        return {"count": 0}
    with _lock:
        r = _conn.execute(
            """SELECT COUNT(*), AVG(room_temp), MIN(room_temp), MAX(room_temp),
                      AVG(humidity), AVG(body_temp),
                      SUM(CASE WHEN ac_on=1 THEN 1 ELSE 0 END)
               FROM telemetry"""
        ).fetchone()
        total = r[0] or 0
        dist = _conn.execute(
            "SELECT comfort, COUNT(*) FROM telemetry GROUP BY comfort ORDER BY COUNT(*) DESC"
        ).fetchall()

    def rnd(v):
        return round(v, 1) if v is not None else None

    return {
        "count": total,
        "avg_temp": rnd(r[1]), "min_temp": r[2], "max_temp": r[3],
        "avg_humidity": rnd(r[4]), "avg_body": rnd(r[5]),
        "ac_on_pct": round(100 * r[6] / total, 1) if total else 0,
        "comfort_distribution": [{"comfort": c, "count": n} for c, n in dist],
    }
