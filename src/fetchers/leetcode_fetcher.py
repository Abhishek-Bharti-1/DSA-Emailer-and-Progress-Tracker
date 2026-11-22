"""
LeetCode Problem Fetcher.

Fetches DSA problems from LeetCode using the public GraphQL API (no auth required).
Maps LeetCode topic tags to a unified topic schema with specificity prioritization.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

try:
    from config import TOPICS
except Exception:
    TOPICS = [
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

logger = logging.getLogger(__name__)

LEETCODE_GRAPHQL_ENDPOINT = "https://leetcode.com/graphql"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/problemset/all/",
    "Origin": "https://leetcode.com",
    "Accept": "application/json",
}

LEETCODE_GRAPHQL_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
    problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
    ) {
        total: totalNum
        questions: data {
            frontendQuestionId: questionFrontendId
            title
            titleSlug
            difficulty
            isPaidOnly
            topicTags {
                name
                slug
            }
        }
    }
}
"""

# Specificity priority for unified topics (higher score = more specific topic chosen)
TOPIC_PRIORITY: dict[str, int] = {
    "Tries": 100,
    "Binary Search Trees": 95,
    "Linked Lists": 90,
    "Sliding Window": 85,
    "Two Pointers": 80,
    "Heaps": 75,
    "Stacks & Queues": 70,
    "Trees": 65,
    "Dynamic Programming": 60,
    "Graphs": 55,
    "Binary Search": 50,
    "Backtracking": 45,
    "Greedy": 40,
    "Bit Manipulation": 35,
    "Sorting": 30,
    "Recursion": 25,
    "Math": 20,
    "Strings": 10,
    "Arrays": 5,
}

# Mapping LeetCode topic tag slugs/names (lowercase) to unified topics
TAG_TO_TOPIC: dict[str, str] = {
    # Tries
    "trie": "Tries",
    "tries": "Tries",
    # Binary Search Trees
    "binary-search-tree": "Binary Search Trees",
    "binary search tree": "Binary Search Trees",
    "bst": "Binary Search Trees",
    "ordered-set": "Binary Search Trees",
    "ordered set": "Binary Search Trees",
    # Trees
    "tree": "Trees",
    "trees": "Trees",
    "binary-tree": "Trees",
    "binary tree": "Trees",
    "segment-tree": "Trees",
    "segment tree": "Trees",
    "binary-indexed-tree": "Trees",
    "binary indexed tree": "Trees",
    "fenwick-tree": "Trees",
    # Linked Lists
    "linked-list": "Linked Lists",
    "linked list": "Linked Lists",
    "doubly-linked-list": "Linked Lists",
    "doubly-linked list": "Linked Lists",
    "doubly linked list": "Linked Lists",
    # Sliding Window
    "sliding-window": "Sliding Window",
    "sliding window": "Sliding Window",
    # Two Pointers
    "two-pointers": "Two Pointers",
    "two pointers": "Two Pointers",
    # Heaps
    "heap-priority-queue": "Heaps",
    "heap (priority queue)": "Heaps",
    "heap": "Heaps",
    "heaps": "Heaps",
    "priority-queue": "Heaps",
    "priority queue": "Heaps",
    # Stacks & Queues
    "stack": "Stacks & Queues",
    "stacks": "Stacks & Queues",
    "queue": "Stacks & Queues",
    "queues": "Stacks & Queues",
    "monotonic-stack": "Stacks & Queues",
    "monotonic stack": "Stacks & Queues",
    "monotonic-queue": "Stacks & Queues",
    "monotonic queue": "Stacks & Queues",
    # Dynamic Programming
    "dynamic-programming": "Dynamic Programming",
    "dynamic programming": "Dynamic Programming",
    "dp": "Dynamic Programming",
    "memoization": "Dynamic Programming",
    # Graphs
    "graph": "Graphs",
    "graphs": "Graphs",
    "breadth-first-search": "Graphs",
    "breadth-first search": "Graphs",
    "depth-first-search": "Graphs",
    "depth-first search": "Graphs",
    "union-find": "Graphs",
    "union find": "Graphs",
    "disjoint-set": "Graphs",
    "disjoint set": "Graphs",
    "shortest-path": "Graphs",
    "shortest path": "Graphs",
    "minimum-spanning-tree": "Graphs",
    "minimum spanning tree": "Graphs",
    "topological-sort": "Graphs",
    "topological sort": "Graphs",
    "strongly-connected-component": "Graphs",
    "strongly connected component": "Graphs",
    "biconnected-component": "Graphs",
    "biconnected component": "Graphs",
    "eulerian-circuit": "Graphs",
    "eulerian circuit": "Graphs",
    # Binary Search
    "binary-search": "Binary Search",
    "binary search": "Binary Search",
    # Backtracking
    "backtracking": "Backtracking",
    # Greedy
    "greedy": "Greedy",
    # Bit Manipulation
    "bit-manipulation": "Bit Manipulation",
    "bit manipulation": "Bit Manipulation",
    "bitmask": "Bit Manipulation",
    # Sorting
    "sorting": "Sorting",
    "sort": "Sorting",
    "bucket-sort": "Sorting",
    "bucket sort": "Sorting",
    "radix-sort": "Sorting",
    "radix sort": "Sorting",
    "counting-sort": "Sorting",
    "counting sort": "Sorting",
    "merge-sort": "Sorting",
    "merge sort": "Sorting",
    "quickselect": "Sorting",
    # Recursion
    "recursion": "Recursion",
    "divide-and-conquer": "Recursion",
    "divide and conquer": "Recursion",
    # Math
    "math": "Math",
    "geometry": "Math",
    "combinatorics": "Math",
    "number-theory": "Math",
    "number theory": "Math",
    "game-theory": "Math",
    "game theory": "Math",
    "probability-and-statistics": "Math",
    "probability and statistics": "Math",
    # Strings
    "string": "Strings",
    "strings": "Strings",
    "string-matching": "Strings",
    "string matching": "Strings",
    # Arrays
    "array": "Arrays",
    "arrays": "Arrays",
    "matrix": "Arrays",
    "prefix-sum": "Arrays",
    "prefix sum": "Arrays",
    "hash-table": "Arrays",
    "hash table": "Arrays",
}

