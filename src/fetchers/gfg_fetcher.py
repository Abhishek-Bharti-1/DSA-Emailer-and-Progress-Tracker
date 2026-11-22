"""
GeeksforGeeks (GFG) problem fetcher.

Loads DSA problems primarily from a local JSON fallback file (e.g., data/gfg_problems.json),
with an optional scraper attempt against GFG practice pages.
Since GeeksforGeeks does not provide an open public API and practice pages are
heavily protected by bot challenges and client-side rendering, scraping is expected
to fail or return empty, gracefully falling back to the maintained local JSON dataset.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Optional dependencies for scraping attempt
try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Fallback path from config module
try:
    from config import GFG_FALLBACK_FILE
except ImportError:
    # Default fallback path relative to the repository root
    GFG_FALLBACK_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "gfg_problems.json"

logger = logging.getLogger(__name__)

# Required fields that must be present and non-empty for every problem entry
REQUIRED_FIELDS = ("title", "topic", "difficulty", "url")

DIFFICULTY_MAP = {
    "school": "Easy",
    "basic": "Easy",
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
}


def _format_id(raw_id: Any, index: int) -> str:
    """
    Format or generate a normalized ID in the format 'gfg-NNNN'.
    """
    if raw_id is not None:
        if isinstance(raw_id, int):
            return f"gfg-{raw_id:04d}"
        raw_str = str(raw_id).strip()
        if raw_str.isdigit():
            return f"gfg-{int(raw_str):04d}"
        if raw_str.lower().startswith("gfg-"):
            suffix = raw_str[4:].strip()
            if suffix.isdigit():
                return f"gfg-{int(suffix):04d}"
            return raw_str.lower()
        if raw_str:
            return f"gfg-{raw_str}"

    return f"gfg-{index:04d}"


def _normalize_difficulty(raw_difficulty: Any) -> str:
    """
    Normalize difficulty string to standard Title Case (e.g., Easy, Medium, Hard).
    Maps GFG-specific 'School' and 'Basic' levels to 'Easy'.
    """
    if not raw_difficulty or not isinstance(raw_difficulty, str):
        return "Medium"
    cleaned = raw_difficulty.strip().lower()
    return DIFFICULTY_MAP.get(cleaned, raw_difficulty.strip().title())


def _validate_and_normalize_problems(raw_problems: List[Any]) -> List[dict]:
    """
    Validate that raw problem dictionaries have all required fields and normalize
    them into the unified problem schema:
    {
        "id": "gfg-NNNN",
        "title": str,
        "topic": str,
        "difficulty": str,
        "source": "gfg",
        "url": str,
        "platform": "gfg"
    }
    """
    validated: List[dict] = []
    for idx, item in enumerate(raw_problems, start=1):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping problem entry at index %d: expected dict, got %s",
                idx,
                type(item).__name__,
            )
            continue

        title = item.get("title")
        url = item.get("url") or item.get("link")
        topic = item.get("topic") or item.get("tag") or item.get("category")
        difficulty = item.get("difficulty") or item.get("level")

        candidate = {
            "title": title,
            "url": url,
            "topic": topic,
            "difficulty": difficulty,
        }

        missing = [
            field
            for field in REQUIRED_FIELDS
            if candidate[field] is None or not str(candidate[field]).strip()
        ]

        if missing:
            logger.warning(
                "Skipping problem at index %d ('%s'): missing or empty required field(s): %s",
                idx,
                item.get("title", "<unknown>"),
                ", ".join(missing),
            )
            continue

        raw_id = item.get("id")
        problem_id = _format_id(raw_id, idx)
        clean_title = str(candidate["title"]).strip()
        clean_topic = str(candidate["topic"]).strip()
        clean_difficulty = _normalize_difficulty(candidate["difficulty"])
        clean_url = str(candidate["url"]).strip()

        problem: dict = {
            "id": problem_id,
            "title": clean_title,
            "topic": clean_topic,
            "difficulty": clean_difficulty,
            "source": "gfg",
            "url": clean_url,
            "platform": "gfg",
        }
        validated.append(problem)

    return validated


def _attempt_scrape_gfg() -> List[dict]:
    """
    Optional attempt to scrape practice problems from GeeksforGeeks.
    GFG has no public API and practice pages are protected/JS-rendered,
    so this is expected to fail or return nothing in most environments.
    """
    if requests is None:
        logger.info("requests library not installed; skipping GFG scraping attempt.")
        return []

    url = "https://practiceapi.geeksforgeeks.org/api/v1/problems/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html, */*",
    }

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            logger.info(
                "GFG scrape returned HTTP %s. Falling back to local data.",
                response.status_code,
            )
            return []

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            data = response.json()
            raw_list = (
                data
                if isinstance(data, list)
                else data.get("results", data.get("problems", []))
            )
            if isinstance(raw_list, list) and raw_list:
                return _validate_and_normalize_problems(raw_list)

        # Fallback to HTML parsing if HTML was returned and BeautifulSoup is available
        if BeautifulSoup is not None:
            soup = BeautifulSoup(response.text, "html.parser")
            problem_cards = soup.find_all(
                "div", class_=lambda c: c and "problem-card" in c
            )
            if not problem_cards:
                logger.info("GFG practice page returned no parseable problem cards.")
                return []

            scraped_raw: List[dict] = []
            for idx, card in enumerate(problem_cards, start=1):
                title_tag = card.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                if href and not href.startswith("http"):
                    href = f"https://www.geeksforgeeks.org{href}"

                scraped_raw.append(
                    {
                        "id": f"gfg-{idx:04d}",
                        "title": title,
                        "topic": "General",
                        "difficulty": "Medium",
                        "url": href,
                    }
                )

            return _validate_and_normalize_problems(scraped_raw)

        logger.info("HTML response received from GFG but BeautifulSoup is not installed.")
        return []

    except requests.RequestException as e:
        logger.info("GFG scrape request failed: %s. Falling back to local file.", e)
        return []
    except Exception as e:
        logger.info("GFG scrape encountered an unexpected error: %s", e)
        return []


def _load_from_fallback(fallback_path: Union[str, Path]) -> List[dict]:
    """
    Load and validate problems from the local JSON fallback file.
    """
    path = Path(fallback_path)
    if not path.exists():
        logger.warning(
            "GFG fallback file not found at '%s'. Returning empty list.", path
        )
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error in GFG fallback file '%s': %s", path, e)
        return []
    except Exception as e:
        logger.error("Unexpected error reading GFG fallback file '%s': %s", path, e)
        return []

    if isinstance(data, list):
        raw_problems = data
    elif isinstance(data, dict):
        raw_problems = data.get("problems", data.get("data", []))
        if not isinstance(raw_problems, list):
            logger.warning(
                "Key 'problems' or 'data' in '%s' is not a list. Got: %s",
                path,
                type(raw_problems).__name__,
            )
            return []
    else:
        logger.warning(
            "Expected JSON list or object with 'problems' list in '%s', got %s",
            path,
            type(data).__name__,
        )
        return []

    validated = _validate_and_normalize_problems(raw_problems)
    logger.info("Loaded %d valid GFG problems from '%s'", len(validated), path)
    return validated


def fetch_gfg_problems(
    fallback_path: Optional[Union[str, Path]] = None,
) -> List[dict]:
    """
    Fetch GeeksforGeeks problems.

    Attempts to scrape GFG practice pages first (optional attempt; expected to fail
    due to lack of public API and bot protection). If scraping yields no problems or
    fails, gracefully falls back to loading problems from the local JSON file.

    Args:
        fallback_path: Optional path to the fallback JSON file. If None, defaults
                       to GFG_FALLBACK_FILE from config module.

    Returns:
        List of dicts with schema:
        {
            "id": "gfg-NNNN",
            "title": str,
            "topic": str,
            "difficulty": str,
            "source": "gfg",
            "url": str,
            "platform": "gfg"
        }
    """
    try:
        resolved_fallback = fallback_path
        if resolved_fallback is None:
            try:
                from config import GFG_FALLBACK_FILE
                resolved_fallback = GFG_FALLBACK_FILE
            except ImportError:
                resolved_fallback = (
                    Path(__file__).resolve().parent.parent.parent
                    / "data"
                    / "gfg_problems.json"
                )

        logger.info("Attempting to fetch GFG problems...")

        # 1. Optional scraper attempt
        problems: List[dict] = []
        try:
            problems = _attempt_scrape_gfg()
        except Exception as e:
            logger.debug("GFG scraping attempt raised an error: %s", e)
            problems = []

        if problems:
            logger.info(
                "Successfully fetched %d problems from GFG scraper.", len(problems)
            )
            return problems

        # 2. Fallback to local JSON file
        logger.info(
            "GFG scraping produced 0 problems. Falling back to local JSON: %s",
            resolved_fallback,
        )
        return _load_from_fallback(resolved_fallback)

    except Exception as e:
        logger.error("Unexpected error in fetch_gfg_problems: %s", e, exc_info=True)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = fetch_gfg_problems()
    print(f"Fetched {len(results)} GFG problems.")
