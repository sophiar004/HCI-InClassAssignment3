# Haven touchscreen prototype

A small, offline Python/Tkinter app based on the Haven concept in
`InClassAssignment3.pdf`. Designed for a **7-inch, 800 x 480 landscape display**
on a Raspberry Pi with Raspberry Pi OS Desktop and Python 3.9+.
It also runs as a desktop window on computers with Tkinter installed.
The existing UniFinder app is independent and unchanged by this addition.

## Start on Raspberry Pi

Copy the `haven` folder to your Pi. Open a terminal in its **parent directory**.
Use the Pi's desktop session; plain SSH without a graphical display cannot show
the window. Configure the display for landscape with at least 800 x 480 pixels.

```bash
sudo apt update
sudo apt install python3-tk fonts-dejavu-core
python3 -m haven.app --fullscreen
```

No pip packages, internet connection, account, or API key are needed for the UI.
For a normal desktop window:

```bash
python3 -m haven.app
```

Press **Escape** to leave fullscreen, **F11** to toggle it, or use
**Settings > Exit Haven**. Buttons work with touch, mouse, or keyboard Tab and
Enter/Space. Touchscreen hardware and its driver must already work in the OS.
All primary touch buttons are approximately 48 pixels high or larger. The app
uses a consistent 96 DPI Tk font scale to keep the layout stable across systems.

## What works

- Home: clock, temperature/humidity, clearly labeled demo or local sensor input.
- Reminders: one daily **example** medication reminder, confirmation, undo,
  and a ten-minute snooze. The status refreshes automatically while open.
- Check-in: three choices with immediate feedback.
- Activity: scrollable local history, up to 100 entries, only when enabled.
- Settings: activity logging toggle, clear-history confirmation, and exit.
- Help: first-run introduction, available again from Help & guide.

The example reminder is fixed at 8 AM; medication editing, audible alarms,
background reminders when the app is closed, caregiver calls, AI guidance,
translations, games, camera, microphone, and emergency detection are not
implemented. Temperature and humidity alone do not identify stove hazards or
falls. Room messages use illustrative bands, not medical safety thresholds.
This is a classroom interface prototype, not a medical monitoring service.

## Local storage and privacy

Activity logging defaults to off. Camera, microphone, and sharing are absent.
Settings, onboarding, and daily reminder completion are stored in
`~/.haven/state.json`, even with activity logging off. With logging on, reminder
actions and check-ins are added to that file. Room readings are not logged.
Turning logging off stops new entries; Clear history removes existing entries
while retaining settings and reminder completion. Files are not encrypted;
use an OS account with appropriate access controls on shared devices.

For isolated testing or a different writable location:

```bash
HAVEN_STATE_FILE=/tmp/haven-demo/state.json python3 -m haven.app
```

## Optional real DHT22 sensor

The UI runs with explicit **Demo data** until `HAVEN_SENSOR_FILE` is configured.
The optional bridge uses Adafruit's driver in a separate process so sensor
reads cannot freeze touch interaction. Follow the official
[Adafruit Raspberry Pi setup and wiring guide](https://learn.adafruit.com/dht-humidity-sensing-on-raspberry-pi-with-gdocs-logging/python-setup)
for your Pi model and sensor module, including any native GPIO dependencies.
Driver API reference: [Adafruit DHT documentation](https://docs.circuitpython.org/projects/dht/en/latest/index.html).
Use the correct module pinout and 3.3 V GPIO-compatible wiring; the bridge
defaults to **BCM GPIO 4**, not physical pin 4.

Create an environment for the optional hardware libraries:

```bash
sudo apt install python3-venv
python3 -m venv --system-site-packages .venv-haven
.venv-haven/bin/python -m pip install adafruit-blinka adafruit-circuitpython-dht
.venv-haven/bin/python -m haven.dht22 --pin 4
```

Leave that terminal running. In another terminal, start the UI from the same
parent directory:

```bash
HAVEN_SENSOR_FILE="$HOME/.haven/climate.json" python3 -m haven.app --fullscreen
```

If the sensor is missing, invalid, or more than two minutes old, the UI shows
**Sensor unavailable** instead of silently using demo readings. Actual DHT22
hardware needs verification on your Pi; it cannot be tested on a Mac.
The bridge overwrites only its latest reading and removes it on a normal exit.

You can also supply your own local sensor bridge. Atomically write JSON to the
configured path every few seconds, using a current ISO timestamp, for example:

```json
{"temperature_c": 22.4, "humidity_percent": 46, "timestamp": "2026-11-03T14:00:00-05:00"}
```

## Verify

From the parent directory:

```bash
python3 -m unittest discover -s haven/tests -v
```

To include GUI workflow and widget bounds checks in a desktop session:

```bash
HAVEN_UI_TESTS=1 python3 -m unittest discover -s haven/tests -v
```

All eight checks passed on the development Mac; actual Pi hardware and visual
appearance still need verification. The tests use temporary files.
For a manual check at 800 x 480: dismiss the
guide, visit every page, confirm and undo the reminder, snooze it, enable
logging, save a check-in, inspect Activity, restart, and clear history.
