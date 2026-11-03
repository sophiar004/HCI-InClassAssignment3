# HCI-InClassAssignment3
Haven is an ambient, smart home assistant that combines localized microclimate telemetry (DHT22 sensor data)  with adaptive AI health guidance, daily activity tracking, and localized privacy controls.

## Touchscreen UI prototype

This branch adds a local Python/Tkinter prototype for a 7-inch **800 x 480**
landscape display. It includes a room dashboard, an example medication reminder
with confirmation/snooze/undo, wellness check-ins, optional local activity
history, privacy settings, and a first-use guide.

On Raspberry Pi OS Desktop, open a terminal in this repository and run:

```bash
sudo apt update
sudo apt install python3-tk fonts-dejavu-core
python3 gui.py --fullscreen
```

For a desktop window, run `python3 gui.py`. Escape exits fullscreen; F11 toggles
it. No pip dependencies or internet connection are required for the UI.

Room values are clearly labeled demo data by default. An optional DHT22 bridge
is included. AI guidance, calls, and emergency detection are not implemented.
See [the Haven setup guide](haven/README.md) for sensor setup, local storage,
privacy controls, limitations, and verification instructions.

Run the storage and sensor tests with:

```bash
python3 -m unittest discover -s haven/tests -v
```

The two optional UI tests require a graphical desktop and `HAVEN_UI_TESTS=1`.
