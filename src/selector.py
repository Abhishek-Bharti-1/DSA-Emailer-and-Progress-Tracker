"""
Problem Selector Module.

Handles intelligent problem selection with difficulty quotas and topic diversity:
- Quota: 1 Easy, 2 Medium, 1 Hard (configurable via config.py)
- Topic diversity: All 4 problems from different topics
- Source priority: Prefer a2z_sheet when unsent problems exist, supplementing
  from fallback sources (leetcode, gfg, codeforces) as needed.
- Fallback: Relax topic diversity constraint if impossible, keeping difficulty quota strict.
- Reproducibility: Supports reproducible seeding for randomization.
"""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

# Ensure project root is in sys.path for config import
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from config import DAILY_EASY, DAILY_MEDIUM, DAILY_HARD, SOURCE_PRIORITY
except ImportError:
    DAILY_EASY = 1
    DAILY_MEDIUM = 2
    DAILY_HARD = 1
    SOURCE_PRIORITY = ["a2z_sheet", "leetcode", "gfg", "codeforces"]

logger = logging.getLogger(__name__)


def set_seed(seed: Optional[int]) -> None:
    """Set random seed for reproducible problem selection."""
    if seed is not None:
        random.seed(seed)
        logger.debug("Random seed set to %s", seed)


def _normalize_difficulty(raw_difficulty: Any) -> str:
    """
    Normalizes problem difficulty string to standard 'Easy', 'Medium', or 'Hard'.
    Defaults to 'Unknown' if unrecognized.
    """
    if not raw_difficulty or not isinstance(raw_difficulty, str):
        return "Unknown"

    cleaned = raw_difficulty.strip().capitalize()
    if cleaned in ("Easy", "Medium", "Hard"):
        return cleaned

    lower = raw_difficulty.strip().lower()
    if lower in ("easy", "e", "basic", "school"):
        return "Easy"
    if lower in ("medium", "m", "med"):
        return "Medium"
    if lower in ("hard", "h"):
        return "Hard"

    return cleaned


def _deduplicate_problems(problems: Sequence[dict]) -> list[dict]:
    """
    Deduplicates a sequence of problem dictionaries preserving order.
    Uses 'id' if present, falling back to object identity.
    """
    seen_ids: Set[str] = set()
    unique_problems: list[dict] = []

    for problem in problems:
        if not isinstance(problem, dict):
            continue
        pid = problem.get("id")
        if pid is not None:
            pid_str = str(pid).strip()
            if pid_str in seen_ids:
                continue
            seen_ids.add(pid_str)
        unique_problems.append(problem)

    return unique_problems


def get_selection_stats(
    problems: Sequence[dict],
    sent_ids: Optional[Union[Set[Any], Sequence[Any]]] = None,
) -> dict:
    """
    Computes problem pool statistics for available and unsent problems.

    Returns:
        {
            "total_available": int,
            "unsent": int,
            "by_source": {source: unsent_count},
            "by_difficulty": {diff: unsent_count},
            "a2z_remaining": int
        }
    """
    sent_set: Set[str] = {str(sid).strip() for sid in sent_ids} if sent_ids else set()
    unique_problems = _deduplicate_problems(problems)
    total_available = len(unique_problems)

    # Filter unsent
    unsent_problems = [
        p for p in unique_problems
        if str(p.get("id", "")).strip() not in sent_set
    ]
    unsent_count = len(unsent_problems)

    # Count by source (initialize with known sources for consistency)
    by_source: Dict[str, int] = {src: 0 for src in SOURCE_PRIORITY}
    for p in unsent_problems:
        src = str(p.get("source", "unknown")).strip()
        by_source[src] = by_source.get(src, 0) + 1

    # Count by difficulty
    by_difficulty: Dict[str, int] = {"Easy": 0, "Medium": 0, "Hard": 0}
    for p in unsent_problems:
        diff = _normalize_difficulty(p.get("difficulty"))
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1

    a2z_remaining = by_source.get("a2z_sheet", 0)

    return {
        "total_available": total_available,
        "unsent": unsent_count,
        "by_source": by_source,
        "by_difficulty": by_difficulty,
        "a2z_remaining": a2z_remaining,
    }


