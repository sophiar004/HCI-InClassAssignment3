"""Hardware boundary checks using fake devices; no GPIO/camera required."""

import threading
import unittest
from unittest.mock import patch

from haven.camera import CameraPreview
from haven.sensors import LiveClimate


class FakeImage:
    def copy(self):
        return self


class FakeCamera:
    def __init__(self):
        self.captured = threading.Event()
        self.closed = threading.Event()
        self.stopped = False
        self.error = None

    def create_preview_configuration(self, **kwargs):
        self.configuration = kwargs
        return kwargs

    def configure(self, config):
        pass

    def start(self):
        pass

    def capture_image(self, name, wait):
        return object()

    def wait(self, job, timeout):
        self.captured.set()
        if self.error:
            raise self.error
        return FakeImage()

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed.set()


class HardwareTests(unittest.TestCase):
    def test_camera_is_opt_in_and_releases_on_stop(self):
        camera = FakeCamera()
        preview = CameraPreview(factory=lambda index: camera)
        self.assertFalse(preview.busy)
        self.assertEqual(preview.snapshot()[0], "Camera off")
        self.addCleanup(preview.close)
        preview.start()
        self.assertTrue(camera.captured.wait(1))
        preview.close()
        self.assertTrue(camera.stopped)
        self.assertTrue(camera.closed.is_set())
        self.assertFalse(preview.busy)
        self.assertEqual(preview.snapshot()[0], "Camera off")
        self.assertIsNone(preview.snapshot()[2])
        self.assertEqual(camera.configuration["main"]["size"], (640, 360))

    def test_camera_frame_failure_clears_preview_and_releases_hardware(self):
        camera = FakeCamera()
        camera.error = TimeoutError("Sensor disconnected")
        preview = CameraPreview(factory=lambda index: camera)
        self.addCleanup(preview.close)
        with self.assertLogs("haven.camera", level="WARNING"):
            preview.start()
            self.assertTrue(camera.closed.wait(1))
            preview._thread.join(1)
        self.assertEqual(preview.snapshot()[0], "Camera unavailable")
        self.assertIsNone(preview.snapshot()[2])
        self.assertTrue(camera.stopped)

    def test_camera_missing_driver_is_recoverable(self):
        def missing(index):
            raise ImportError("picamera2")
        preview = CameraPreview(factory=missing)
        self.addCleanup(preview.close)
        with self.assertLogs("haven.camera", level="WARNING"):
            preview.start()
            preview._thread.join(1)
        self.assertEqual(preview.snapshot()[0], "Camera unavailable")
        preview.factory = lambda index: FakeCamera()
        preview.start()
        preview.close()
        self.assertEqual(preview.snapshot()[0], "Camera off")

    def test_live_dht_publishes_values_and_releases_gpio(self):
        class Sensor:
            temperature = 24.6
            humidity = 51.0
            exited = False

            def exit(self):
                self.exited = True

        sensor = Sensor()
        reader = LiveClimate(factory=lambda pin: sensor)
        self.addCleanup(reader.close)
        readings = []
        # Run one read, observing its publication before cleanup clears it.
        def inspect(interval):
            readings.append(reader.snapshot())
            reader._stop.set()
        with patch.object(reader._stop, "wait", side_effect=inspect):
            reader._run()
        self.assertTrue(readings[0]["available"])
        self.assertEqual(readings[0]["temperature"], 24.6)
        self.assertEqual(readings[0]["humidity"], 51.0)
        self.assertEqual(readings[0]["source"], "Live DHT22")
        self.assertTrue(sensor.exited)
        self.assertFalse(reader.snapshot()["available"])

    def test_live_dht_transient_failure_clears_previous_reading_then_recovers(self):
        class Sensor:
            count = 0
            humidity = 40.0

            @property
            def temperature(self):
                self.count += 1
                if self.count == 2:
                    raise RuntimeError("Checksum error")
                return 22.0

            def exit(self):
                pass

        sensor = Sensor()
        reader = LiveClimate(factory=lambda pin: sensor)
        results = []
        def next_read(interval):
            results.append(reader.snapshot()["available"])
            if len(results) == 3:
                reader._stop.set()
        with patch.object(reader._stop, "wait", side_effect=next_read), self.assertLogs("haven.sensors", level="WARNING"):
            reader._run()
        self.assertEqual(results, [True, False, True])

    def test_live_dht_never_substitutes_demo_when_driver_missing(self):
        def missing(pin):
            raise ImportError("adafruit_dht")
        reader = LiveClimate(factory=missing)
        with self.assertLogs("haven.sensors", level="WARNING"):
            reader._run()
        reading = reader.snapshot()
        self.assertFalse(reading["available"])
        self.assertIsNone(reading["temperature"])
        self.assertIn("Install", reading["detail"])


if __name__ == "__main__":
    unittest.main()
