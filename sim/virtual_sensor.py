#!/usr/bin/env python3
"""Virtual sensor — a software stand-in for the ESP32.

Publishes environment telemetry to the broker every 2s and drives a closed-loop
thermal model: it listens for the backend's AC state and warms/cools the room
accordingly. When the real ESP32 is ready, it publishes the same JSON to the
same topic and this script is simply not run.

Usage:
    python sim/virtual_sensor.py                     # normal room
    python sim/virtual_sensor.py --scenario toowarm  # start hot
    python sim/virtual_sensor.py --scenario faulty   # invalid readings
    MQTT_HOST=localhost python sim/virtual_sensor.py  # local broker

Scenarios map to the report's experiment table (E1-E10).
"""
import argparse
import json
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
ROOM = os.getenv("ROOM_ID", "room-101")
SENSOR_ID = os.getenv("SENSOR_ID", "esp32-a")

TOPIC_TELEMETRY = f"smartcool/{ROOM}/telemetry"
TOPIC_AC = f"smartcool/{ROOM}/ac"

# ---- scenario presets (E1-E10) ---------------------------------------------
SCENARIOS = {
    "normal":   dict(room=23.0, hum=50, body=36.6, occ=True,  warn=False, wifi=True),
    "warm":     dict(room=25.5, hum=55, body=36.7, occ=True,  warn=False, wifi=True),
    "toowarm":  dict(room=28.0, hum=60, body=36.8, occ=True,  warn=False, wifi=True),
    "humid":    dict(room=24.5, hum=72, body=36.7, occ=True,  warn=False, wifi=True),
    "empty":    dict(room=28.0, hum=55, body=36.6, occ=False, warn=False, wifi=True),
    "faulty":   dict(room=27.0, hum=56, body=36.6, occ=True,  warn=True,  wifi=True),
    "offline":  dict(room=27.0, hum=56, body=36.6, occ=True,  warn=False, wifi=False),
    "abnormal": dict(room=26.0, hum=55, body=38.4, occ=True,  warn=False, wifi=True),
}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def jitter(mag):
    return (random.random() * 2 - 1) * mag


class VirtualSensor:
    def __init__(self, scenario: str):
        s = SCENARIOS.get(scenario, SCENARIOS["normal"])
        self.room = s["room"]
        self.hum = s["hum"]
        self.body = s["body"]
        self.occ = s["occ"]
        self.warn = s["warn"]
        self.wifi = s["wifi"]
        self.people = 3 if s["occ"] else 0
        self.ac_on = True          # updated from the backend's AC state
        self.frozen = self.warn    # faulty sensor => reading stops changing

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        print(f"[sensor] connected rc={rc}; publishing to {TOPIC_TELEMETRY}")
        client.subscribe(TOPIC_AC)

    def _on_message(self, client, userdata, msg):
        try:
            state = json.loads(msg.payload.decode())
            self.ac_on = bool(state.get("acOn", self.ac_on))
        except Exception:
            pass

    def step(self):
        if self.frozen:
            return  # faulty sensor: values do not update
        drift = -0.12 if self.ac_on else 0.10
        self.room = clamp(self.room + drift + jitter(0.06), 20, 32)
        self.hum = clamp(self.hum + jitter(0.6), 35, 80)
        self.body = clamp(self.body + jitter(0.05), 36.0, 38.6)

    def payload(self) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "roomId": ROOM,
            "sensorId": SENSOR_ID,
            "roomTemp": round(self.room, 2),
            "humidity": round(self.hum, 1),
            "bodyTemp": round(self.body, 2),
            "occupancy": self.occ,
            "people": self.people,
            "warning": self.warn,
            "wifiOk": self.wifi,
        }

    def run(self):
        # connect_async + loop_start tolerates the broker not being up yet
        # (important under docker-compose startup ordering) and auto-reconnects.
        self.client.connect_async(HOST, PORT, keepalive=30)
        self.client.loop_start()
        try:
            while True:
                self.step()
                self.client.publish(TOPIC_TELEMETRY, json.dumps(self.payload()))
                time.sleep(2)
        except KeyboardInterrupt:
            print("\n[sensor] stopping")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=os.getenv("SCENARIO", "normal"),
                    choices=sorted(SCENARIOS))
    args = ap.parse_args()
    print(f"[sensor] scenario={args.scenario} broker={HOST}:{PORT}")
    VirtualSensor(args.scenario).run()
