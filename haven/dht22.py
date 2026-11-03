"""Optional Raspberry Pi DHT22 bridge; the UI reads its atomic JSON output."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Read a DHT22 on a Raspberry Pi")
    parser.add_argument("--pin", type=int, default=4, help="BCM GPIO number (default: 4)")
    parser.add_argument("--output", type=Path, default=Path.home() / ".haven" / "climate.json")
    args = parser.parse_args()
    try:
        import board
        import adafruit_dht
    except ImportError:
        parser.exit(1, "Install the optional sensor dependencies first; see haven/README.md.\n")
    pin = getattr(board, f"D{args.pin}", None)
    if pin is None:
        parser.error("GPIO pin is not supported on this board")
    sensor = adafruit_dht.DHT22(pin, use_pulseio=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            try:
                temperature, humidity = sensor.temperature, sensor.humidity
                if temperature is not None and humidity is not None:
                    payload = {"temperature_c": temperature, "humidity_percent": humidity,
                               "timestamp": datetime.now(timezone.utc).isoformat()}
                    temporary = args.output.with_suffix(".tmp")
                    temporary.write_text(json.dumps(payload, allow_nan=False))
                    temporary.replace(args.output)
            except (RuntimeError, ValueError) as error:
                # DHT sensors occasionally miss reads. The UI detects stale data.
                print(f"Read failed; retrying: {error}", flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.exit()
        args.output.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