def _build_difficulty_pools(
    unsent_problems: Sequence[dict],
    source_priority: Sequence[str],
    has_a2z: bool,
) -> dict[str, list[dict]]:
    """
    Groups unsent problems by difficulty ('Easy', 'Medium', 'Hard').
    Within each difficulty:
    - If `has_a2z` is True:
        a2z_sheet problems are placed first (shuffled),
        followed by fallback sources grouped in `source_priority` order (each shuffled).
    - Otherwise:
        all sources are ordered according to `source_priority` (each shuffled).
    """
    pools: dict[str, list[dict]] = {"Easy": [], "Medium": [], "Hard": []}

    for diff in ("Easy", "Medium", "Hard"):
        matching = [
            p for p in unsent_problems
            if _normalize_difficulty(p.get("difficulty")) == diff
        ]

        if has_a2z:
            # 1. Primary priority source: a2z_sheet
            a2z_candidates = [p for p in matching if p.get("source") == "a2z_sheet"]
            random.shuffle(a2z_candidates)

            # 2. Fallback sources ordered by SOURCE_PRIORITY
            fallback_candidates: list[dict] = []
            for src in source_priority:
                if src == "a2z_sheet":
                    continue
                src_group = [p for p in matching if p.get("source") == src]
                random.shuffle(src_group)
                fallback_candidates.extend(src_group)

            # 3. Any additional unknown / other sources
            known = set(source_priority)
            other_group = [p for p in matching if p.get("source") not in known]
            random.shuffle(other_group)
            fallback_candidates.extend(other_group)

            pools[diff] = a2z_candidates + fallback_candidates
        else:
            # No unsent a2z_sheet problems -> use all sources ordered by priority
            combined: list[dict] = []
            for src in source_priority:
                src_group = [p for p in matching if p.get("source") == src]
                random.shuffle(src_group)
                combined.extend(src_group)

            known = set(source_priority)
            other_group = [p for p in matching if p.get("source") not in known]
            random.shuffle(other_group)
            combined.extend(other_group)

            pools[diff] = combined

    return pools


def _find_diverse_selection(
    pools: dict[str, list[dict]],
    targets: list[str],
) -> Optional[list[dict]]:
    """
    Attempts to select exactly one problem per slot in `targets` (e.g. ['Easy', 'Medium', 'Medium', 'Hard'])
    satisfying the strict topic diversity constraint (all selected problems have different topics
    and unique IDs).

    Uses depth-first search / backtracking over candidate pools. Because candidate pools are
    ordered with priority sources first and shuffled within sources, this guarantees:
    - Preference for priority sources (a2z_sheet first, fallback sources when needed).
    - Randomization across available problems.
    - Systematic resolution of topic conflicts.
    """
    selected: list[dict] = []
    used_ids: Set[str] = set()
    used_topics: Set[str] = set()

    def backtrack(idx: int) -> Optional[list[dict]]:
        if idx == len(targets):
            return list(selected)

        diff = targets[idx]
        candidates = pools.get(diff, [])

        for problem in candidates:
            pid = str(problem.get("id", "")).strip() or f"synthetic-{id(problem)}"
            raw_topic = problem.get("topic")
            topic = str(raw_topic).strip() if raw_topic else "Unknown"

            if pid in used_ids:
                continue
            if topic in used_topics:
                continue

            selected.append(problem)
            used_ids.add(pid)
            used_topics.add(topic)

            result = backtrack(idx + 1)
            if result is not None:
                return result

            # Backtrack
            selected.pop()
            used_ids.remove(pid)
            used_topics.remove(topic)

        return None

    return backtrack(0)


