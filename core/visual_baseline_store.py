"""SQLite baseline store for Level 3 autonomous scans."""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from utils.structured_event_logging import get_logger

logger = get_logger(__name__)


class BaselineStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path or os.getenv("BASELINE_DB_PATH", "output/baselines/baselines.db"))
        self.baseline_dir = self.db_path.parent

    def initialize(self) -> None:
        try:
            self.baseline_dir.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS baselines (
                        page_id TEXT PRIMARY KEY,
                        page_url TEXT NOT NULL,
                        screenshot_path TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        scan_id TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS baseline_versions (
                        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        page_id TEXT NOT NULL,
                        page_url TEXT NOT NULL,
                        screenshot_path TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        scan_id TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scan_runs (
                        scan_id TEXT PRIMARY KEY,
                        config_file TEXT NOT NULL,
                        target_url TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        completed_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        pages_scanned INTEGER NOT NULL,
                        pages_with_regressions INTEGER NOT NULL,
                        report_path TEXT
                    )
                    """
                )
            logger.info("baseline store initialized", extra={"db_path": str(self.db_path)})
        except sqlite3.Error as exc:
            logger.exception("Baseline store initialization failed", extra={"error": str(exc)})

    def save_baseline(self, page_id: str, page_url: str, screenshot_path: str, scan_id: str) -> Optional[str]:
        try:
            self.baseline_dir.mkdir(parents=True, exist_ok=True)
            source = Path(screenshot_path)
            safe_page_id = self._safe_page_id(page_id)
            stable_path = self.baseline_dir / f"{safe_page_id}.png"
            version_dir = self.baseline_dir / "versions"
            version_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            version_path = version_dir / f"{safe_page_id}_{scan_id}_{timestamp}.png"
            shutil.copy2(source, stable_path)
            shutil.copy2(source, version_path)
            size_bytes = stable_path.stat().st_size
            created_at = datetime.now(UTC).isoformat()
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO baselines
                    (page_id, page_url, screenshot_path, created_at, scan_id, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (page_id, page_url, str(stable_path), created_at, scan_id, size_bytes),
                )
                conn.execute(
                    """
                    INSERT INTO baseline_versions
                    (page_id, page_url, screenshot_path, created_at, scan_id, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (page_id, page_url, str(version_path), created_at, scan_id, version_path.stat().st_size),
                )
            logger.info(
                "baseline saved",
                extra={"page_id": page_id, "scan_id": scan_id, "stable_path": str(stable_path), "version_path": str(version_path)},
            )
            return str(stable_path)
        except (OSError, sqlite3.Error) as exc:
            logger.exception("Baseline save failed", extra={"page_id": page_id, "error": str(exc)})
            return None

    def get_baseline(self, page_id: str) -> Optional[dict]:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM baselines WHERE page_id = ?", (page_id,)).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.exception("Baseline lookup failed", extra={"page_id": page_id, "error": str(exc)})
            return None

    def list_baselines(self) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM baselines ORDER BY page_id").fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.exception("Baseline listing failed", extra={"error": str(exc)})
            return []

    def get_baseline_versions(self, page_id: str, limit: int = 20) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM baseline_versions
                    WHERE page_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (page_id, max(1, min(limit, 100))),
                ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.exception("Baseline version lookup failed", extra={"page_id": page_id, "error": str(exc)})
            return []

    def refresh_baseline(self, page_id: str, screenshot_path: str, scan_id: str) -> Optional[str]:
        old = self.get_baseline(page_id)
        page_url = old["page_url"] if old else page_id
        new_path = self.save_baseline(page_id, page_url, screenshot_path, scan_id)
        logger.info(
            "baseline refreshed",
            extra={"page_id": page_id, "old_path": old.get("screenshot_path") if old else None, "new_path": new_path},
        )
        return new_path

    def save_scan_run(
        self,
        scan_id: str,
        config_file: str,
        target_url: str,
        started_at: datetime,
        status: str,
        pages_scanned: int,
        pages_with_regressions: int,
        report_path: Optional[str],
    ) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO scan_runs
                    (scan_id, config_file, target_url, started_at, completed_at, status,
                     pages_scanned, pages_with_regressions, report_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scan_id,
                        config_file,
                        target_url,
                        started_at.isoformat(),
                        datetime.now(UTC).isoformat(),
                        status,
                        pages_scanned,
                        pages_with_regressions,
                        report_path,
                    ),
                )
            logger.info("scan run saved", extra={"scan_id": scan_id, "status": status})
        except sqlite3.Error as exc:
            logger.exception("Scan run save failed", extra={"scan_id": scan_id, "error": str(exc)})

    def get_scan_history(self, limit: int = 10) -> list[dict]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT ?",
                    (max(1, min(limit, 100)),),
                ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.exception("Scan history lookup failed", extra={"error": str(exc)})
            return []

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _safe_page_id(page_id: str) -> str:
        return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in page_id)


baseline_store = BaselineStore()
