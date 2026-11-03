"""Optional GUI checks: HAVEN_UI_TESTS=1 python3 -m unittest discover -s haven/tests."""

import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from haven.app import Haven, TUTORIAL_STEPS
from haven.model import Store


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
        for step in range(len(TUTORIAL_STEPS)):
            with self.subTest(tutorial_step=step + 1):
                self.app.tutorial(step)
                self.app.update()
                self.assert_fits(self.app.dialog)
        self.app.dialog.destroy()
        self.app.dialog = None
        self.app.finish_guide()
        self.assertTrue(Store(self.store.path).state["onboarded"])
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


if __name__ == "__main__":
    unittest.main()
