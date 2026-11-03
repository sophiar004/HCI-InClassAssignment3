"""Optional GUI checks: HAVEN_UI_TESTS=1 python3 -m unittest discover -s haven/tests."""

import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from haven.app import Haven
from haven.model import Store
from haven.camera import CameraPreview
from unittest.mock import Mock


@unittest.skipUnless(os.environ.get("HAVEN_UI_TESTS") == "1", "Requires a graphical desktop")
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "state.json")
        self.store.state["onboarded"] = True
        self.app = Haven(store=self.store)
        self.addCleanup(self.app.destroy)
        self.app.update()

    def assert_fits(self, parent):
        for widget in parent.winfo_children():
            if isinstance(widget, (tk.Label, tk.Button)) and widget.winfo_ismapped():
                self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth(),
                                        f"Clipped width: {widget.cget('text')}")
                self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight(),
                                        f"Clipped height: {widget.cget('text')}")
            self.assert_fits(widget)

    def test_every_page_fits_at_800_by_480(self):
        for page in self.app.nav_buttons:
            with self.subTest(page=page):
                self.app.show(page)
                self.app.update()
                self.assert_fits(self.app)

    def test_workflow_and_dialogs(self):
        self.app.guide()
        self.app.update()
        self.assert_fits(self.app.dialog)
        self.app.dialog.destroy()
        self.app.dialog = None
        self.app.complete(True)
        self.assertTrue(self.store.taken())
        self.app.complete(False)
        self.assertFalse(self.store.taken())
        self.app.snooze()
        self.assertTrue(self.store.reminder_status().startswith("Snoozed"))
        self.app.show("Settings")
        self.app.toggle_logging()
        self.app.record_checkin("I'm feeling well")
        self.app.update()
        self.assert_fits(self.app.dialog)
        self.assertEqual(len(self.store.state["events"]), 1)
        self.app.dialog.destroy()
        self.app.dialog = None
        self.app.show("Activity")
        self.app.update()
        self.assert_fits(self.app)

    def test_activity_stops_camera_when_navigating_away(self):
        camera = Mock(spec=CameraPreview)
        camera.snapshot.return_value = ("Camera off", "Tap Start camera to view locally.", None, 0)
        camera.busy = False
        self.app.camera = camera
        self.app.show("Activity")
        self.app.update()
        self.assertEqual(self.app.camera_button.cget("text"), "Start camera")
        camera.start.assert_not_called()
        self.app.show("Home")
        camera.stop.assert_called_once()

    def test_live_dht_values_reach_home_labels(self):
        self.app.climate = Mock()
        self.app.climate.snapshot.return_value = {"temperature": 25.3, "humidity": 52,
                                                 "available": True, "source": "Live DHT22"}
        self.app.show("Home")
        self.assertEqual(self.app.climate_labels[1].cget("text"), "25.3 °C")
        self.app.climate.snapshot.return_value = {"available": False, "source": "Sensor unavailable",
                                                 "detail": "Read failed. Check wiring; retrying."}
        self.app.update_climate()
        self.assertEqual(self.app.climate_labels[1].cget("text"), "-- °C")
        self.assert_fits(self.app)

    def test_camera_frame_renders_then_disappears_on_stop(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is optional on development desktops")
        camera = Mock(spec=CameraPreview)
        camera.busy = False
        camera.snapshot.return_value = ("Camera off", "Tap Start camera to view locally.", None, 0)
        self.app.camera = camera
        self.app.show("Activity")
        self.app.update()
        camera.busy = True
        camera.snapshot.return_value = ("Live camera", "Local preview only. Not recording.", Image.new("RGB", (640, 360)), 1)
        self.app.after_cancel(self.app.camera_job)
        self.app.refresh_camera()
        self.app.update()
        self.assertIsNotNone(self.app.camera_photo)
        self.assertEqual(self.app.camera_status.cget("text"), "Live camera")
        self.assert_fits(self.app)
        camera.busy = False
        camera.snapshot.return_value = ("Camera off", "Tap Start camera to view locally.", None, 1)
        self.app.after_cancel(self.app.camera_job)
        self.app.refresh_camera()
        self.assertIsNone(self.app.camera_photo)
        self.assertEqual(self.app.camera_image.cget("text"), "Camera off")


if __name__ == "__main__":
    unittest.main()
