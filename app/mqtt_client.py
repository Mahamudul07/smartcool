"""Paho MQTT wrapper that bridges the broker's background thread to the
FastAPI asyncio loop.

Paho runs its network loop in its own thread (loop_start). Incoming messages
are handed to the async telemetry handler via run_coroutine_threadsafe, which
is the safe way to cross from a plain thread into the event loop.
"""
import asyncio
import json
from typing import Awaitable, Callable

import paho.mqtt.client as mqtt

from .config import CONFIG


class MqttBridge:
    def __init__(self, loop: asyncio.AbstractEventLoop,
                 on_telemetry: Callable[[dict], Awaitable[None]]) -> None:
        self.loop = loop
        self.on_telemetry = on_telemetry
        self.connected = False
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    # lifecycle ---------------------------------------------------------------
    def start(self) -> None:
        # connect_async + loop_start never blocks and auto-reconnects, so the
        # app starts fine even if the broker is not up yet.
        self.client.connect_async(CONFIG.mqtt_host, CONFIG.mqtt_port, keepalive=30)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    # callbacks ---------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc) -> None:
        self.connected = rc == 0
        if self.connected:
            client.subscribe(CONFIG.topic_telemetry)
            print(f"[mqtt] connected, subscribed to {CONFIG.topic_telemetry}")
        else:
            print(f"[mqtt] connect failed rc={rc}")

    def _on_disconnect(self, client, userdata, rc) -> None:
        self.connected = False
        print("[mqtt] disconnected")

    def _on_message(self, client, userdata, msg) -> None:
        try:
            env = json.loads(msg.payload.decode())
        except Exception:
            return
        asyncio.run_coroutine_threadsafe(self.on_telemetry(env), self.loop)

    # publish -----------------------------------------------------------------
    def publish_ac(self, state: dict) -> None:
        self.client.publish(CONFIG.topic_ac, json.dumps(state))
