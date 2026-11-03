"""Live DHT22 acquisition, kept off the Tkinter thread."""

import logging
import math
import threading
import time
from pathlib import Path

LOG = logging.getLogger(__name__)


def is_raspberry_pi():
    try:
        return "Raspberry Pi" in Path("/proc/device-tree/model").read_text()
    except OSError:
        return False


def open_dht22(pin):
    import board
    import adafruit_dht
    gpio = getattr(board, f"D{pin}", None)
    if gpio is None:
        raise ValueError(f"Unsupported BCM GPIO {pin}")
    return adafruit_dht.DHT22(gpio, use_pulseio=False)


class LiveClimate:
    def __init__(self, pin=4, factory=None, interval=5):
        self.pin = pin
        self.factory = factory or open_dht22
        self.interval = max(2, interval)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._values = None
        self._updated = None
        self._message = f"Connecting to DHT22 on GPIO {pin}."

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="haven-dht22", daemon=True)
        self._thread.start()

    def snapshot(self):
        with self._lock:
            available = self._values is not None and self._updated is not None and time.monotonic() - self._updated <= 30
            t, h = self._values if available else (None, None)
            return {"temperature": t, "humidity": h, "available": available,
                    "source": "Live DHT22" if available else "Sensor unavailable",
                    "detail": self._message}

    def close(self, timeout=3):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self):
        sensor = None
        try:
            sensor = self.factory(self.pin)
            while not self._stop.is_set():
                try:
                    t, h = sensor.temperature, sensor.humidity
                    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (t, h)):
                        raise RuntimeError("Incomplete sensor reading")
                    if not -40 <= t <= 80 or not 0 <= h <= 100:
                        raise RuntimeError("Reading outside DHT22 range")
                    with self._lock:
                        self._values = (t, h)
                        self._updated = time.monotonic()
                        self._message = "Live reading updated."
                except RuntimeError as error:
                    LOG.warning("DHT22 read failed: %s", error)
                    with self._lock:
                        self._values = None
                        self._message = "Read failed. Check wiring; retrying."
                self._stop.wait(self.interval)
        except Exception as error:
            LOG.warning("DHT22 unavailable: %s", error)
            with self._lock:
                self._values = None
                self._message = ("Install the DHT22 libraries on the Pi." if isinstance(error, ImportError)
                                 else f"Check DHT22 wiring on GPIO {self.pin}.")
        finally:
            if sensor is not None:
                try:
                    sensor.exit()
                except Exception:
                    LOG.exception("Could not release DHT22")
            with self._lock:
                self._values = None
