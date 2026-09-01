"""Rule-based comfort classification (report rules R1-R8).

Pure functions of a telemetry dict — no I/O, no state — so they can be unit
tested directly against the report's scenario table (E1-E10). This is the same
logic the dashboard runs in JS; keeping one authoritative copy here means the
backend's decisions and the dashboard's display always agree.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Comfort:
    state: str
    tone: str      # ok | warn | hot | info
    title: str     # recommendation headline
    desc: str      # recommendation detail


def classify(t: dict) -> Comfort:
    # R1 — invalid / unsafe reading: pause automation
    if t.get("warning"):
        return Comfort("Invalid Reading", "hot",
                       "Automatic cooling paused",
                       "Sensor reading invalid — awaiting valid data")

    # R2 — manual override takes priority
    if t.get("acMode") == "manual":
        return Comfort("Manual Override", "info",
                       "Manual mode active",
                       "Following user command; automatic logic paused")

    # R3 — unoccupied: energy-saving standby
    if not t.get("occupancy"):
        return Comfort("Standby", "info",
                       "Energy-saving mode",
                       "Room unoccupied — cooling held")

    # R7 — abnormal human thermal indicator
    if t.get("bodyTemp", 0.0) >= 38.0:
        return Comfort("Alert", "hot",
                       "Abnormal body temperature",
                       "Recommend manual check; do not rely on auto AC")

    room = t.get("roomTemp", 0.0)
    hum = t.get("humidity", 0.0)

    # R6 — too warm
    if room >= 27.5 or (room >= 26 and hum > 65):
        return Comfort("Too Warm", "hot",
                       "AC adjustment required",
                       "Increase cooling within safe temperature limits")

    # R5 — warm
    if room >= 25.0 or hum > 62:
        return Comfort("Warm", "warn",
                       "Cooling recommended",
                       "Temperature rising above the comfort range")

    # R4 — comfortable
    return Comfort("Comfortable", "ok",
                   "Cooling not required",
                   "Current conditions are within the comfort range")


def decide_ac(comfort_state: str, current_ac_on: bool) -> bool:
    """Auto-mode actuation. Returns the desired AC on/off state.

    For non-actionable states (Invalid Reading, Alert, Manual Override) the
    current state is held — automation is paused rather than toggled unsafely.
    """
    if comfort_state in ("Too Warm", "Warm"):
        return True
    if comfort_state in ("Comfortable", "Standby"):
        return False
    return current_ac_on


def pmv(room_temp: float) -> float:
    """Simplified predicted-mean-vote proxy for the comfort card."""
    return round((room_temp - 24.0) / 3.5, 1)