TOPICS_BY_LOWER: dict[str, str] = {topic.lower(): topic for topic in TOPICS}


def map_topic(topic_tags: list[dict[str, Any]] | None) -> str:
    """
    Map LeetCode topic tags to a unified topic.

    If multiple tags exist, selects the most specific topic based on TOPIC_PRIORITY.
    Defaults to 'Arrays' if no tags match.
    """
    if not topic_tags:
        return "Arrays"

    matched_topics: set[str] = set()

    for tag in topic_tags:
        if not isinstance(tag, dict):
            continue

        slug = (tag.get("slug") or "").strip().lower()
        name = (tag.get("name") or "").strip().lower()

        topic = (
            TAG_TO_TOPIC.get(slug)
            or TAG_TO_TOPIC.get(name)
            or TOPICS_BY_LOWER.get(slug)
            or TOPICS_BY_LOWER.get(name)
        )
        if topic:
            matched_topics.add(topic)

    if not matched_topics:
        return "Arrays"

    # Select the topic with the highest specificity score
    return max(matched_topics, key=lambda t: TOPIC_PRIORITY.get(t, 0))


def _fetch_page(
    session: requests.Session,
    skip: int,
    limit: int,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    """
    Fetch a single page of problems from the LeetCode GraphQL API with retry logic.
    """
    payload = {
        "query": LEETCODE_GRAPHQL_QUERY,
        "variables": {
            "categorySlug": "",
            "skip": skip,
            "limit": limit,
            "filters": {},
        },
        "operationName": "problemsetQuestionList",
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = session.post(
                LEETCODE_GRAPHQL_ENDPOINT,
                json=payload,
                timeout=20,
            )

            if response.status_code == 429:
                wait_time = 2.0 * attempt
                logger.warning(
                    "Rate limited (429) on LeetCode API (skip=%d, attempt %d/%d). Sleeping %.1fs...",
                    skip,
                    attempt,
                    max_retries,
                    wait_time,
                )
                time.sleep(wait_time)
                continue

            response.raise_for_status()

            res_json = response.json()
            if "errors" in res_json:
                logger.warning(
                    "GraphQL response contained errors for skip=%d: %s",
                    skip,
                    res_json.get("errors"),
                )

            data = res_json.get("data") or {}
            q_list = (
                data.get("problemsetQuestionList")
                or data.get("questionList")
                or {}
            )

            total = q_list.get("total") or q_list.get("totalNum")
            questions = q_list.get("questions") or q_list.get("data") or []

            return {
                "total": total,
                "questions": questions,
            }

        except requests.RequestException as exc:
            logger.warning(
                "Network error fetching LeetCode problems (skip=%d, attempt %d/%d): %s",
                skip,
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
        except Exception as exc:
            logger.error(
                "Unexpected error parsing LeetCode response for skip=%d: %s",
                skip,
                exc,
            )
            return None

    logger.error("Failed to fetch LeetCode page after %d retries (skip=%d).", max_retries, skip)
    return None


def fetch_leetcode_problems(
    max_problems: int = 2500,
    page_size: int = 100,
    sleep_seconds: float = 1.0,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """
    Fetch public LeetCode problems via the GraphQL API with pagination.

    Args:
        max_problems: Maximum number of problems to fetch (default: 2500).
        page_size: Number of problems per page (default: 100).
        sleep_seconds: Pause between page requests for rate limiting (default: 1.0s).
        session: Optional pre-configured requests.Session (useful for testing/connection pooling).

    Returns:
        List of problem dictionaries matching the unified schema:
        {
            "id": "lc-{frontendId}",
            "title": str,
            "topic": str,
            "difficulty": str,
            "source": "leetcode",
            "url": "https://leetcode.com/problems/{slug}/",
            "platform": "leetcode"
        }
    """
    logger.info("Starting LeetCode problem fetch (max_problems=%d, page_size=%d)...", max_problems, page_size)

    problems: list[dict[str, Any]] = []
    skip = 0
    limit = page_size

    owns_session = session is None
    req_session = session or requests.Session()
    if owns_session:
        req_session.headers.update(DEFAULT_HEADERS)

    try:
        while len(problems) < max_problems:
            logger.debug(
                "Requesting LeetCode page: skip=%d, limit=%d (collected %d/%d)",
                skip,
                limit,
                len(problems),
                max_problems,
            )

            page_result = _fetch_page(req_session, skip=skip, limit=limit)
            if not page_result:
                logger.warning(
                    "No response or unrecoverable error at skip=%d. Returning %d problems collected so far.",
                    skip,
                    len(problems),
                )
                break

            raw_questions = page_result.get("questions") or []
            total_available = page_result.get("total")

            if not raw_questions:
                logger.info("Reached end of problem list at skip=%d.", skip)
                break

            page_added = 0
            for item in raw_questions:
                if len(problems) >= max_problems:
                    break

                if not isinstance(item, dict):
                    continue

                # Skip paid-only problems
                if item.get("isPaidOnly") or item.get("paidOnly"):
                    continue

                frontend_id = item.get("frontendQuestionId") or item.get("questionFrontendId")
                if not frontend_id:
                    continue

                title = (item.get("title") or "").strip()
                slug = (item.get("titleSlug") or "").strip()
                difficulty = (item.get("difficulty") or "Medium").strip().capitalize()
                topic = map_topic(item.get("topicTags"))

                problem_dict = {
                    "id": f"lc-{frontend_id}",
                    "title": title,
                    "topic": topic,
                    "difficulty": difficulty,
                    "source": "leetcode",
                    "url": f"https://leetcode.com/problems/{slug}/",
                    "platform": "leetcode",
                }
                problems.append(problem_dict)
                page_added += 1

            logger.info(
                "Fetched page skip=%d: %d valid problems added (total: %d/%d).",
                skip,
                page_added,
                len(problems),
                max_problems,
            )

            skip += limit

            # Stop if total questions known and exceeded
            if total_available is not None and skip >= total_available:
                logger.info("Fetched all available LeetCode problems (total=%d).", total_available)
                break

            # Stop if LeetCode returned fewer questions than requested limit
            if len(raw_questions) < limit:
                logger.info("Received partial page (%d < %d), no more questions.", len(raw_questions), limit)
                break

            # Sleep between pages if more problems are needed
            if len(problems) < max_problems and sleep_seconds > 0:
                time.sleep(sleep_seconds)

    except Exception as exc:
        logger.error("Unexpected error during LeetCode fetch: %s", exc, exc_info=True)
    finally:
        if owns_session:
            req_session.close()

    logger.info("Completed LeetCode fetch: successfully retrieved %d problems.", len(problems))
    return problems


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("Testing LeetCode fetcher...")
    sample_problems = fetch_leetcode_problems(max_problems=5)
    print(f"Retrieved {len(sample_problems)} problems:")
    for prob in sample_problems:
        print(prob)
