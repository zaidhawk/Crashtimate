"""SQLite storage: cached photo analyses, saved estimates and the daily analysis count.

Everything here is a quick local-file query, so the API calls it directly instead of
handing it to a thread pool. One connection is shared behind a lock.
"""

import secrets
import sqlite3
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

_SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    sha256 TEXT PRIMARY KEY,
    data BLOB NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analyses (
    sha256 TEXT NOT NULL,
    detector TEXT NOT NULL,
    report TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (sha256, detector)
);
CREATE TABLE IF NOT EXISTS shares (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS share_photos (
    share_id TEXT NOT NULL REFERENCES shares (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (share_id, position)
);
CREATE TABLE IF NOT EXISTS daily_usage (
    day TEXT PRIMARY KEY,
    analyses INTEGER NOT NULL
);
"""


@dataclass(frozen=True)
class StoredPhoto:
    data: bytes
    width: int
    height: int


@dataclass(frozen=True)
class StoredAnalysis:
    report: str
    model: str | None


@dataclass(frozen=True)
class StoredShare:
    id: str
    payload: str
    created_at: datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Store:
    def __init__(self, path: str = ":memory:", clock: Callable[[], datetime] = _utc_now) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            # Readers don't block the writer, which matters once there's more than one request.
            self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # Photos and analyses

    def save_photo(self, sha256: str, data: bytes, width: int, height: int) -> None:
        self._run(
            "INSERT OR IGNORE INTO photos (sha256, data, width, height, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (sha256, data, width, height, self._now()),
        )

    def get_photo(self, sha256: str) -> StoredPhoto | None:
        row = self._one("SELECT data, width, height FROM photos WHERE sha256 = ?", (sha256,))
        return StoredPhoto(*row) if row else None

    def save_analysis(self, sha256: str, detector: str, report: str, model: str | None) -> None:
        self._run(
            "INSERT OR REPLACE INTO analyses (sha256, detector, report, model, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (sha256, detector, report, model, self._now()),
        )

    def get_analysis(self, sha256: str, detector: str) -> StoredAnalysis | None:
        row = self._one(
            "SELECT report, model FROM analyses WHERE sha256 = ? AND detector = ?",
            (sha256, detector),
        )
        return StoredAnalysis(*row) if row else None

    def latest_analysis(self, sha256: str) -> StoredAnalysis | None:
        """The newest analysis of a photo, whichever detector made it."""
        row = self._one(
            "SELECT report, model FROM analyses WHERE sha256 = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (sha256,),
        )
        return StoredAnalysis(*row) if row else None

    # Saved estimates

    def create_share(self, payload: str, photo_hashes: Sequence[str]) -> StoredShare:
        # 72 random bits: links can't be guessed, and they stay short enough to paste.
        share_id = secrets.token_urlsafe(9)
        created_at = self._now()
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._db.execute(
                    "INSERT INTO shares (id, payload, created_at) VALUES (?, ?, ?)",
                    (share_id, payload, created_at),
                )
                self._db.executemany(
                    "INSERT INTO share_photos (share_id, position, sha256) VALUES (?, ?, ?)",
                    [(share_id, index, sha) for index, sha in enumerate(photo_hashes)],
                )
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._db.execute("COMMIT")
        return StoredShare(share_id, payload, datetime.fromisoformat(created_at))

    def get_share(self, share_id: str) -> StoredShare | None:
        row = self._one("SELECT id, payload, created_at FROM shares WHERE id = ?", (share_id,))
        return StoredShare(row[0], row[1], datetime.fromisoformat(row[2])) if row else None

    def get_share_photo(self, share_id: str, position: int) -> StoredPhoto | None:
        row = self._one(
            "SELECT p.data, p.width, p.height FROM share_photos s "
            "JOIN photos p ON p.sha256 = s.sha256 WHERE s.share_id = ? AND s.position = ?",
            (share_id, position),
        )
        return StoredPhoto(*row) if row else None

    # Spend cap

    def reserve_analysis(self, daily_limit: int) -> bool:
        """Count one paid analysis against today's limit. False if the limit is used up."""
        day = self._clock().date().isoformat()
        with self._lock:
            if daily_limit <= 0:
                return True
            cursor = self._db.execute(
                "INSERT INTO daily_usage (day, analyses) VALUES (?, 1) "
                "ON CONFLICT (day) DO UPDATE SET analyses = analyses + 1 WHERE analyses < ?",
                (day, daily_limit),
            )
            return cursor.rowcount == 1

    def analyses_today(self) -> int:
        row = self._one(
            "SELECT analyses FROM daily_usage WHERE day = ?", (self._clock().date().isoformat(),)
        )
        return row[0] if row else 0

    # Retention

    def purge(self, older_than: timedelta) -> None:
        """Delete saved estimates, analyses and photos older than the retention period."""
        cutoff = (self._clock() - older_than).isoformat()
        with self._lock:
            self._db.execute("DELETE FROM shares WHERE created_at < ?", (cutoff,))
            self._db.execute("DELETE FROM analyses WHERE created_at < ?", (cutoff,))
            # A photo outlives the retention period while a saved estimate still shows it.
            self._db.execute(
                "DELETE FROM photos WHERE created_at < ? "
                "AND sha256 NOT IN (SELECT sha256 FROM share_photos)",
                (cutoff,),
            )

    def _now(self) -> str:
        return self._clock().isoformat()

    def _run(self, sql: str, params: tuple) -> None:
        with self._lock:
            self._db.execute(sql, params)

    def _one(self, sql: str, params: tuple) -> tuple | None:
        with self._lock:
            return self._db.execute(sql, params).fetchone()
