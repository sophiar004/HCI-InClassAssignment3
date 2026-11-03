"""Run Haven's climate sensor and (opt-in) activity camera, saving readings to a CSV.

Run from the repository root:
    python haven.py                         # climate sensor only
    python haven.py --enable-camera         # also track activity with the camera
    python haven.py --enable-camera --privacy-pin 17 --led-pin 27 --quiet-hours 22-7
"""

import argparse
import threading
from datetime import datetime

import adafruit_dht
import board

from sensor.dht22_reader import MIN_READ_INTERVAL, read_sensor
from storage.store import HavenStore


def parse_quiet_hours(value):
    try:
        start, end = (int(hour) for hour in value.split("-"))
    except ValueError:
        raise argparse.ArgumentTypeError("use START-END in 24h hours, e.g. 22-7")
    if not (0 <= start < 24 and 0 <= end < 24):
        raise argparse.ArgumentTypeError("hours must be between 0 and 23")
    return start, end


def run_climate(store, sensor, interval, stop_event):
    while not stop_event.is_set():
        try:
            temperature, humidity = read_sensor(sensor)
        except RuntimeError as e:
            print(f"Climate warning: {e}")
        else:
            store.add_climate(datetime.now().isoformat(timespec="seconds"), temperature, humidity)
        stop_event.wait(interval)


def main():
    parser = argparse.ArgumentParser(description="Run Haven's sensors.")
    parser.add_argument("--csv", default="haven_data.csv", help="CSV file readings are saved to")
    parser.add_argument("--retention-days", type=int, default=30, help="delete readings older than this")

    climate = parser.add_argument_group("climate sensor")
    climate.add_argument("--dht-pin", default="D4", help="board pin name for the DHT22 DATA line")
    climate.add_argument("--pi5", action="store_true", help="use bit-banging mode (needed on Raspberry Pi 5)")
    climate.add_argument("--climate-interval", type=float, default=60.0, help="seconds between readings")

    camera = parser.add_argument_group("activity camera")
    camera.add_argument("--enable-camera", action="store_true", help="turn on activity tracking (off by default)")
    camera.add_argument("--fps", type=float, default=2.0, help="frames analysed per second")
    camera.add_argument("--activity-interval", type=float, default=30.0, help="seconds per saved activity row")
    camera.add_argument("--privacy-pin", type=int, help="GPIO number of the privacy switch")
    camera.add_argument("--led-pin", type=int, help="GPIO number of the camera-on indicator LED")
    camera.add_argument("--quiet-hours", type=parse_quiet_hours, help="hours the camera stays off, e.g. 22-7")
    args = parser.parse_args()

    store = HavenStore(args.csv)
    removed = store.purge_older_than(args.retention_days)
    if removed:
        print(f"Deleted {removed} readings older than {args.retention_days} days")

    stop_event = threading.Event()
    sensor = adafruit_dht.DHT22(getattr(board, args.dht_pin), use_pulseio=not args.pi5)
    climate_interval = max(args.climate_interval, MIN_READ_INTERVAL)
    threads = [threading.Thread(target=run_climate, args=(store, sensor, climate_interval, stop_event), daemon=True)]

    if args.enable_camera:
        # Imported here so the climate sensor still works without the camera libraries installed.
        from camera.activity_camera import ActivityMonitor

        monitor = ActivityMonitor(
            store,
            fps=args.fps,
            summary_interval=args.activity_interval,
            privacy_pin=args.privacy_pin,
            led_pin=args.led_pin,
            quiet_hours=args.quiet_hours,
        )
        threads.append(threading.Thread(target=monitor.run, args=(stop_event,), daemon=True))

    for thread in threads:
        thread.start()
    print(f"Haven running (camera {'on' if args.enable_camera else 'off'}), saving to {args.csv}. Ctrl+C to stop.")

    try:
        # Re-apply the retention limit once a day while running.
        while not stop_event.wait(24 * 60 * 60):
            store.purge_older_than(args.retention_days)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=15)
        sensor.exit()


if __name__ == "__main__":
    main()
