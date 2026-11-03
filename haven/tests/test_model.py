import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from haven.model import Store, read_climate, set_live_sensor_reader
from sensor.dht22_reader import read_sensor_once


class HavenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "state.json"

    def test_completion_and_undo_survive_restart_without_activity_logging(self):
        store = Store(self.path)
        store.mark_taken(True)
        self.assertTrue(Store(self.path).taken())
        self.assertEqual(Store(self.path).state["events"], [])
        store.mark_taken(False)
        self.assertFalse(Store(self.path).taken())

    def test_logging_is_opt_in_and_snooze_survives_restart(self):
        store = Store(self.path)
        store.log("private check-in")
        self.assertEqual(store.state["events"], [])
        store.state["logging"] = True
        store.snooze()
        restored = Store(self.path)
        self.assertTrue(restored.reminder_status().startswith("Snoozed until"))
        self.assertEqual(len(restored.state["events"]), 1)
        store.mark_taken(True)
        self.assertEqual(store.state["snoozed"], {})

    def test_reminder_resets_on_new_day(self):
        store = Store(self.path)
        store.mark_taken(True)
        tomorrow = datetime.now() + timedelta(days=1)
        with patch.object(Store, "reminder_key", return_value=Store.reminder_key(tomorrow)):
            self.assertFalse(store.taken())

    def test_corrupt_settings_recover_without_overwriting_original(self):
        self.path.write_text("{broken")
        store = Store(self.path)
        self.assertFalse(store.state["logging"])
        self.assertTrue(store.notice)
        self.assertEqual(self.path.read_text(), "{broken")

    def sensor(self, age=0, **overrides):
        data = {"temperature_c": 23.1, "humidity_percent": 45,
                "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()}
        data.update(overrides)
        self.path.write_text(json.dumps(data))
        return read_climate(self.path)

    def test_sensor_fresh_reading_and_stale_failure(self):
        self.assertEqual(self.sensor()["source"], "Local sensor")
        self.assertFalse(self.sensor(age=121)["available"])
        self.assertFalse(self.sensor(age=-60)["available"])

    def test_sensor_invalid_or_missing_never_returns_demo(self):
        self.assertFalse(read_climate(self.path)["available"])
        for value in (float("nan"), float("inf"), "22", True, None, 999):
            with self.subTest(value=value):
                self.assertFalse(self.sensor(temperature_c=value)["available"])
        self.assertFalse(self.sensor(humidity_percent=101)["available"])
        self.assertFalse(self.sensor(timestamp="invalid")["available"])

    def test_live_sensor_reader_integration(self):
        class MockReader:
            def get_reading(self):
                return {
                    "temperature": 25.3,
                    "humidity": 52.8,
                    "source": "Live sensor",
                    "available": True,
                    "timestamp": 1234567890.0,
                }

        set_live_sensor_reader(MockReader())
        try:
            reading = read_climate()
            self.assertEqual(reading["source"], "Live sensor")
            self.assertTrue(reading["available"])
            self.assertAlmostEqual(reading["temperature"], 25.3)
            self.assertAlmostEqual(reading["humidity"], 52.8)
        finally:
            set_live_sensor_reader(None)

    def test_live_sensor_reader_waiting_or_unavailable(self):
        class WaitingReader:
            def get_reading(self):
                return {
                    "temperature": None,
                    "humidity": None,
                    "source": "Waiting for sensor reading...",
                    "available": False,
                    "timestamp": None,
                }

        set_live_sensor_reader(WaitingReader())
        try:
            reading = read_climate()
            self.assertFalse(reading["available"])
            self.assertEqual(reading["source"], "Waiting for sensor reading...")
            self.assertIsNone(reading["temperature"])
        finally:
            set_live_sensor_reader(None)

    def test_read_sensor_once_handles_glitches(self):
        class GlitchySensor:
            @property
            def temperature(self):
                raise RuntimeError("Checksum error")

            @property
            def humidity(self):
                return 50.0

        t, h = read_sensor_once(GlitchySensor())
        self.assertIsNone(t)
        self.assertIsNone(h)

        class WorkingSensor:
            @property
            def temperature(self):
                return 24.5

            @property
            def humidity(self):
                return 48.2

        t, h = read_sensor_once(WorkingSensor())
        self.assertEqual(t, 24.5)
        self.assertEqual(h, 48.2)


if __name__ == "__main__":
    unittest.main()
