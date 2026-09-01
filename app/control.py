"""Holds AC control state and turns raw sensor telemetry into the full
telemetry object the dashboard expects.

The backend owns AC control (acOn / acMode / setpoint); the sensor owns the
environment (temperature, humidity, etc.). resolve() merges the two, runs the
decision logic in auto mode, and honours the user in manual mode.
"""
from dataclasses import dataclass

from .config import CONFIG
from . import logic


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class ControlState:
    ac_on: bool = True
    ac_mode: str = "auto"           # auto | manual
    setpoint: float = CONFIG.setpoint_default

    def apply_command(self, cmd: str) -> None:
        """Manual override — setting manual mode is what gives it priority."""
        if cmd == "ac_on":
            self.ac_mode, self.ac_on = "manual", True
        elif cmd == "ac_off":
            self.ac_mode, self.ac_on = "manual", False
        elif cmd == "cool_up":
            self.ac_mode, self.ac_on = "manual", True
            self.setpoint = _clamp(self.setpoint - 0.5, 18, 28)
        elif cmd == "cool_down":
            self.ac_mode = "manual"
            self.setpoint = _clamp(self.setpoint + 0.5, 18, 28)
        elif cmd == "auto":
            self.ac_mode = "auto"

    def resolve(self, env: dict):
        """Merge control state onto environment telemetry and decide AC.

        Returns (full_telemetry_dict, Comfort).
        """
        merged = {
            **env,
            "acMode": self.ac_mode,
            "setpoint": self.setpoint,
            "acOn": self.ac_on,
        }

        comfort = logic.classify(merged)

        # Auto mode drives the AC from comfort; manual holds the user's choice.
        if self.ac_mode == "auto" and not merged.get("warning"):
            self.ac_on = logic.decide_ac(comfort.state, self.ac_on)

        merged["acOn"] = self.ac_on
        merged["pmv"] = logic.pmv(merged.get("roomTemp", 24.0))
        return merged, comfort

    def ac_state(self) -> dict:
        """Payload published to the sensor/AC so it can respond."""
        return {"acOn": self.ac_on, "setpoint": self.setpoint, "acMode": self.ac_mode}
