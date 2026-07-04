"""Cross-platform persistence for PortScope snapshots."""

import json
import os
import sqlite3
import sys
import threading
from pathlib import Path


def _default_data_dir(app_name="portscope"):
    """Return an OS-appropriate per-user data directory."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / app_name


class SnapshotStore:
    """SQLite-backed storage for captured snapshots."""

    def __init__(self, db_path, max_rows=2000):
        self.db_path = Path(db_path)
        self.max_rows = max_rows
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def from_data_dir(cls, data_dir=None, db_name="history.sqlite3", max_rows=2000):
        root = Path(data_dir).expanduser() if data_dir else _default_data_dir()
        return cls(root / db_name, max_rows=max_rows)

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_recorded_at ON snapshots(recorded_at)"
            )

    def save(self, snapshot_data):
        payload = json.dumps(snapshot_data, separators=(",", ":"))
        ts = int(snapshot_data.get("epoch") or 0)
        if ts <= 0:
            ts = int(__import__("time").time())

        with self._lock:
            with self._connect() as con:
                con.execute(
                    "INSERT INTO snapshots(recorded_at, payload) VALUES(?, ?)",
                    (ts, payload),
                )
                if self.max_rows and self.max_rows > 0:
                    con.execute(
                        """
                        DELETE FROM snapshots
                        WHERE id NOT IN (
                            SELECT id FROM snapshots ORDER BY id DESC LIMIT ?
                        )
                        """,
                        (self.max_rows,),
                    )

    def recent(self, limit=50):
        limit = max(1, min(int(limit), 1000))
        with self._connect() as con:
            rows = con.execute(
                "SELECT payload FROM snapshots ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
