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
import time
from datetime import datetime
from pathlib import Path

import board
import adafruit_dht

# The DHT22 can't be polled faster than once every ~2 seconds.
MIN_READ_INTERVAL = 2.0


def read_sensor(sensor, retries=5):
    """Return (temperature_c, humidity_pct), retrying on the DHT22's frequent glitches."""
    for _ in range(retries):
        try:
            temperature = sensor.temperature
            humidity = sensor.humidity
            if temperature is not None and humidity is not None:
                return temperature, humidity
        except RuntimeError:
            # Checksum errors and timeouts are normal for this sensor; just try again.
            pass
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


def main():
    parser = argparse.ArgumentParser(description="Log DHT22 temperature readings.")
    parser.add_argument("--pin", default="D4", help="board pin name for DATA (default: D4 = GPIO4)")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between readings")
    parser.add_argument("--csv", help="optional CSV file to append readings to")
    parser.add_argument("--pi5", action="store_true", help="use bit-banging mode (needed on Raspberry Pi 5)")
    args = parser.parse_args()

    pin = getattr(board, args.pin)
    sensor = adafruit_dht.DHT22(pin, use_pulseio=not args.pi5)
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
        sensor.exit()


if __name__ == "__main__":
    main()
