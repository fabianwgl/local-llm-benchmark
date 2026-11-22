"""SQLite backend for development and single-machine deployments."""
import contextlib
import os
import sqlite3
import threading
from datetime import datetime

from tessera.storage.sql import SqlStore
from tessera.util.timeutil import isoformat

sqlite3.register_adapter(datetime, isoformat)
sqlite3.register_converter("TIMESTAMPTZ", lambda raw: datetime.fromisoformat(raw.decode().replace("Z", "+00:00")))


class SqliteStore(SqlStore):
    def __init__(self, path):
        super().__init__()
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        if os.environ.get("TESSERA_SINGLE_NODE"):
            self._conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        self._mutex = threading.RLock()

    @contextlib.contextmanager
    def _connection(self):
        with self._mutex:
            yield self._conn

    def close(self):
        with self._mutex:
            self._conn.close()
