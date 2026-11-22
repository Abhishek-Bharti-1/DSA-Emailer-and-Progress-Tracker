"""
Codeforces problem fetcher for DSA Problems Daily Emailer.
Fetches all problems via the official Codeforces REST API (no auth required).
Endpoint: GET https://codeforces.com/api/problemset.problems
"""

import logging
from typing import Any
import requests

logger = logging.getLogger(__name__)

CODEFORCES_API_URL = "https://codeforces.com/api/problemset.problems"

# Unified topic list supported by the emailer system
UNIFIED_TOPICS = [
    "Arrays",
    "Strings",
    "Linked Lists",
    "Stacks & Queues",
    "Trees",
    "Binary Search Trees",
    "Binary Search",
    "Graphs",
    "Dynamic Programming",
    "Greedy",
    "Backtracking",
    "Bit Manipulation",
    "Math",
    "Heaps",
    "Tries",
    "Sliding Window",
    "Two Pointers",
    "Recursion",
    "Sorting",
]

# Tag to (Unified Topic, Specificity Weight) mapping.
# When a problem has multiple tags, the tag with the highest specificity
# weight is selected so that specific concepts (e.g. Trees, DP, Tries)
# take precedence over generic tags (e.g. implementation, brute force).
TAG_MAPPING: dict[str, tuple[str, int]] = {
    # Generic / Ad-hoc / Arrays (Base level: 10-15)
    "implementation": ("Arrays", 10),
    "brute force": ("Arrays", 10),
    "data structures": ("Arrays", 15),
    "interactive": ("Arrays", 10),
    "arrays": ("Arrays", 10),
    "array": ("Arrays", 10),

    # Math & Number Theory (Level: 20-40)
    "constructive algorithms": ("Math", 20),
    "math": ("Math", 25),
    "matrices": ("Math", 25),
    "probabilities": ("Math", 30),
    "games": ("Math", 30),
    "combinatorics": ("Math", 35),
    "number theory": ("Math", 35),
    "geometry": ("Math", 35),
    "fft": ("Math", 40),

    # Sorting & Greedy (Level: 30-40)
    "sortings": ("Sorting", 30),
    "sorting": ("Sorting", 30),
    "greedy": ("Greedy", 40),
    "schedules": ("Greedy", 40),

    # Strings & Hashing (Level: 45-50)
    "hashing": ("Strings", 45),
    "strings": ("Strings", 50),
    "string": ("Strings", 50),

    # Bit Manipulation (Level: 50)
    "bitmasks": ("Bit Manipulation", 50),
    "bitmask": ("Bit Manipulation", 50),
    "bitwise operations": ("Bit Manipulation", 50),

    # Recursion & Divide and Conquer (Level: 55)
    "divide and conquer": ("Recursion", 55),
    "recursion": ("Recursion", 55),

    # Pointers & Windows (Level: 60-65)
    "two pointers": ("Two Pointers", 60),
    "two-pointers": ("Two Pointers", 60),
    "sliding window": ("Sliding Window", 65),
    "sliding-window": ("Sliding Window", 65),

    # Binary Search & Search Techniques (Level: 65-70)
    "ternary search": ("Binary Search", 65),
    "meet-in-the-middle": ("Binary Search", 65),
    "binary search": ("Binary Search", 70),
    "binary-search": ("Binary Search", 70),

    # Stacks & Queues (Level: 75)
    "expression parsing": ("Stacks & Queues", 75),
    "stack": ("Stacks & Queues", 75),
    "stacks": ("Stacks & Queues", 75),
    "queue": ("Stacks & Queues", 75),
    "queues": ("Stacks & Queues", 75),

    # Heaps & Priority Queues (Level: 80)
    "heaps": ("Heaps", 80),
    "heap": ("Heaps", 80),
    "priority queue": ("Heaps", 80),

    # Backtracking (Level: 80)
    "backtracking": ("Backtracking", 80),

    # Graphs (Level: 80-85)
    "graphs": ("Graphs", 80),
    "graph": ("Graphs", 80),
    "dfs and similar": ("Graphs", 82),
    "bfs": ("Graphs", 82),
    "dsu": ("Graphs", 82),
    "disjoint set union": ("Graphs", 82),
    "shortest paths": ("Graphs", 85),
    "flows": ("Graphs", 85),
    "graph matchings": ("Graphs", 85),
    "2-sat": ("Graphs", 85),
    "bipartite graph": ("Graphs", 85),
    "eulerian circuit": ("Graphs", 85),

    # Dynamic Programming (Level: 88)
    "dp": ("Dynamic Programming", 88),
    "dynamic programming": ("Dynamic Programming", 88),

    # Trees & Tree structures (Level: 86-90)
    "segment tree": ("Trees", 86),
    "segment trees": ("Trees", 86),
    "fenwick tree": ("Trees", 86),
    "fenwick trees": ("Trees", 86),
    "trees": ("Trees", 90),
    "tree": ("Trees", 90),

    # Tries & Suffix structures (Level: 92)
    "string suffix structures": ("Tries", 92),
    "trie": ("Tries", 92),
    "tries": ("Tries", 92),

    # Binary Search Trees (Level: 95)
    "binary search tree": ("Binary Search Trees", 95),
    "binary search trees": ("Binary Search Trees", 95),
    "bst": ("Binary Search Trees", 95),

    # Linked Lists (Level: 98)
    "linked list": ("Linked Lists", 98),
    "linked lists": ("Linked Lists", 98),
}


