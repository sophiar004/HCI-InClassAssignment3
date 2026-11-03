"""On-demand Picamera2 preview. Only the worker touches camera hardware."""

import logging
import threading

LOG = logging.getLogger(__name__)


def open_camera(index):
    from picamera2 import Picamera2
    return Picamera2(camera_num=index)


class CameraPreview:
    def __init__(self, index=0, factory=None):
        self.index = index
        self.factory = factory or open_camera
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._image = None
        self._sequence = 0
        self._status = "Camera off"
        self._detail = "Tap Start camera to view locally."

    @property
    def busy(self):
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self):
        with self._lock:
            return self._status, self._detail, self._image, self._sequence

    def start(self):
        if self.busy:
            return
        self._stop.clear()
        with self._lock:
            self._image = None
            self._status = "Starting camera"
            self._detail = "Connecting to the Arducam..."
        self._thread = threading.Thread(target=self._run, name="haven-camera", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        with self._lock:
            self._image = None
            self._status = "Stopping camera" if self.busy else "Camera off"
            self._detail = "Releasing camera..." if self.busy else "Tap Start camera to view locally."

    def close(self, timeout=3):
        self.stop()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self):
        camera = None
        started = False
        try:
            camera = self.factory(self.index)
            config = camera.create_preview_configuration(
                main={"size": (640, 360), "format": "RGB888"},
                controls={"FrameRate": 10}, buffer_count=4)
            camera.configure(config)
            if "AfMode" in getattr(camera, "camera_controls", {}):
                camera.set_controls({"AfMode": 2})  # Continuous autofocus, when supported.
            if self._stop.is_set():
                return
            camera.start()
            started = True
            while not self._stop.is_set():
                # A timeout prevents an unplugged camera from leaving an old frame marked live.
                job = camera.capture_image("main", wait=False)
                image = camera.wait(job, timeout=2).copy()
                with self._lock:
                    if self._stop.is_set():
                        break
                    self._image = image
                    self._sequence += 1
                    self._status = "Live camera"
                    self._detail = "Local preview only. Not recording."
                self._stop.wait(0.1)
        except Exception as error:
            LOG.warning("Camera preview failed: %s", error)
            with self._lock:
                self._image = None
                self._status = "Camera unavailable"
                self._detail = ("Install Picamera2 and Pillow on the Pi." if isinstance(error, ImportError)
                                else "Check camera setup; close other camera apps.")
        finally:
            if camera is not None:
                try:
                    if started:
                        camera.stop()
                except Exception:
                    LOG.exception("Could not stop camera")
                finally:
                    try:
                        camera.close()
                    except Exception:
                        LOG.exception("Could not release camera")
            with self._lock:
                self._image = None
                if self._stop.is_set():
                    self._status = "Camera off"
                    self._detail = "Tap Start camera to view locally."
