"""
Seed script to import existing local state (sent_log.json and progress.json)
into Google Cloud Firestore.
Run this once when migrating from local file storage to Firestore.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cloud_state import FirestoreStateManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")

def seed():
    logger.info("Initializing Firestore state manager...")
    state_mgr = FirestoreStateManager()

    data_dir = PROJECT_ROOT / "data"
    sent_log_path = data_dir / "sent_log.json"
    progress_path = data_dir / "progress.json"

    # 1. Import sent log
    if sent_log_path.exists():
        with open(sent_log_path, "r", encoding="utf-8") as f:
            sent_entries = json.load(f)

        if sent_entries and isinstance(sent_entries, list):
            logger.info("Migrating %d sent log entries to Firestore...", len(sent_entries))
            batch = state_mgr.db.batch()
            count = 0
            for entry in sent_entries:
                prob_id = entry.get("id")
                date_str = str(entry.get("date", "")).split("T")[0]
                doc_id = f"{date_str}_{prob_id}" if prob_id else f"entry_{count}"
                doc_ref = state_mgr.sent_ref.document(doc_id)
                batch.set(doc_ref, entry)
                count += 1
                if count % 300 == 0:
                    batch.commit()
                    batch = state_mgr.db.batch()
            if count % 300 != 0:
                batch.commit()
            logger.info("Successfully imported %d sent entries into Firestore.", count)
        else:
            logger.info("sent_log.json is empty or not a list. Skipping sent log migration.")

    # 2. Sync progress
    logger.info("Recalculating and syncing progress document in Firestore...")
    today_str = (PROJECT_ROOT / "data").name
    progress = state_mgr._sync_progress(today_str)
    logger.info("Progress synced: Total Sent: %d, Streak: %d days",
                progress.get("total_sent", 0), progress.get("streak_days", 0))
    print("\n✅ Firestore seeding completed successfully!")

if __name__ == "__main__":
    seed()