def map_rating_to_difficulty(rating: int | float | None) -> str | None:
    """
    Map Codeforces rating to unified difficulty level:
      - Easy: 800 - 1200
      - Medium: 1300 - 1800
      - Hard: 1900+

    Skip problems with no rating or invalid rating by returning None.
    """
    if rating is None or not isinstance(rating, (int, float)):
        return None

    if rating <= 0:
        return None
    elif rating <= 1200:
        return "Easy"
    elif rating <= 1800:
        return "Medium"
    else:
        return "Hard"


def map_tags_to_topic(tags: list[str]) -> str:
    """
    Map a list of Codeforces tags to the single most specific unified topic.
    Returns 'Arrays' as default fallback if no mapped topic is found.
    """
    if not tags:
        return "Arrays"

    best_topic: str | None = None
    best_priority: int = -1

    for tag in tags:
        normalized_tag = str(tag).strip().lower()
        if normalized_tag in TAG_MAPPING:
            topic, priority = TAG_MAPPING[normalized_tag]
            if priority > best_priority:
                best_priority = priority
                best_topic = topic

    return best_topic if best_topic else "Arrays"


def fetch_codeforces_problems(timeout: int = 30) -> list[dict]:
    """
    Fetch programming problems from the Codeforces REST API.

    Endpoint: GET https://codeforces.com/api/problemset.problems
    Returns all problems in one response with `problems` and `problemStatistics` arrays.

    Returns:
        list[dict]: A list of problem dicts with schema:
            {
                "id": "cf-{contestId}-{index}",
                "title": str,
                "topic": str,
                "difficulty": str,
                "source": "codeforces",
                "url": "https://codeforces.com/problemset/problem/{contestId}/{index}",
                "platform": "codeforces"
            }
    """
    logger.info("Fetching Codeforces problems from %s", CODEFORCES_API_URL)

    try:
        response = requests.get(
            CODEFORCES_API_URL,
            headers={"User-Agent": "DSA-Problems-Daily-Emailer/1.0"},
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        logger.error("Network or HTTP error while fetching Codeforces problems: %s", exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error while fetching Codeforces problems: %s", exc)
        return []

    if not isinstance(data, dict):
        logger.error("Invalid Codeforces API response: expected JSON object, got %s", type(data).__name__)
        return []

    status = data.get("status")
    if status != "OK":
        comment = data.get("comment", "No description provided")
        logger.error("Codeforces API returned non-OK status '%s': %s", status, comment)
        return []

    result = data.get("result")
    if not isinstance(result, dict):
        logger.error("Invalid Codeforces API response: 'result' field is missing or not a dict")
        return []

    raw_problems = result.get("problems")
    if not isinstance(raw_problems, list):
        logger.error("Invalid Codeforces API response: 'problems' field is missing or not a list")
        return []

    logger.info("Received %d raw problems from Codeforces API. Filtering and parsing...", len(raw_problems))

    parsed_problems: list[dict] = []
    for problem in raw_problems:
        try:
            if not isinstance(problem, dict):
                continue

            # Only include type=PROGRAMMING problems
            if problem.get("type") != "PROGRAMMING":
                continue

            # Skip problems with no rating or invalid rating
            rating = problem.get("rating")
            difficulty = map_rating_to_difficulty(rating)
            if not difficulty:
                continue

            contest_id = problem.get("contestId")
            index = problem.get("index")
            if contest_id is None or not index:
                continue

            title = str(problem.get("name", "")).strip()
            if not title:
                continue

            index_str = str(index).strip()
            tags = problem.get("tags") or []
            topic = map_tags_to_topic(tags)

            problem_dict = {
                "id": f"cf-{contest_id}-{index_str}",
                "title": title,
                "topic": topic,
                "difficulty": difficulty,
                "source": "codeforces",
                "url": f"https://codeforces.com/problemset/problem/{contest_id}/{index_str}",
                "platform": "codeforces",
            }
            parsed_problems.append(problem_dict)
        except Exception as exc:
            logger.debug("Skipping problem due to parsing error: %s (problem: %s)", exc, problem)
            continue

    logger.info("Successfully parsed %d valid Codeforces problems", len(parsed_problems))
    return parsed_problems


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    problems = fetch_codeforces_problems()
    print(f"Total problems fetched: {len(problems)}")
    if problems:
        print("Sample problem:", problems[0])
