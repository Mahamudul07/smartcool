import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    mqtt_host: str = os.getenv("MQTT_HOST", "broker.hivemq.com")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
    room_id: str = os.getenv("ROOM_ID", "room-101")
    setpoint_default: float = float(os.getenv("SETPOINT_DEFAULT", "24.0"))
    db_path: str = os.getenv("DB_PATH", "smartcool.db")

    @property
    def topic_telemetry(self) -> str:
        """Sensor -> backend: raw environment readings."""
        return f"smartcool/{self.room_id}/telemetry"

    @property
    def topic_ac(self) -> str:
        """Backend -> sensor/AC: resolved AC state."""
        return f"smartcool/{self.room_id}/ac"


CONFIG = Config()
