# HCI-InClassAssignment3
Haven is an ambient, smart home assistant that combines localized microclimate telemetry (DHT22 sensor data)  with adaptive AI health guidance, daily activity tracking, and localized privacy controls.

## Touchscreen UI prototype

This branch adds a local Python/Tkinter prototype for a 7-inch **800 x 480**
landscape display. It includes a room dashboard, an example medication reminder
with confirmation/snooze/undo, wellness check-ins, a live Arducam preview in
Activity, optional local activity history, privacy settings, and a first-use guide.

On Raspberry Pi OS Desktop, open a terminal in this repository and run:

```bash
sudo apt update
sudo apt install python3-tk fonts-dejavu-core python3-venv python3-lgpio python3-picamera2 python3-pil.imagetk
python3 -m venv --system-site-packages .venv-haven
.venv-haven/bin/python -m pip install -r haven/requirements-pi.txt
.venv-haven/bin/python gui.py --fullscreen --live --sensor-pin 4
```

For a desktop window or preview without sensor hardware, run `python3 gui.py --demo`
or `python3 gui.py`. Escape exits fullscreen; F11 toggles it.

When running on a Raspberry Pi, the app reads a DHT22 directly on BCM GPIO 4 by
default (`--sensor-pin 4`) and displays live temperature and humidity. If the
sensor is not connected or when running on a desktop, it gracefully falls back to
labeled demo values.
Open **Activity > Start camera** to start the local Arducam preview. Camera
capture stops when leaving Activity; frames are not recorded or shared.
AI guidance, calls, and emergency detection are not implemented.
See [the Haven setup guide](haven/README.md) for sensor setup, local storage,
privacy controls, limitations, and verification instructions.

Run the storage and sensor tests with:

```bash
python3 -m unittest discover -s haven/tests -v
```

The five optional UI tests require a graphical desktop and `HAVEN_UI_TESTS=1`.