def _relaxed_selection(
    pools: dict[str, list[dict]],
    targets: list[str],
) -> list[dict]:
    """
    Selects problems satisfying the strict difficulty quota `targets`, relaxing the
    topic diversity constraint when distinct topics are insufficient.

    Maintains as much topic diversity as possible by attempting to pick unused topics first.
    Ensures unique problem IDs.
    """
    selected: list[dict] = []
    used_ids: Set[str] = set()
    used_topics: Set[str] = set()

    for diff in targets:
        candidates = pools.get(diff, [])
        chosen: Optional[dict] = None

        # Pass 1: Try to find a candidate of this difficulty with an unused topic
        for problem in candidates:
            pid = str(problem.get("id", "")).strip() or f"synthetic-{id(problem)}"
            raw_topic = problem.get("topic")
            topic = str(raw_topic).strip() if raw_topic else "Unknown"

            if pid not in used_ids and topic not in used_topics:
                chosen = problem
                used_ids.add(pid)
                used_topics.add(topic)
                break

        # Pass 2: Fall back to any unpicked problem of this difficulty
        if chosen is None:
            for problem in candidates:
                pid = str(problem.get("id", "")).strip() or f"synthetic-{id(problem)}"
                raw_topic = problem.get("topic")
                topic = str(raw_topic).strip() if raw_topic else "Unknown"

                if pid not in used_ids:
                    chosen = problem
                    used_ids.add(pid)
                    used_topics.add(topic)
                    break

        if chosen is not None:
            selected.append(chosen)
        else:
            logger.warning(
                "Not enough available problems of difficulty '%s' to meet quota.",
                diff,
            )

    return selected


