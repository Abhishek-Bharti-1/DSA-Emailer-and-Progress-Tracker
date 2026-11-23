"""
Persistent state manager for the DSA Problems Daily Emailer.
Tracks sent problems, user progress, streak metrics, and problem caching.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

# Base directory for resolving default paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Attempt to load path constants from project config; fall back to local defaults
try:
    from config import (
        SENT_LOG_FILE as CONFIG_SENT_LOG_FILE,
        PROGRESS_FILE as CONFIG_PROGRESS_FILE,
        PROBLEM_CACHE_FILE as CONFIG_PROBLEM_CACHE_FILE,
        A2Z_FALLBACK_FILE as CONFIG_A2Z_FALLBACK_FILE,
    )
except Exception as e:
    logger.debug("Could not import config module directly: %s; trying relative import", e)
    try:
        from ..config import (
            SENT_LOG_FILE as CONFIG_SENT_LOG_FILE,
            PROGRESS_FILE as CONFIG_PROGRESS_FILE,
            PROBLEM_CACHE_FILE as CONFIG_PROBLEM_CACHE_FILE,
            A2Z_FALLBACK_FILE as CONFIG_A2Z_FALLBACK_FILE,
        )
    except Exception as e2:
        logger.debug("Could not import config module: %s; using local defaults", e2)
        CONFIG_SENT_LOG_FILE = DATA_DIR / "sent_log.json"
        CONFIG_PROGRESS_FILE = DATA_DIR / "progress.json"
        CONFIG_PROBLEM_CACHE_FILE = DATA_DIR / "problem_cache.json"
        CONFIG_A2Z_FALLBACK_FILE = DATA_DIR / "a2z_fallback.json"


class StateManager:
    """
    Manages persistent state: sent problems log, progress tracking, and problem cache.
    Thread-safe and uses atomic writes to prevent file corruption.
    Automatically switches to FirestoreStateManager when USE_FIRESTORE=true.
    """

    def __new__(cls, *args, **kwargs):
        if os.environ.get("USE_FIRESTORE", "").strip().lower() in ("true", "1", "yes"):
            try:
                from src.cloud_state import FirestoreStateManager
                return FirestoreStateManager()
            except Exception as e:
                logger.warning("Failed to initialize FirestoreStateManager: %s; falling back to local file state", e)
        return super().__new__(cls)

    def __init__(
        self,
        sent_log_path: Optional[Union[str, Path]] = None,
        progress_path: Optional[Union[str, Path]] = None,
        cache_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Initializes StateManager with paths for sent log, progress, and cache files.
        Defaults are loaded from project configuration constants.
        Missing JSON files are automatically created with empty list/dict structures.
        """
        self.sent_log_path = Path(
            sent_log_path if sent_log_path is not None else CONFIG_SENT_LOG_FILE
        ).resolve()
        self.progress_path = Path(
            progress_path if progress_path is not None else CONFIG_PROGRESS_FILE
        ).resolve()
        self.cache_path = Path(
            cache_path if cache_path is not None else CONFIG_PROBLEM_CACHE_FILE
        ).resolve()

        self._lock = threading.RLock()

        # Initialize JSON files if they do not exist
        with self._lock:
            self._init_files()

    def _init_files(self) -> None:
        """
        Ensures that storage directories and initial JSON files exist.
        Initializes sent_log as [], progress as {}, and cache as [].
        """
        for path, default_content in (
            (self.sent_log_path, []),
            (self.progress_path, {}),
            (self.cache_path, []),
        ):
            if not path.exists():
                logger.info("Initializing persistent state file at %s", path)
                self._atomic_write_json(path, default_content)

    def _atomic_write_json(self, file_path: Path, data: Any) -> None:
        """
        Writes data to file_path atomically by writing to a temporary file in the
        same directory and replacing the destination file.
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            delete=False,
        )
        temp_path = Path(temp_file.name)
        try:
            json.dump(data, temp_file, indent=2, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_path, file_path)
        except Exception as e:
            try:
                temp_file.close()
            except Exception:
                pass
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            logger.error("Failed atomic write to %s: %s", file_path, e)
            raise

    def _read_json(self, file_path: Path, default: Any) -> Any:
        """
        Safely reads JSON data from file_path. Returns default if file is missing,
        empty, or invalid JSON.
        """
        if not file_path.exists():
            return default
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return default
                return json.loads(content)
        except Exception as e:
            logger.warning("Failed to read JSON from %s: %s; returning default", file_path, e)
            return default

    def get_all_sent_entries(self) -> list[dict]:
        """
        Returns the full sent log entries (not just IDs).
        """
        with self._lock:
            data = self._read_json(self.sent_log_path, default=[])
            if isinstance(data, list):
                return data
            return []

    def get_sent_ids(self) -> set[str]:
        """
        Returns set of all problem IDs that have been sent.
        """
        entries = self.get_all_sent_entries()
        sent_ids: set[str] = set()
        for entry in entries:
            if isinstance(entry, dict) and "id" in entry and entry["id"] is not None:
                sent_ids.add(str(entry["id"]))
        return sent_ids

    def mark_sent(self, problems: list[dict], date: str = None) -> None:
        """
        Records problems as sent with today's date (or provided date string).
        Each entry schema:
        {"id": str, "title": str, "topic": str, "difficulty": str, "source": str, "date": str}
        """
        if not problems:
            logger.debug("mark_sent called with empty problems list; skipping")
            return

        if date is None:
            date_str = datetime.date.today().isoformat()
        elif isinstance(date, (datetime.date, datetime.datetime)):
            date_str = date.isoformat()
        else:
            date_str = str(date).strip()

        with self._lock:
            entries = self.get_all_sent_entries()
            new_entries = []
            for p in problems:
                if not isinstance(p, dict):
                    continue
                entry = {
                    "id": str(p.get("id", "")),
                    "title": str(p.get("title", "")),
                    "topic": str(p.get("topic", "")),
                    "difficulty": str(p.get("difficulty", "")),
                    "source": str(p.get("source", "")),
                    "date": date_str,
                }
                entries.append(entry)
                new_entries.append(entry)

            self._atomic_write_json(self.sent_log_path, entries)
            logger.info("Marked %d problem(s) as sent on %s", len(new_entries), date_str)

            # Update progress tracking file
            progress = self._compute_progress(entries)
            try:
                self._atomic_write_json(self.progress_path, progress)
            except Exception as e:
                logger.warning("Failed to update progress file %s: %s", self.progress_path, e)

    def _get_a2z_total(self) -> int:
        """
        Determines the total count of A2Z sheet problems.
        Checks progress file, then fallback file, defaulting to 455.
        """
        # If progress file already has a valid a2z_total, prefer it
        if self.progress_path.exists():
            data = self._read_json(self.progress_path, default={})
            if isinstance(data, dict) and "a2z_total" in data:
                try:
                    val = int(data["a2z_total"])
                    if val > 0:
                        return val
                except (ValueError, TypeError):
                    pass

        # Check fallback file
        if CONFIG_A2Z_FALLBACK_FILE and Path(CONFIG_A2Z_FALLBACK_FILE).exists():
            try:
                with open(CONFIG_A2Z_FALLBACK_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return len(data)
            except Exception as e:
                logger.debug("Failed reading A2Z fallback file %s: %s", CONFIG_A2Z_FALLBACK_FILE, e)

        return 455

    def _calculate_streak(self, dates_set: set[str]) -> int:
        """
        Streak calculation: count consecutive days from today going backwards.
        Uses datetime.date.today().isoformat() for dates.
        """
        today = datetime.date.today()
        streak = 0
        current = today
        while current.isoformat() in dates_set:
            streak += 1
            current -= datetime.timedelta(days=1)
        return streak

    def _compute_progress(self, entries: list[dict]) -> dict:
        """
        Computes progress statistics dictionary from a list of sent entries.
        """
        by_source: dict[str, int] = {}
        by_topic: dict[str, int] = {}
        by_difficulty: dict[str, int] = {}
        dates_set: set[str] = set()

        a2z_sent = 0
        valid_entries_count = 0

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            valid_entries_count += 1

            source = str(entry.get("source", "")).strip()
            if source:
                by_source[source] = by_source.get(source, 0) + 1

            topic = str(entry.get("topic", "")).strip()
            if topic:
                by_topic[topic] = by_topic.get(topic, 0) + 1

            difficulty = str(entry.get("difficulty", "")).strip()
            if difficulty:
                by_difficulty[difficulty] = by_difficulty.get(difficulty, 0) + 1

            raw_date = entry.get("date")
            if raw_date:
                clean_date = str(raw_date).split("T")[0].strip()
                if clean_date:
                    dates_set.add(clean_date)

            # Check if problem is from A2Z sheet
            prob_id = str(entry.get("id", ""))
            if source == "a2z_sheet" or prob_id.startswith("a2z-"):
                a2z_sent += 1

        dates_list = sorted(list(dates_set))
        streak_days = self._calculate_streak(dates_set)
        a2z_total = self._get_a2z_total()

        return {
            "total_sent": valid_entries_count,
            "by_source": by_source,
            "by_topic": by_topic,
            "by_difficulty": by_difficulty,
            "streak_days": streak_days,
            "a2z_total": a2z_total,
            "a2z_sent": a2z_sent,
            "dates": dates_list,
        }

    def get_progress(self) -> dict:
        """
        Returns progress stats:
        {"total_sent": int, "by_source": {source: count}, "by_topic": {topic: count},
         "by_difficulty": {diff: count}, "streak_days": int, "a2z_total": int, "a2z_sent": int,
         "dates": [list of dates problems were sent]}
        """
        with self._lock:
            entries = self.get_all_sent_entries()
            progress = self._compute_progress(entries)
            try:
                self._atomic_write_json(self.progress_path, progress)
            except Exception as e:
                logger.warning("Failed to save progress to %s: %s", self.progress_path, e)
            return progress

    def get_weekly_stats(self, weeks_back: int = 1) -> dict:
        """
        Returns stats for the last N weeks:
        {"problems_sent": int, "topics_covered": list[str], "difficulty_breakdown": {diff: count}}
        """
        if weeks_back is None or weeks_back < 1:
            weeks_back = 1

        cutoff_date = datetime.date.today() - datetime.timedelta(days=weeks_back * 7)
        cutoff_str = cutoff_date.isoformat()

        with self._lock:
            entries = self.get_all_sent_entries()

        problems_in_window = []
        topics_set = set()
        diff_breakdown: dict[str, int] = {}

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            raw_date = entry.get("date")
            if not raw_date:
                continue
            entry_date_str = str(raw_date).split("T")[0].strip()
            if entry_date_str >= cutoff_str:
                problems_in_window.append(entry)
                topic = str(entry.get("topic", "")).strip()
                if topic:
                    topics_set.add(topic)
                diff = str(entry.get("difficulty", "")).strip()
                if diff:
                    diff_breakdown[diff] = diff_breakdown.get(diff, 0) + 1

        return {
            "problems_sent": len(problems_in_window),
            "topics_covered": sorted(list(topics_set)),
            "difficulty_breakdown": diff_breakdown,
        }

    def save_cache(self, problems: list[dict]) -> None:
        """
        Saves fetched problems to the cache file.
        """
        with self._lock:
            self._atomic_write_json(self.cache_path, problems)
            logger.info("Saved %d problems to cache at %s", len(problems), self.cache_path)

    def load_cache(self) -> list[dict]:
        """
        Loads problems from the cache file. Returns empty list if not found.
        """
        with self._lock:
            if not self.cache_path.exists():
                logger.debug("Cache file %s does not exist; returning empty list", self.cache_path)
                return []
            data = self._read_json(self.cache_path, default=[])
            if isinstance(data, list):
                logger.info("Loaded %d problems from cache at %s", len(data), self.cache_path)
                return data
            logger.warning("Cache file %s did not contain a list; returning empty list", self.cache_path)
            return []

    def reset_state(self, clear_cache: bool = False) -> None:
        """
        Resets sent problems log and analytics to start afresh.
        If clear_cache is True, also empties the problem cache.
        """
        with self._lock:
            self._atomic_write_json(self.sent_log_path, [])
            fresh_progress = self._compute_progress([])
            self._atomic_write_json(self.progress_path, fresh_progress)
            if clear_cache:
                self._atomic_write_json(self.cache_path, [])
            logger.info("Persistent state reset successfully (clear_cache=%s).", clear_cache)
