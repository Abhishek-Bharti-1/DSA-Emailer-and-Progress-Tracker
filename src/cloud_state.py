"""
Cloud Firestore State Manager for DSA Problems Daily Emailer.
Provides a persistent state store in Google Cloud Firestore for sent problem logs,
user streak tracking, and progress metrics when running in serverless environments
like Google Cloud Run or Cloud Functions.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from google.cloud import firestore
except ImportError:
    firestore = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class FirestoreStateManager:
    """
    Manages persistent state using Google Cloud Firestore.
    Maintains 1:1 API compatibility with the local file-based StateManager.
    """

    def __init__(
        self,
        database_id: str = "(default)",
        cache_path: Optional[Path] = None,
    ) -> None:
        if firestore is None:
            raise ImportError(
                "google-cloud-firestore is required to use FirestoreStateManager. "
                "Install it via 'pip install google-cloud-firestore'."
            )
        self.db = firestore.Client(database=database_id)
        self.sent_ref = self.db.collection("sent_problems")
        self.progress_ref = self.db.collection("state").document("progress")
        self.cache_path = Path(cache_path if cache_path else DATA_DIR / "problem_cache.json").resolve()
        self.a2z_fallback_path = DATA_DIR / "a2z_fallback.json"

    def get_all_sent_entries(self) -> list[dict]:
        """
        Retrieves all sent problem entries from Firestore ordered chronologically.
        """
        try:
            docs = self.sent_ref.order_by("date").stream()
            entries: list[dict] = []
            for doc in docs:
                data = doc.to_dict()
                if data:
                    entries.append(data)
            return entries
        except Exception as exc:
            logger.error("Failed to fetch sent entries from Firestore: %s", exc)
            return []

    def get_sent_ids(self) -> set[str]:
        """
        Returns set of all problem IDs that have been sent.
        """
        try:
            docs = self.sent_ref.select(["id"]).stream()
            sent_ids: set[str] = set()
            for doc in docs:
                data = doc.to_dict()
                if data and "id" in data and data["id"] is not None:
                    sent_ids.add(str(data["id"]))
            return sent_ids
        except Exception as exc:
            logger.error("Failed to fetch sent IDs from Firestore: %s", exc)
            return set()

    def mark_sent(self, problems: list[dict], date: str = None) -> None:
        """
        Atomically records problems as sent in Firestore and updates the progress document.
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

        batch = self.db.batch()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for p in problems:
            if not isinstance(p, dict):
                continue
            prob_id = str(p.get("id", "")).strip()
            # Canonical doc ID: date_probid (e.g. 2026-11-24_a2z-0001)
            doc_id = f"{date_str}_{prob_id}" if prob_id else f"{date_str}_{int(datetime.datetime.now().timestamp())}"
            doc_ref = self.sent_ref.document(doc_id)
            entry = {
                "id": prob_id,
                "title": str(p.get("title", "")),
                "topic": str(p.get("topic", "")),
                "difficulty": str(p.get("difficulty", "")),
                "source": str(p.get("source", "")),
                "url": str(p.get("url", "")),
                "platform": str(p.get("platform", "")),
                "date": date_str,
                "created_at": now_iso,
            }
            batch.set(doc_ref, entry)

        try:
            batch.commit()
            logger.info("Successfully recorded %d sent problem(s) in Firestore for %s", len(problems), date_str)
        except Exception as exc:
            logger.error("Failed to commit batch sent problems to Firestore: %s", exc)
            raise

        # Update progress tracking document
        self._sync_progress(date_str)

    def _sync_progress(self, latest_date_str: str) -> dict:
        """Recomputes and saves progress document in Firestore."""
        entries = self.get_all_sent_entries()
        progress = self._compute_progress(entries)
        try:
            self.progress_ref.set(progress)
            logger.info("Updated progress document in Firestore: total_sent=%d, streak=%d",
                        progress.get("total_sent", 0), progress.get("streak_days", 0))
        except Exception as exc:
            logger.warning("Failed to save progress document to Firestore: %s", exc)
        return progress

    def _get_a2z_total(self) -> int:
        if self.a2z_fallback_path.exists():
            try:
                with open(self.a2z_fallback_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return len(data)
            except Exception:
                pass
        return 455

    def _calculate_streak(self, dates_set: set[str]) -> int:
        today = datetime.date.today()
        streak = 0
        current = today
        while current.isoformat() in dates_set:
            streak += 1
            current -= datetime.timedelta(days=1)
        return streak

    def _compute_progress(self, entries: list[dict]) -> dict:
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
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def get_progress(self) -> dict:
        """Returns user progress stats from Firestore (or recomputes if missing)."""
        try:
            doc = self.progress_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception as exc:
            logger.warning("Could not read progress doc from Firestore: %s", exc)

        entries = self.get_all_sent_entries()
        progress = self._compute_progress(entries)
        try:
            self.progress_ref.set(progress)
        except Exception:
            pass
        return progress

    def get_weekly_stats(self, weeks_back: int = 1) -> dict:
        """Returns statistics for the last N weeks."""
        if weeks_back is None or weeks_back < 1:
            weeks_back = 1

        cutoff_date = datetime.date.today() - datetime.timedelta(days=weeks_back * 7)
        cutoff_str = cutoff_date.isoformat()

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
        """Saves problem cache to local file on disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(problems, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d problems to cache at %s", len(problems), self.cache_path)

    def load_cache(self) -> list[dict]:
        """Loads problems from local cache file or fallback file."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        logger.info("Loaded %d problems from cache at %s", len(data), self.cache_path)
                        return data
            except Exception as exc:
                logger.warning("Error reading cache from %s: %s", self.cache_path, exc)

        if self.a2z_fallback_path.exists():
            try:
                with open(self.a2z_fallback_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        logger.info("Loaded %d fallback problems from %s", len(data), self.a2z_fallback_path)
                        return data
            except Exception as exc:
                logger.warning("Error reading fallback from %s: %s", self.a2z_fallback_path, exc)

        return []

    def reset_state(self, clear_cache: bool = False) -> None:
        """Resets sent problems and progress in Firestore."""
        try:
            docs = self.sent_ref.stream()
            batch = self.db.batch()
            count = 0
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 400:  # Firestore batch limit is 500
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            if count > 0:
                batch.commit()

            empty_progress = self._compute_progress([])
            self.progress_ref.set(empty_progress)
            logger.info("Firestore state reset successfully.")
        except Exception as exc:
            logger.error("Failed to reset Firestore state: %s", exc)
