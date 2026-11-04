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
sudo apt install python3-tk fonts-dejavu-core python3-venv python3-lgpio python3-picamera2 python3-pil.imagetk
python3 -m venv --system-site-packages .venv-haven
.venv-haven/bin/python -m pip install -r haven/requirements-pi.txt
.venv-haven/bin/python -m haven.app --fullscreen --live --sensor-pin 4
```

GPIO 4 means **BCM GPIO 4 (physical header pin 7)**. Change `--sensor-pin` if
the DHT22 data wire uses another GPIO. Stop any separate DHT22 reader before
starting the UI so only one process uses that sensor. On a Raspberry Pi, direct
DHT22 reading is selected automatically unless `--demo` or an external sensor
file is selected. No account, API key, or internet connection is used at runtime.

For a normal desktop window without Pi hardware or extra dependencies:

```bash
python3 -m haven.app --demo
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
- Activity: on-demand live Arducam preview beside scrollable local history.
  History retains up to 100 entries, only when enabled.
- Settings: activity logging toggle, clear-history confirmation, and exit.
- Help: six-step first-use tutorial, available again from Help & guide.

The example reminder is fixed at 8 AM; medication editing, audible alarms,
background reminders when the app is closed, caregiver calls, AI guidance,
translations, games, microphone, and emergency detection are not
implemented. Temperature and humidity alone do not identify stove hazards or
falls. Room messages use illustrative bands, not medical safety thresholds.
This is a classroom interface prototype, not a medical monitoring service.

## Local storage and privacy

Activity logging defaults to off. The camera starts only when you press
**Activity > Start camera**. It stops when you press Stop camera, leave Activity,
or close Haven. Frames are held only in memory; they are never saved, recorded,
sent over the network, or included in activity history. Microphone and sharing
are absent.
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

## Live DHT22 sensor

The Pi UI reads temperature and humidity about every five seconds in a worker
thread and refreshes Home every second. Failed reads show **Sensor unavailable**
and are retried automatically; values over 30 seconds old are also unavailable.
Real sensor failures never fall back to demo readings. If a driver cannot be
loaded, fix the installation and restart Haven. Follow the official
[Adafruit Raspberry Pi setup and wiring guide](https://learn.adafruit.com/dht-humidity-sensing-on-raspberry-pi-with-gdocs-logging/python-setup)
for your Pi model and sensor module, including any native GPIO dependencies.
Driver API reference: [Adafruit DHT documentation](https://docs.circuitpython.org/projects/dht/en/latest/index.html).
Use the correct module pinout and 3.3 V GPIO-compatible wiring; the bridge
defaults to **BCM GPIO 4**, not physical pin 4.

Use the installation commands above, then launch with your data GPIO:

```bash
.venv-haven/bin/python -m haven.app --live --sensor-pin 4 --fullscreen
```

### Optional separate sensor bridge

The existing JSON-file interface is still supported. Run only this bridge,
instead of the UI's direct reader, if you prefer separate processes:

```bash
.venv-haven/bin/python -m haven.dht22 --pin 4
```

In another terminal:

```bash
HAVEN_SENSOR_FILE="$HOME/.haven/climate.json" .venv-haven/bin/python -m haven.app --fullscreen
```

If the sensor is missing, invalid, or more than two minutes old, the UI shows
**Sensor unavailable** instead of silently using demo readings. Actual DHT22
hardware needs verification on your Pi; it cannot be tested on a Mac.
The bridge overwrites only its latest reading and removes it on a normal exit.
The two-minute expiry applies to this file interface; direct reads expire after
30 seconds and are immediately marked unavailable after a failed read.

You can also supply your own local sensor bridge. Atomically write JSON to the
configured path every few seconds, using a current ISO timestamp, for example:

```json
{"temperature_c": 22.4, "humidity_percent": 46, "timestamp": "2026-11-03T14:00:00-05:00"}
```

## Live Arducam preview in Activity

The camera must already be enabled and detected by Raspberry Pi OS. Follow the
[Arducam IMX708 installation guide](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/12MP-IMX708/)
for your module, cable, and CAM/DISP port. Check it before starting Haven:

```bash
rpicam-hello --list-cameras
```

Haven uses **Picamera2**, installed through apt above, and Pillow's Tk bindings.
The environment must be created with `--system-site-packages` so it can access
the OS camera packages. Reference:
[official Picamera2 documentation](https://github.com/raspberrypi/picamera2).

Open **Activity**, then press **Start camera**. A 640 x 360 stream at a target
10 fps is scaled into the camera area. Continuous autofocus is enabled when
the module reports support. Camera capture runs off the UI thread. There is no
recording. Startup errors, unavailable cameras, and frame timeouts display a
clear unavailable state. Stop the preview before running another camera app.

If more than one camera is detected, select its index (not the CAM/DISP port
number) from the camera list:

```bash
.venv-haven/bin/python -m haven.app --fullscreen --live --camera-index 1
```

You can test the real camera while using demo climate values with `--demo`.
On computers without Picamera2, all other pages still work and starting the
camera displays setup guidance rather than crashing.

## Verify

From the parent directory:

```bash
python3 -m unittest discover -s haven/tests -v
```

To include GUI workflow and widget bounds checks in a desktop session:

```bash
HAVEN_UI_TESTS=1 python3 -m unittest discover -s haven/tests -v
```

All 17 checks passed on the development Mac, including fake hardware failure
and cleanup, frame rendering, live temperature labels, and widget bounds at
800 x 480. Actual Pi hardware still needs verification. Tests use temporary files.
For a manual check at 800 x 480: dismiss the
guide, visit every page, confirm and undo the reminder, snooze it, enable
logging, save a check-in, inspect Activity, restart, and clear history.
On the Pi, also start/stop the Arducam preview, leave Activity while live, and
confirm the camera is released. Confirm Home readings change with the DHT22
and show an unavailable state when sensor reads fail.
