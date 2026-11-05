"""Read temperature and humidity from a DHT22 sensor on a Raspberry Pi.

Wiring (DHT22 -> Pi header):
    VCC  -> 3.3V   (physical pin 1)
    DATA -> GPIO4  (physical pin 7), with a 10k pull-up to 3.3V if your
                                     board doesn't already have one
    GND  -> GND    (physical pin 6)

Usage:
    python dht22_reader.py                  # print a reading every 5 seconds
    python dht22_reader.py --csv log.csv    # also append readings to a CSV
"""

import argparse
import csv
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import board
    import adafruit_dht
    HAS_HARDWARE = True
except (ImportError, NotImplementedError):
    board = None
    adafruit_dht = None
    HAS_HARDWARE = False
# The DHT22 can't be polled faster than once every ~2 seconds.
MIN_READ_INTERVAL = 2.0


def create_sensor(pin="D4", use_pulseio=False):
    """Initialize and return an adafruit_dht.DHT22 sensor, or None if hardware is unavailable."""
    if not HAS_HARDWARE:
        return None
    try:
        pin_obj = getattr(board, pin) if isinstance(pin, str) else pin
        return adafruit_dht.DHT22(pin_obj, use_pulseio=use_pulseio)
    except Exception as e:
        print(f"Sensor initialization failed on pin {pin}: {e}")
        return None


def read_sensor_once(sensor):
    """Attempt a single non-blocking read of the DHT22 sensor.

    Returns (temperature_c, humidity_pct) on success, or (None, None) on failure.
    """
    if sensor is None:
        return None, None
    try:
        temperature = sensor.temperature
        humidity = sensor.humidity
        if temperature is not None and humidity is not None:
            return temperature, humidity
    except (RuntimeError, ValueError):
        # DHT22 readings can occasionally fail (checksum or timeout error).
        pass
    except Exception as e:
        print(f"Sensor read error: {e}")
    return None, None


def read_sensor(sensor, retries=5):
    """Return (temperature_c, humidity_pct), retrying on the DHT22's frequent glitches."""
    for _ in range(retries):
        temperature, humidity = read_sensor_once(sensor)
        if temperature is not None and humidity is not None:
            return temperature, humidity
        time.sleep(MIN_READ_INTERVAL)
    raise RuntimeError(f"No valid reading from DHT22 after {retries} attempts")


def read_temperature(sensor):
    """Return just the temperature in degrees Celsius."""
    temperature, _ = read_sensor(sensor)
    return temperature


def append_csv(path, timestamp, temperature, humidity):
    path = Path(path)
    is_new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "temperature_c", "humidity_pct"])
        writer.writerow([timestamp, f"{temperature:.1f}", f"{humidity:.1f}"])


class DHT22Reader:
    """Continuous background reader for DHT22 sensor data.

    Utilizes the DHT22 polling and error-handling approach from old_sensor.py,
    running in a background thread to prevent blocking or freezing the GUI.
    """

    def __init__(self, pin="D4", interval=2.5, use_pulseio=False):
        self.pin = pin
        self.interval = max(interval, MIN_READ_INTERVAL)
        self.use_pulseio = use_pulseio
        self.sensor = create_sensor(pin=self.pin, use_pulseio=self.use_pulseio)
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.last_reading = {
            "temperature": None,
            "humidity": None,
            "source": "Waiting for sensor reading...",
            "available": False,
            "timestamp": None,
        }
        if self.sensor is not None:
            self.running = True
            self.thread = threading.Thread(target=self._poll_loop, daemon=True)
            self.thread.start()

    def _poll_loop(self):
        while self.running:
            try:
                temperature = self.sensor.temperature
                humidity = self.sensor.humidity
                if temperature is not None and humidity is not None:
                    with self.lock:
                        self.last_reading = {
                            "temperature": temperature,
                            "humidity": humidity,
                            "source": "Live sensor",
                            "available": True,
                            "timestamp": time.time(),
                        }
            except (RuntimeError, ValueError):
                # DHT22 readings can occasionally fail; retain previous reading if recent.
                with self.lock:
                    if self.last_reading["timestamp"] is None:
                        self.last_reading["source"] = "Waiting for sensor reading..."
            except Exception as e:
                print(f"DHT22 poll error: {e}")
            time.sleep(self.interval)

    def get_reading(self):
        """Return the most recent climate reading dictionary."""
        with self.lock:
            reading = dict(self.last_reading)
            if reading["timestamp"] is not None and (time.time() - reading["timestamp"] > 30):
                reading["available"] = False
                reading["source"] = "Sensor unavailable"
            return reading

    def close(self):
        """Stop background polling and release GPIO pin."""
        self.running = False
        if self.sensor is not None:
            try:
                self.sensor.exit()
            except Exception:
                pass
            self.sensor = None


def main():
    parser = argparse.ArgumentParser(description="Log DHT22 temperature readings.")
    parser.add_argument("--pin", default="D4", help="board pin name for DATA (default: D4 = GPIO4)")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between readings")
    parser.add_argument("--csv", help="optional CSV file to append readings to")
    parser.add_argument("--pi5", action="store_true", help="use bit-banging mode (needed on Raspberry Pi 5)")
    args = parser.parse_args()

    if not HAS_HARDWARE:
        print("Hardware libraries (board, adafruit_dht) are not available on this system.")
        return

    sensor = create_sensor(pin=args.pin, use_pulseio=not args.pi5)
    if sensor is None:
        print(f"Failed to initialize DHT22 on pin {args.pin}")
        return
    interval = max(args.interval, MIN_READ_INTERVAL)

    try:
        while True:
            try:
                temperature, humidity = read_sensor(sensor)
            except RuntimeError as e:
                print(f"Warning: {e}")
            else:
                timestamp = datetime.now().isoformat(timespec="seconds")
                print(f"{timestamp}  {temperature:.1f} °C  {humidity:.1f} %RH")
                if args.csv:
                    append_csv(args.csv, timestamp, temperature, humidity)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        # Release the GPIO pin so the next run can claim it.
        try:
            sensor.exit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