def select_daily_problems(
    all_problems: Sequence[dict],
    sent_ids: Optional[Union[Set[Any], Sequence[Any]]] = None,
    a2z_total: int = 0,
    seed: Optional[int] = None,
) -> list[dict]:
    """
    Intelligently selects daily DSA problems with difficulty quotas and topic diversity.

    Algorithm:
    1. Filter out problems whose ID is in sent_ids.
    2. Determine source priority: If unsent a2z_sheet problems exist, prefer them.
       Otherwise use all sources.
    3. Pick exactly 4 problems: 1 Easy, 2 Medium, 1 Hard (DAILY_EASY, DAILY_MEDIUM, DAILY_HARD).
    4. ALL 4 must be from DIFFERENT topics.
    5. Steps:
       a. Separate available problems by difficulty (Easy/Medium/Hard).
       b. Shuffle each difficulty pool.
       c. Pick 1 Easy problem -> record topic as used.
       d. Pick 2 Medium problems with different topics (and different from Easy).
       e. Pick 1 Hard problem with a topic different from all 3 above.
    6. If not enough problems in the priority source (a2z_sheet), supplement from
       fallback sources (leetcode, codeforces, gfg).
    7. If absolutely not enough problems to satisfy all constraints, relax the topic
       diversity constraint but keep difficulty quota strict.

    Args:
        all_problems: Master list of problem dicts from cache/fetchers.
        sent_ids: Set or list of problem IDs that have already been sent.
        a2z_total: Optional total count of A2Z sheet problems for progress tracking.
        seed: Optional integer seed for reproducible randomization.

    Returns:
        List of selected problem dicts: [1 Easy, 2 Medium, 1 Hard].
    """
    if seed is not None:
        set_seed(seed)

    if not all_problems:
        logger.warning("Empty problem list provided to select_daily_problems; returning []")
        return []

    sent_set: Set[str] = {str(sid).strip() for sid in sent_ids} if sent_ids else set()

    # Calculate selection stats
    stats = get_selection_stats(all_problems, sent_set)
    total_available = stats["total_available"]
    unsent_count = stats["unsent"]
    a2z_remaining = stats["a2z_remaining"]

    logger.info(
        "Problem selection initiated: %d total available, %d unsent, %d sent IDs registered",
        total_available,
        unsent_count,
        len(sent_set),
    )
    logger.debug("Unsent breakdown by difficulty: %s", stats["by_difficulty"])
    logger.debug("Unsent breakdown by source: %s", stats["by_source"])

    # Progress tracking for A2Z Sheet
    if a2z_total > 0:
        a2z_sent = max(0, a2z_total - a2z_remaining)
        completion_pct = (a2z_sent / a2z_total) * 100.0 if a2z_total > 0 else 0.0
        logger.info(
            "A2Z Sheet progress: %d/%d sent (%d remaining, %.1f%% complete)",
            a2z_sent,
            a2z_total,
            a2z_remaining,
            completion_pct,
        )

    # 1. Filter out already-sent problems
    unique_problems = _deduplicate_problems(all_problems)
    unsent_problems = [
        p for p in unique_problems
        if str(p.get("id", "")).strip() not in sent_set
    ]

    if not unsent_problems:
        logger.warning("All available problems have already been sent; none remain to select.")
        return []

    # 2. Determine source priority: Prefer a2z_sheet if unsent problems exist
    has_a2z = a2z_remaining > 0
    if has_a2z:
        logger.info("Priority source 'a2z_sheet' active (%d unsent problems remaining)", a2z_remaining)
    else:
        logger.info("No unsent 'a2z_sheet' problems available; utilizing all fallback sources")

    # 3. Quota definition: 1 Easy, 2 Medium, 1 Hard
    targets: list[str] = (
        ["Easy"] * DAILY_EASY
        + ["Medium"] * DAILY_MEDIUM
        + ["Hard"] * DAILY_HARD
    )
    expected_total = len(targets)

    # 5a & 5b: Group by difficulty and shuffle difficulty pools with source priority ordering
    pools = _build_difficulty_pools(unsent_problems, SOURCE_PRIORITY, has_a2z)

    logger.debug(
        "Difficulty pool sizes: Easy=%d, Medium=%d, Hard=%d",
        len(pools.get("Easy", [])),
        len(pools.get("Medium", [])),
        len(pools.get("Hard", [])),
    )

    # 4 & 5c-e & 6: Attempt diverse selection (4 distinct topics)
    selected = _find_diverse_selection(pools, targets)

    # 7. Fallback: Relax topic diversity constraint if impossible
    if selected is None or len(selected) < expected_total:
        logger.warning(
            "Could not find %d problems with strictly unique topics across difficulties. "
            "Relaxing topic diversity constraint while keeping difficulty quota strict.",
            expected_total,
        )
        selected = _relaxed_selection(pools, targets)

    # Log selection results and check for fallback supplements
    if selected:
        a2z_picked = sum(1 for p in selected if p.get("source") == "a2z_sheet")
        fallback_picked = len(selected) - a2z_picked

        if has_a2z:
            if fallback_picked > 0:
                logger.info(
                    "Selected %d problem(s) from 'a2z_sheet' and supplemented %d from fallback sources",
                    a2z_picked,
                    fallback_picked,
                )
            else:
                logger.info("All %d problem(s) selected from primary source 'a2z_sheet'", len(selected))

        topics_chosen = [p.get("topic") for p in selected]
        unique_topics = set(topics_chosen)
        if len(unique_topics) == len(selected):
            logger.info("Topic diversity confirmed: all %d problems from distinct topics: %s", len(selected), topics_chosen)
        else:
            logger.warning("Topic diversity relaxed: topics selected: %s", topics_chosen)

        logger.info("Daily problem selection completed (%d problems):", len(selected))
        for idx, p in enumerate(selected, 1):
            logger.info(
                "  %d. [%s] %s | Topic: %s | Source: %s (ID: %s)",
                idx,
                p.get("difficulty"),
                p.get("title"),
                p.get("topic"),
                p.get("source"),
                p.get("id"),
            )
    else:
        logger.error("Failed to select any problems from available pools.")

    return selected
