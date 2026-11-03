"""Turn camera frames into activity readings for Haven without keeping any images.

Each frame is compared against a learned background to measure how much of
the scene is moving. Every `summary_interval` seconds that is boiled down to
one row -- whether someone is present and the average motion -- and the
frames themselves are discarded. Nothing visual is written to disk or sent
anywhere.

"Present" means motion was seen within the last `presence_timeout` seconds,
so someone sitting perfectly still for longer than that reads as absent.

Camera: an Arducam IMX708 (the same sensor as the Raspberry Pi Camera Module 3).
Connect it with the Pi powered off -- the camera port isn't hot-pluggable --
then boot and run `rpicam-hello --list-cameras`. It should list an imx708.
If it doesn't, add these lines to /boot/firmware/config.txt and reboot:
    camera_auto_detect=0
    dtoverlay=imx708            (Pi 5 using the CAM0 port: dtoverlay=imx708,cam0)

Setup on the Pi -- install these with apt, not pip (pip's OpenCV can pull in
a numpy version that breaks Picamera2):
    sudo apt install -y python3-picamera2 python3-opencv python3-gpiozero
and create the virtual environment with --system-site-packages so it can see them.

Privacy hardware (optional):
    privacy switch: a slide switch between a GPIO pin and GND. While it's
                    closed, the camera is fully off.
    indicator LED:  GPIO pin -> 330 ohm resistor -> LED -> GND. Lit whenever
                    the camera is capturing.

Usage (test the camera on its own; prints motion and saves nothing):
    python -m camera.activity_camera
"""

import time
from datetime import datetime

import cv2

# Frames are analysed at this small size: enough to detect motion, cheap on
# the Pi, and too coarse to be much use as a picture of anyone. It's 16:9 to
# match the IMX708, so none of its field of view is cropped away.
FRAME_SIZE = (384, 216)

# Read the IMX708 in its 2x2-binned mode, which covers the whole sensor. Its
# faster 1536x864 mode is cropped and would miss the edges of the room.
SENSOR_MODE_SIZE = (2304, 1296)

# Fixed focus in dioptres (1 / distance in metres): 0.4 is about 2.5 m, typical
# for watching a room. Autofocus is off because the image changing as the
# lens hunts would register as motion.
LENS_POSITION = 0.4

# Percent of the frame that has to change to count as movement.
MOTION_THRESHOLD_PCT = 1.0

# The background model marks everything as moving until it has seen a few frames.
WARMUP_FRAMES = 10


class Camera:
    """The Arducam IMX708 on the Pi's camera port, via Picamera2."""

    def __init__(self, size=FRAME_SIZE):
        try:
            from libcamera import controls
            from picamera2 import Picamera2
        except ImportError:
            raise RuntimeError("Picamera2 isn't installed: sudo apt install -y python3-picamera2") from None

        # Model is "imx708", or "imx708_wide" / "imx708_noir" for those variants.
        found = [num for num, info in enumerate(Picamera2.global_camera_info())
                 if info["Model"].startswith("imx708")]
        if not found:
            raise RuntimeError("No IMX708 camera found -- check the ribbon cable and run "
                               "`rpicam-hello --list-cameras`")

        self._picam = Picamera2(found[0])
        # "RGB888" gives pixels in the BGR order that OpenCV expects.
        config = self._picam.create_video_configuration(
            main={"size": size, "format": "RGB888"},
            raw={"size": SENSOR_MODE_SIZE},
        )
        self._picam.configure(config)
        # Only set focus if this board has an autofocus motor.
        if "AfMode" in self._picam.camera_controls:
            self._picam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": LENS_POSITION})
        self._picam.start()

    def read(self):
        return self._picam.capture_array()

    def close(self):
        self._picam.stop()
        self._picam.close()


class MotionDetector:
    """Measures what percent of each frame differs from the learned background."""

    def __init__(self):
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=25, detectShadows=False
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._frames_seen = 0

    def motion_pct(self, frame):
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        mask = self._subtractor.apply(gray)
        # Remove single-pixel sensor noise.
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        self._frames_seen += 1
        if self._frames_seen <= WARMUP_FRAMES:
            return 0.0
        return 100.0 * cv2.countNonZero(mask) / mask.size


def in_quiet_hours(now, quiet_hours):
    """quiet_hours is (start_hour, end_hour) in 24h time, e.g. (22, 7) for 10pm-7am."""
    if quiet_hours is None:
        return False
    start, end = quiet_hours
    if start <= end:
        return start <= now.hour < end
    return now.hour >= start or now.hour < end


class ActivityMonitor:
    """Runs the camera, honouring the privacy switch and quiet hours, and saves activity summaries."""

    def __init__(self, store, fps=2.0, summary_interval=30.0, presence_timeout=300.0,
                 privacy_pin=None, led_pin=None, quiet_hours=None):
        self.store = store
        self.frame_delay = 1.0 / fps
        self.summary_interval = summary_interval
        self.presence_timeout = presence_timeout
        self.quiet_hours = quiet_hours

        self.privacy_switch = None
        self.led = None
        if privacy_pin is not None or led_pin is not None:
            from gpiozero import LED, Button
            if privacy_pin is not None:
                # Internal pull-up, so a closed switch (pin -> GND) reads as pressed.
                self.privacy_switch = Button(privacy_pin)
            if led_pin is not None:
                self.led = LED(led_pin)

        self._camera = None

    def camera_allowed(self):
        if self.privacy_switch is not None and self.privacy_switch.is_pressed:
            return False
        return not in_quiet_hours(datetime.now(), self.quiet_hours)

    def _start(self):
        self._camera = Camera()
        self._detector = MotionDetector()
        self._last_motion = None
        self._window_start = time.monotonic()
        self._window_motion = []
        if self.led is not None:
            self.led.on()

    def _stop(self):
        self._flush()
        self._camera.close()
        self._camera = None
        if self.led is not None:
            self.led.off()

    def _flush(self):
        """Save one summary row for the frames seen since the last flush."""
        if not self._window_motion:
            return
        now = time.monotonic()
        present = self._last_motion is not None and now - self._last_motion <= self.presence_timeout
        average = sum(self._window_motion) / len(self._window_motion)
        self.store.add_activity(datetime.now().isoformat(timespec="seconds"), present, average)
        self._window_motion = []
        self._window_start = now

    def run(self, stop_event):
        """Capture until `stop_event` is set. Meant to run in its own thread."""
        try:
            while not stop_event.is_set():
                if not self.camera_allowed():
                    if self._camera is not None:
                        self._stop()
                    stop_event.wait(1.0)
                    continue

                try:
                    if self._camera is None:
                        self._start()
                    pct = self._detector.motion_pct(self._camera.read())
                except RuntimeError as e:
                    print(f"Camera warning: {e}")
                    if self._camera is not None:
                        self._stop()
                    stop_event.wait(5.0)
                    continue

                if pct >= MOTION_THRESHOLD_PCT:
                    self._last_motion = time.monotonic()
                self._window_motion.append(pct)
                if time.monotonic() - self._window_start >= self.summary_interval:
                    self._flush()
                stop_event.wait(self.frame_delay)
        finally:
            if self._camera is not None:
                self._stop()


if __name__ == "__main__":
    camera = Camera()
    detector = MotionDetector()
    try:
        while True:
            pct = detector.motion_pct(camera.read())
            print(f"motion: {pct:5.2f}%  {'MOVING' if pct >= MOTION_THRESHOLD_PCT else ''}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        camera.close()
