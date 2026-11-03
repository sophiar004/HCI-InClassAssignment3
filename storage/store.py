"""Local CSV store shared by the climate sensor, the activity camera, and the UI.

Every reading is one row in a single CSV file, tagged with its `kind`
("climate" or "activity"). Only derived readings are stored -- never camera
images.
"""

import csv
import fcntl
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

FIELDS = ["timestamp", "kind", "temperature_c", "humidity_pct", "present", "motion_pct"]


class HavenStore:
    def __init__(self, path="haven_data.csv"):
        self.path = Path(path)
        self._lock_path = self.path.with_name(self.path.name + ".lock")
        self._thread_lock = threading.Lock()
        with self._locked():
            if not self.path.exists() or self.path.stat().st_size == 0:
                with self.path.open("w", newline="") as f:
                    csv.writer(f).writerow(FIELDS)

    @contextmanager
    def _locked(self):
        # The thread lock covers the sensor and camera threads in this process;
        # the file lock covers other processes (like the UI) that use this class.
        with self._thread_lock, open(self._lock_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            yield  # the file lock is released when lock_file closes

    def _append(self, row):
        with self._locked(), self.path.open("a", newline="") as f:
            csv.DictWriter(f, FIELDS).writerow(row)

    def add_climate(self, timestamp, temperature, humidity):
        self._append({
            "timestamp": timestamp,
            "kind": "climate",
            "temperature_c": f"{temperature:.1f}",
            "humidity_pct": f"{humidity:.1f}",
        })

    def add_activity(self, timestamp, present, motion_pct):
        self._append({
            "timestamp": timestamp,
            "kind": "activity",
            "present": int(present),
            "motion_pct": f"{motion_pct:.2f}",
        })

    def read_rows(self, kind=None):
        """Return rows as dicts of strings, optionally only those of one kind."""
        with self._locked(), self.path.open(newline="") as f:
            return [row for row in csv.DictReader(f) if kind is None or row["kind"] == kind]

    def purge_older_than(self, days):
        """Delete rows older than `days` days. Returns the number of rows removed."""
        # ISO timestamps sort correctly as plain strings.
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with self._locked():
            with self.path.open(newline="") as f:
                rows = list(csv.DictReader(f))
            kept = [row for row in rows if row["timestamp"] >= cutoff]
            if len(kept) < len(rows):
                # Write to a temp file and swap it in, so a crash can't leave a half-written CSV.
                tmp_path = self.path.with_name(self.path.name + ".tmp")
                with tmp_path.open("w", newline="") as f:
                    writer = csv.DictWriter(f, FIELDS)
                    writer.writeheader()
                    writer.writerows(kept)
                os.replace(tmp_path, self.path)
        return len(rows) - len(kept)
