"""Local state and sensor input. No network requests or background recording."""

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("HAVEN_STATE_FILE", Path.home() / ".haven" / "state.json"))
        self.state = {"logging": False, "onboarded": False, "taken": {}, "snoozed": {}, "events": []}
        self.notice = ""
        try:
            saved = json.loads(self.path.read_text())
            if not isinstance(saved, dict):
                raise ValueError("Invalid state")
            for key, default in self.state.items():
                if key in saved and type(saved[key]) is type(default):
                    self.state[key] = saved[key]
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self.notice = "Saved settings could not be read. Using defaults."

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2))
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def log(self, text):
        if self.state["logging"]:
            self.state["events"].insert(0, {"time": datetime.now().isoformat(timespec="seconds"), "text": text})
            self.state["events"] = self.state["events"][:100]

    @staticmethod
    def reminder_key(now=None):
        return (now or datetime.now()).date().isoformat() + ":morning"

    def taken(self):
        return self.state["taken"].get(self.reminder_key()) is True

    def mark_taken(self, value):
        key = self.reminder_key()
        self.state["taken"][key] = value
        self.state["snoozed"].pop(key, None)
        # Keep only recent daily completion flags.
        cutoff = (datetime.now() - timedelta(days=30)).date().isoformat()
        self.state["taken"] = {k: v for k, v in self.state["taken"].items() if k[:10] >= cutoff}
        self.log("Example reminder marked done" if value else "Example reminder undone")
        self.save()

    def snooze(self):
        self.state["snoozed"][self.reminder_key()] = (datetime.now() + timedelta(minutes=10)).isoformat()
        self.log("Example reminder snoozed for 10 minutes")
        self.save()

    def reminder_status(self):
        if self.taken():
            return "Done for today"
        try:
            until = datetime.fromisoformat(self.state["snoozed"].get(self.reminder_key(), ""))
            if until > datetime.now():
                return "Snoozed until " + until.strftime("%I:%M %p").lstrip("0")
        except (TypeError, ValueError):
            pass
        return "At 8:00 AM" if datetime.now().hour < 8 else "Ready to check off"


_live_reader = None


def set_live_sensor_reader(reader):
    global _live_reader
    _live_reader = reader


def get_live_sensor_reader():
    return _live_reader


def read_climate(path=None):
    """Accept a local sensor bridge file, live DHT22 sensor, or show explicitly labeled demo values.

    A failed or old real reading never falls back to a simulated healthy reading.
    """
    path = path or os.environ.get("HAVEN_SENSOR_FILE")
    if path:
        try:
            data = json.loads(Path(path).read_text())
            temperature, humidity = data["temperature_c"], data["humidity_percent"]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in (temperature, humidity)):
                raise ValueError("Invalid numbers")
            if not -40 <= temperature <= 80 or not 0 <= humidity <= 100:
                raise ValueError("Out of sensor range")
            timestamp = datetime.fromisoformat(data["timestamp"])
            age = (datetime.now(timestamp.tzinfo) - timestamp).total_seconds()
            if age > 120 or age < -10:
                raise ValueError("Stale timestamp")
            return {"temperature": temperature, "humidity": humidity, "source": "Local sensor", "available": True}
        except (OSError, ValueError, KeyError, TypeError):
            return {"temperature": None, "humidity": None, "source": "Sensor unavailable", "available": False}

    if _live_reader is not None:
        reading = _live_reader.get_reading()
        if reading.get("available"):
            return {
                "temperature": reading["temperature"],
                "humidity": reading["humidity"],
                "source": reading.get("source", "Live sensor"),
                "available": True,
            }
        source = reading.get("source", "Sensor unavailable")
        return {"temperature": None, "humidity": None, "source": source, "available": False}

    return {"temperature": 22.4, "humidity": 46.0, "source": "Demo data", "available": True}
