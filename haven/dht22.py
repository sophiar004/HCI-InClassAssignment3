"""Optional Raspberry Pi DHT22 bridge; the UI reads its atomic JSON output."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sensor.dht22_reader import create_sensor, read_sensor


def main():
    parser = argparse.ArgumentParser(description="Read a DHT22 on a Raspberry Pi")
    parser.add_argument("--pin", type=int, default=4, help="BCM GPIO number (default: 4)")
    parser.add_argument("--output", type=Path, default=Path.home() / ".haven" / "climate.json")
    args = parser.parse_args()
    try:
        # Bit-banging mode works across current Pi models and avoids PulseIn issues.
        sensor = create_sensor(f"D{args.pin}", use_pulseio=False)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    if sensor is None:
        parser.error("DHT22 hardware is unavailable; check the driver installation and wiring")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            try:
                temperature, humidity = read_sensor(sensor, retries=1)
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
