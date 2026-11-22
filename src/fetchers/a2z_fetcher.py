"""
Striver A2Z DSA Sheet Problem Fetcher.
Fetches curated DSA problems from Striver's A2Z DSA sheet on takeuforward.org.

Strategy:
1. Scrapes takeuforward.org:
   - Examines __NEXT_DATA__ embedded JSON script tag.
   - Falls back to HTML structure parsing (tables, accordions, cards).
   - Falls back to direct problem link extraction.
2. If scraping fails (network error, schema change, timeout), falls back
   to data/a2z_fallback.json or built-in curated problems.
"""

import json
import logging
import pathlib
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Union

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)

# Base directory for resolving relative paths
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent

# Try importing configuration constants; provide fallbacks if config is unavailable
try:
    from config import A2Z_FALLBACK_FILE, TOPICS as CONFIG_TOPICS  # type: ignore
except Exception as e:
    logger.debug("Could not import from config module: %s; using local defaults", e)
    A2Z_FALLBACK_FILE = BASE_DIR / "data" / "a2z_fallback.json"
    CONFIG_TOPICS = None

# Unified topic list according to project specification
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

# Source URLs for Striver's A2Z sheet
TAKEUFORWARD_SHEET_URLS = [
    "https://takeuforward.org/prep-hub/strivers-a2z-dsa-sheet",
    "https://takeuforward.org/prep-hub/strivers-a2z-dsa-sheet?open=1995%2C2014%2C2015%2C2016%2C2017%2C2018%2C2019%2C2020%2C2021%2C2022%2C2023%2C2024%2C2025%2C1996%2C2026%2C1997%2C2027%2C2028%2C2029%2C2030%2C1998%2C2032%2C2033%2C1999%2C2035%2C2036%2C2037%2C2038%2C2039%2C17176%2C17177%2C17178%2C17179%2C2000%2C2041%2C2042%2C2043%2C2044%2C2045%2C2001%2C2047%2C2048%2C2049%2C2050%2C2051%2C2052%2C2002%2C2054%2C17180%2C2055%2C2003%2C2057%2C2058%2C2059%2C2004%2C2061%2C2062%2C2063%2C2064%2C2005%2C2066%2C17181%2C2067%2C2068%2C2006%2C2070%2C2071%2C2072%2C2073%2C2074%2C2007%2C2076%2C2077%2C2078%2C2008%2C2080%2C2081%2C2009%2C2083%2C2084%2C2085%2C2086%2C2087%2C2088%2C2089%2C2090%2C2010%2C2092%2C2093%2C2094%2C2095%2C2096%2C2097%2C2098%2C2099%2C2100%2C2011%2C2102%2C2103%2C2012%2C2104%2C2105%2C2013%2C2107",
    "https://takeuforward.org/strivers-a2z-dsa-course/strivers-a2z-dsa-course-sheet-2/",
    "https://takeuforward.org/strivers-a2z-dsa-course/strivers-a2z-dsa-sheet/",
]

# User agent header to emulate standard browser requests
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_platform(url: str) -> str:
    """
    Detects platform (leetcode, gfg, codingninjas, codeforces, etc.) from problem URL.

    Args:
        url: URL string of the problem.

    Returns:
        Platform identifier ('leetcode', 'gfg', 'codingninjas', 'codeforces', 'takeuforward', or 'unknown').
    """
    if not url or not isinstance(url, str):
        return "unknown"

    url_lower = url.lower()

    if "leetcode" in url_lower:
        return "leetcode"
    if "geeksforgeeks" in url_lower or "gfg" in url_lower:
        return "gfg"
    if "codingninjas" in url_lower or "code360" in url_lower or "naukri.com" in url_lower:
        return "codingninjas"
    if "codeforces" in url_lower:
        return "codeforces"
    if "takeuforward" in url_lower:
        return "takeuforward"

    try:
        parsed = urlparse(url_lower)
        netloc = parsed.netloc
        if netloc:
            parts = netloc.split(".")
            if len(parts) >= 2:
                return parts[-2]
            return netloc
    except Exception:
        pass

    return "unknown"


def _normalize_difficulty(raw_diff: Optional[str]) -> str:
    """
    Normalizes problem difficulty string to Easy, Medium, or Hard.
    Supports traditional labels as well as takeUforward Prep Hub badges:
    'Basic' -> Easy, 'Core' -> Medium, 'Pro' -> Hard.

    Args:
        raw_diff: Raw difficulty string.

    Returns:
        One of 'Easy', 'Medium', 'Hard'. Defaults to 'Medium'.
    """
    if not raw_diff or not isinstance(raw_diff, str):
        return "Medium"

    diff_str = raw_diff.strip().lower()
    if diff_str in ("e", "easy", "basic", "beginner", "school") or "easy" in diff_str or "basic" in diff_str:
        return "Easy"
    if diff_str in ("h", "hard", "advanced", "difficult", "pro") or "hard" in diff_str or "adv" in diff_str or "pro" in diff_str:
        return "Hard"
    if diff_str in ("m", "med", "medium", "intermediate", "core") or "med" in diff_str or "core" in diff_str:
        return "Medium"

    return "Medium"


def normalize_topic(raw_topic: Optional[str]) -> str:
    """
    Normalizes raw step or category names to one of the 19 unified topics:
    Arrays, Strings, Linked Lists, Stacks & Queues, Trees, Binary Search Trees,
    Binary Search, Graphs, Dynamic Programming, Greedy, Backtracking,
    Bit Manipulation, Math, Heaps, Tries, Sliding Window, Two Pointers,
    Recursion, Sorting.

    Args:
        raw_topic: Raw step/topic name from scraper or data file.

    Returns:
        A unified topic string from UNIFIED_TOPICS.
    """
    if not raw_topic or not isinstance(raw_topic, str):
        return "Arrays"

    text = raw_topic.strip()
    text_lower = text.lower()

    # Exact case-insensitive match against canonical unified topics
    for topic in UNIFIED_TOPICS:
        if text_lower == topic.lower():
            return topic

    # Direct short-string mappings
    direct_map = {
        "bst": "Binary Search Trees",
        "dp": "Dynamic Programming",
        "ll": "Linked Lists",
        "bs": "Binary Search",
        "heap": "Heaps",
        "heaps": "Heaps",
        "tree": "Trees",
        "trees": "Trees",
        "graph": "Graphs",
        "graphs": "Graphs",
        "string": "Strings",
        "strings": "Strings",
        "array": "Arrays",
        "arrays": "Arrays",
        "stack": "Stacks & Queues",
        "stacks": "Stacks & Queues",
        "queue": "Stacks & Queues",
        "queues": "Stacks & Queues",
        "stacks & queues": "Stacks & Queues",
        "stacks and queues": "Stacks & Queues",
        "stack and queues": "Stacks & Queues",
        "stack and queue": "Stacks & Queues",
        "linked list": "Linked Lists",
        "linked lists": "Linked Lists",
        "linkedlist": "Linked Lists",
        "two pointers": "Two Pointers",
        "two pointer": "Two Pointers",
        "sliding window": "Sliding Window",
        "sliding window & two pointer": "Sliding Window",
        "binary search": "Binary Search",
        "binary search tree": "Binary Search Trees",
        "binary search trees": "Binary Search Trees",
        "binary tree": "Trees",
        "binary trees": "Trees",
        "bit manipulation": "Bit Manipulation",
        "bits": "Bit Manipulation",
        "bitwise": "Bit Manipulation",
        "math": "Math",
        "maths": "Math",
        "mathematics": "Math",
        "basic maths": "Math",
        "recursion": "Recursion",
        "sorting": "Sorting",
        "sorting techniques": "Sorting",
        "greedy": "Greedy",
        "greedy algorithms": "Greedy",
        "backtrack": "Backtracking",
        "backtracking": "Backtracking",
        "trie": "Tries",
        "tries": "Tries",
        "beginner problems": "Math",
        "faqs(medium)": "Arrays",
        "faqs(hard)": "Arrays",
        "fundamentals": "Arrays",
        "logic building": "Arrays",
        "algorithms": "Sorting",
    }
    if text_lower in direct_map:
        return direct_map[text_lower]

    # Striver Sheet Step Number Regex: "Step 1", "Step 3.2", "Step 16: Dynamic Programming", etc.
    step_match = re.search(r"step\s*(\d+)(?:\.(\d+))?", text_lower)
    if step_match:
        step_num = int(step_match.group(1))
        sub_step = int(step_match.group(2)) if step_match.group(2) else None

        if step_num == 1:
            if sub_step == 4 or "math" in text_lower:
                return "Math"
            if sub_step == 5 or "recursion" in text_lower:
                return "Recursion"
            if sub_step == 6 or "hashing" in text_lower:
                return "Arrays"
            return "Math"
        elif step_num == 2:
            return "Sorting"
        elif step_num == 3:
            return "Arrays"
        elif step_num == 4:
            return "Binary Search"
        elif step_num == 5:
            return "Strings"
        elif step_num == 6:
            return "Linked Lists"
        elif step_num == 7:
            if "backtrack" in text_lower or (sub_step and sub_step >= 3):
                return "Backtracking"
            return "Recursion"
        elif step_num == 8:
            if "math" in text_lower or (sub_step and sub_step == 3):
                return "Math"
            return "Bit Manipulation"
        elif step_num == 9:
            return "Stacks & Queues"
        elif step_num == 10:
            if "two pointer" in text_lower and "sliding window" not in text_lower:
                return "Two Pointers"
            return "Sliding Window"
        elif step_num == 11:
            return "Heaps"
        elif step_num == 12:
            return "Greedy"
        elif step_num == 13:
            return "Trees"
        elif step_num == 14:
            return "Binary Search Trees"
        elif step_num == 15:
            return "Graphs"
        elif step_num == 16:
            return "Dynamic Programming"
        elif step_num == 17:
            return "Tries"
        elif step_num == 18:
            return "Strings"

    # Specific keyword pattern matching in order of specificity
    if "binary search tree" in text_lower or re.search(r"\bbst\b", text_lower):
        return "Binary Search Trees"
    if "binary search" in text_lower or re.search(r"\bbs\b", text_lower):
        return "Binary Search"
    if "sliding window" in text_lower:
        return "Sliding Window"
    if "two pointer" in text_lower:
        return "Two Pointers"
    if "stack" in text_lower or "queue" in text_lower:
        return "Stacks & Queues"
    if "linked" in text_lower or "link list" in text_lower or "doubly" in text_lower or "singly" in text_lower:
        return "Linked Lists"
    if "binary tree" in text_lower or "tree" in text_lower:
        return "Trees"
    if "dynamic programming" in text_lower or re.search(r"\bdp\b", text_lower):
        return "Dynamic Programming"
    if "graph" in text_lower:
        return "Graphs"
    if "heap" in text_lower or "priority queue" in text_lower:
        return "Heaps"
    if "trie" in text_lower:
        return "Tries"
    if "backtrack" in text_lower:
        return "Backtracking"
    if "greedy" in text_lower:
        return "Greedy"
    if "bit" in text_lower or "bitwise" in text_lower:
        return "Bit Manipulation"
    if "sort" in text_lower:
        return "Sorting"
    if "recursi" in text_lower:
        return "Recursion"
    if "string" in text_lower:
        return "Strings"
    if "array" in text_lower or "matrix" in text_lower or "hashing" in text_lower:
        return "Arrays"
    if "math" in text_lower or "prime" in text_lower or "gcd" in text_lower:
        return "Math"

    return "Arrays"


def _find_problems_in_json(obj: Any, current_topic: str = "Arrays") -> List[Dict[str, str]]:
    """
    Recursively scans nested JSON (like __NEXT_DATA__) to discover problem dictionaries.

    Args:
        obj: JSON object (dict or list).
        current_topic: Topic tracked through hierarchy.

    Returns:
        List of extracted problem dicts (unformatted).
    """
    problems: List[Dict[str, str]] = []

    if isinstance(obj, dict):
        # Update topic context if container labels a step or topic
        for tk in ("step_name", "step_title", "stepTitle", "stepName", "topic", "topic_name", "topicName", "chapter", "category"):
            val = obj.get(tk)
            if isinstance(val, str) and val.strip():
                current_topic = val.strip()
                break

        # Check if current dict is a problem item
        title = None
        for k in ("title", "problem_name", "problemTitle", "name", "question_title", "questionTitle", "problem"):
            val = obj.get(k)
            if isinstance(val, str) and val.strip():
                title = val.strip()
                break

        url = None
        for k in ("url", "link", "problem_link", "problemUrl", "leetcode_link", "leetcode_url", "gfg_link", "gfg_url", "coding_ninjas_link", "external_url", "article_link"):
            val = obj.get(k)
            if isinstance(val, str) and val.startswith("http"):
                url = val.strip()
                break

        # Check nested links dict (e.g. obj["links"]["leetcode"])
        if not url and isinstance(obj.get("links"), dict):
            for lk in ("leetcode", "gfg", "codingninjas", "codeforces", "article"):
                val = obj["links"].get(lk)
                if isinstance(val, str) and val.startswith("http"):
                    url = val.strip()
                    break

        difficulty = "Medium"
        for k in ("difficulty", "diff", "level", "difficulty_level", "difficultyLevel"):
            val = obj.get(k)
            if isinstance(val, str) and val.strip():
                difficulty = val.strip()
                break

        if title and url and len(title) > 2 and not title.lower().startswith("http"):
            prob_topic = normalize_topic(obj.get("topic") or current_topic)
            problems.append({
                "title": title,
                "topic": prob_topic,
                "difficulty": _normalize_difficulty(difficulty),
                "url": url,
                "platform": _extract_platform(url),
            })
        else:
            for v in obj.values():
                problems.extend(_find_problems_in_json(v, current_topic))

    elif isinstance(obj, list):
        for item in obj:
            problems.extend(_find_problems_in_json(item, current_topic))

    return problems


def _parse_next_data(soup: Any) -> List[Dict[str, str]]:
    """
    Extracts problems from the __NEXT_DATA__ JSON script tag embedded by Next.js.
    """
    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag or not script_tag.string:
        return []

    try:
        data = json.loads(script_tag.string)
        props = data.get("props", {}).get("pageProps", {})
        extracted = _find_problems_in_json(props)
        if extracted:
            logger.info("Found %d problems in __NEXT_DATA__ pageProps", len(extracted))
            return extracted
    except Exception as e:
        logger.debug("Failed parsing __NEXT_DATA__: %s", e)

    return []


def _parse_prep_hub_structure(soup: Any) -> List[Dict[str, str]]:
    """
    Extracts problems specifically from the takeuforward.org Prep Hub UI
    (e.g., https://takeuforward.org/prep-hub/strivers-a2z-dsa-sheet).
    Parses table rows, difficulty badges (Basic/Core/Pro), and LeetCode/GFG links.
    """
    problems: List[Dict[str, str]] = []

    # Find table rows with data-slot="table-row" or class containing contentTableRow / sheet-tree
    rows = soup.find_all("tr", attrs={"data-slot": "table-row"})
    if not rows:
        rows = soup.find_all("tr", class_=re.compile(r"contentTableRow|sheet-tree", re.I))

    for row in rows:
        # Skip contest or non-problem rows
        if row.get("data-row-type") == "contest":
            continue

        # 1. Title extraction
        title = None
        # Option A: Check aria-label="Mark <Title> complete" on checkbox/button
        checkbox = row.find(attrs={"aria-label": re.compile(r"Mark\s+.+?\s+complete", re.I)})
        if checkbox and checkbox.get("aria-label"):
            m = re.search(r"Mark\s+(.+?)\s+complete", checkbox["aria-label"], re.I)
            if m:
                title = m.group(1).strip()

        # Option B: Check element with class containing problemLabel or problemName
        if not title:
            label_el = row.find(class_=re.compile(r"problemLabel|problemName", re.I))
            if label_el:
                badge = label_el.find(class_=re.compile(r"difficultyBadge", re.I))
                if badge:
                    badge.extract()
                title = label_el.get_text(strip=True)

        # Option C: Check table cell data-label="Problem"
        if not title:
            cell = row.find(attrs={"data-label": "Problem"})
            if cell:
                title = cell.get_text(strip=True)

        if not title or len(title) < 2:
            continue

        # Clean title: strip trailing difficulty tags if any
        title = re.sub(r"\s+(Basic|Core|Pro|Easy|Medium|Hard)$", "", title, flags=re.I).strip()

        # 2. Difficulty extraction (Basic -> Easy, Core -> Medium, Pro -> Hard)
        diff = "Medium"
        diff_el = row.find(class_=re.compile(r"difficultyBadge|difficulty", re.I))
        if diff_el:
            diff = _normalize_difficulty(diff_el.get_text(strip=True))
        else:
            row_text = row.get_text(separator=" ", strip=True).lower()
            if "basic" in row_text or "easy" in row_text:
                diff = "Easy"
            elif "pro" in row_text or "hard" in row_text:
                diff = "Hard"
            elif "core" in row_text or "medium" in row_text:
                diff = "Medium"

        # 3. URL extraction (prefer LeetCode/GFG, then takeuforward practice/zen, then blog)
        url = None
        lc_a = row.find("a", attrs={"aria-label": re.compile(r"LeetCode", re.I)}) or \
               row.find("a", href=re.compile(r"leetcode\.com/problems", re.I))
        if lc_a and lc_a.get("href"):
            url = lc_a["href"].strip()

        if not url:
            gfg_a = row.find("a", attrs={"aria-label": re.compile(r"Geeks", re.I)}) or \
                    row.find("a", href=re.compile(r"geeksforgeeks\.org/problems", re.I))
            if gfg_a and gfg_a.get("href"):
                url = gfg_a["href"].strip()

        if not url:
            tu_practice = row.find("a", href=re.compile(r"/practice/dsa/", re.I))
            if tu_practice and tu_practice.get("href"):
                href = tu_practice["href"].strip()
                url = href if href.startswith("http") else f"https://takeuforward.org{href}"

        if not url:
            tu_blog = row.find("a", href=re.compile(r"/blogs/", re.I)) or \
                      row.find("a", attrs={"aria-label": re.compile(r"Read article", re.I)})
            if tu_blog and tu_blog.get("href"):
                href = tu_blog["href"].strip()
                url = href if href.startswith("http") else f"https://takeuforward.org{href}"

        if not url:
            for a in row.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") and any(d in href.lower() for d in ("leetcode", "geeksforgeeks", "codingninjas", "codeforces")):
                    url = href
                    break

        if not url:
            continue

        # 4. Topic extraction from preceding header or accordion button
        topic = "Arrays"
        prev = row.find_previous(["button", "h2", "h3", "h4", "summary"])
        if prev:
            topic = normalize_topic(prev.get_text(strip=True))

        problems.append({
            "title": title,
            "topic": topic,
            "difficulty": diff,
            "url": url,
            "platform": _extract_platform(url),
        })

    return problems


def _parse_next_rsc_data(soup: Any) -> List[Dict[str, str]]:
    """
    Extracts problems from Next.js App Router RSC (React Server Component) payloads.
    Next.js App Router streams serialized components inside inline <script> tags.
    """
    problems: List[Dict[str, str]] = []
    scripts = soup.find_all("script")

    for script in scripts:
        text = script.string or ""
        if not text or ("problemLabel" not in text and "leetcode.com" not in text and "/practice/dsa/" not in text):
            continue

        # Search for JSON fragments representing problem items
        matches = re.finditer(
            r'\{[^{}]*?"(?:title|problemLabel|problemName)"\s*:\s*"([^"]+)"[^{}]*?\}',
            text
        )
        for m in matches:
            block = m.group(0)
            try:
                tm = re.search(r'"(?:title|problemLabel|problemName)"\s*:\s*"([^"]+)"', block)
                if not tm:
                    continue
                title = tm.group(1).strip()
                if len(title) < 2 or title.startswith("http"):
                    continue

                dm = re.search(r'"(?:difficulty|diff|level)"\s*:\s*"([^"]+)"', block)
                diff = _normalize_difficulty(dm.group(1) if dm else "Medium")

                um = re.search(r'"(?:url|link|leetcode|href)"\s*:\s*"([^"]+)"', block)
                if not um:
                    continue
                url = um.group(1).replace(r"\/", "/")
                if not url.startswith("http"):
                    if url.startswith("/"):
                        url = f"https://takeuforward.org{url}"
                    else:
                        continue

                top_m = re.search(r'"(?:topic|chapter|category|step_name)"\s*:\s*"([^"]+)"', block)
                topic = normalize_topic(top_m.group(1) if top_m else "Arrays")

                problems.append({
                    "title": title,
                    "topic": topic,
                    "difficulty": diff,
                    "url": url,
                    "platform": _extract_platform(url),
                })
            except Exception:
                continue

    return problems


def _parse_html_structure(soup: Any) -> List[Dict[str, str]]:
    """
    Extracts problems by parsing structured HTML elements (tables, accordions, sections).
    """
    problems: List[Dict[str, str]] = []

    # 1. Check for table rows
    tables = soup.find_all("table")
    for table in tables:
        current_topic = "Arrays"
        prev_heading = table.find_previous(["h1", "h2", "h3", "h4", "h5", "summary"])
        if prev_heading:
            current_topic = normalize_topic(prev_heading.get_text(strip=True))

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells or len(cells) < 2:
                continue

            # Look for practice/problem links inside cells
            problem_link = None
            for a in row.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") and any(
                    domain in href.lower()
                    for domain in ("leetcode", "geeksforgeeks", "codingninjas", "codeforces", "takeuforward")
                ):
                    problem_link = href
                    break

            if not problem_link:
                continue

            # Title extraction: check cells or anchor text
            title = None
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                if cell_text and len(cell_text) > 2 and not cell_text.lower() in ("practice", "link", "solve", "easy", "medium", "hard", "revision", "note"):
                    title = cell_text
                    break

            if not title:
                continue

            # Difficulty extraction
            diff = "Medium"
            row_text = row.get_text(separator=" ", strip=True).lower()
            if re.search(r"\beasy\b", row_text):
                diff = "Easy"
            elif re.search(r"\bhard\b", row_text):
                diff = "Hard"
            elif re.search(r"\bmedium\b", row_text):
                diff = "Medium"

            problems.append({
                "title": title,
                "topic": current_topic,
                "difficulty": diff,
                "url": problem_link,
                "platform": _extract_platform(problem_link),
            })

    # 2. Check for card or accordion containers if tables did not yield problems
    if not problems:
        containers = soup.find_all(["div", "section", "details", "li"], class_=re.compile(r"step|topic|problem|chapter|accordion", re.I))
        for cont in containers:
            header = cont.find(["h2", "h3", "h4", "summary", "strong"])
            cont_topic = normalize_topic(header.get_text(strip=True)) if header else "Arrays"

            for a in cont.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") and any(
                    domain in href.lower()
                    for domain in ("leetcode", "geeksforgeeks", "codingninjas", "codeforces")
                ):
                    title = a.get_text(strip=True)
                    if not title or len(title) < 3 or title.lower() in ("practice", "link", "solution"):
                        parent_text = a.parent.get_text(strip=True) if a.parent else ""
                        title = parent_text if parent_text else "DSA Problem"

                    diff = _normalize_difficulty(cont.get_text(strip=True))
                    problems.append({
                        "title": title,
                        "topic": cont_topic,
                        "difficulty": diff,
                        "url": href,
                        "platform": _extract_platform(href),
                    })

    return problems


def _parse_links(soup: Any) -> List[Dict[str, str]]:
    """
    Fallback extractor: collects all links pointing to external problem platforms.
    """
    problems: List[Dict[str, str]] = []
    target_domains = ("leetcode.com", "geeksforgeeks.org", "codingninjas.com", "code360", "codeforces.com")

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue

        if any(domain in href.lower() for domain in target_domains):
            title = a.get_text(strip=True)
            if not title or len(title) < 2 or title.lower() in ("leetcode", "gfg", "link", "practice", "solution"):
                parent = a.find_parent(["tr", "li", "div", "p"])
                if parent:
                    p_text = parent.get_text(separator=" ", strip=True)
                    title = p_text[:60] if p_text else "DSA Problem"
                else:
                    title = "DSA Problem"

            prev_heading = a.find_previous(["h1", "h2", "h3", "h4", "summary"])
            topic = normalize_topic(prev_heading.get_text(strip=True)) if prev_heading else "Arrays"

            # Check surrounding text for difficulty hints
            diff = "Medium"
            surround = a.parent.get_text(strip=True).lower() if a.parent else ""
            if "easy" in surround:
                diff = "Easy"
            elif "hard" in surround:
                diff = "Hard"

            problems.append({
                "title": title,
                "topic": topic,
                "difficulty": diff,
                "url": href,
                "platform": _extract_platform(href),
            })

    return problems


def _format_id(raw_id: Any, index: int) -> str:
    """
    Format or generate a normalized ID in the format 'a2z-NNNN'.
    """
    if raw_id is not None:
        if isinstance(raw_id, int):
            return f"a2z-{raw_id:04d}"
        raw_str = str(raw_id).strip()
        if raw_str.isdigit():
            return f"a2z-{int(raw_str):04d}"
        if raw_str.lower().startswith("a2z-"):
            suffix = raw_str[4:].strip()
            if suffix.isdigit():
                return f"a2z-{int(suffix):04d}"
            return raw_str.lower()
        if raw_str:
            return f"a2z-{raw_str}"

    return f"a2z-{index:04d}"


def _format_and_dedup_problems(raw_problems: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Deduplicates problems by (title, url) and formats them into the standard schema:
    {"id": "a2z-NNNN", "title": str, "topic": str, "difficulty": str, "source": "a2z_sheet", "url": str, "platform": str}
    """
    seen = set()
    deduped = []

    for item in raw_problems:
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        if not title or not url:
            continue

        key = (title.lower(), url.lower())
        if key in seen:
            continue
        seen.add(key)

        topic = normalize_topic(item.get("topic"))
        difficulty = _normalize_difficulty(item.get("difficulty"))
        platform = item.get("platform") or _extract_platform(url)

        deduped.append({
            "id": item.get("id"),
            "title": title,
            "topic": topic,
            "difficulty": difficulty,
            "source": "a2z_sheet",
            "url": url,
            "platform": platform,
        })

    # Assign sequential IDs zero-padded to 4 digits: a2z-0001, a2z-0002, etc.
    formatted = []
    for idx, p in enumerate(deduped, start=1):
        formatted.append({
            "id": _format_id(p.get("id"), idx),
            "title": p["title"],
            "topic": p["topic"],
            "difficulty": p["difficulty"],
            "source": "a2z_sheet",
            "url": p["url"],
            "platform": p["platform"],
        })

    return formatted


def _scrape_takeuforward() -> List[Dict[str, str]]:
    """
    Attempts to scrape Striver's A2Z DSA Sheet from takeuforward.org URLs.
    Tries __NEXT_DATA__, then HTML structure, then problem links.
    """
    if requests is None or BeautifulSoup is None:
        logger.warning("requests or beautifulsoup4 is not available; skipping live scraping")
        return []

    for url in TAKEUFORWARD_SHEET_URLS:
        try:
            logger.info("Attempting to scrape A2Z sheet from %s", url)
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=12)
            if resp.status_code != 200:
                logger.warning("GET %s returned status %d", url, resp.status_code)
                continue

            try:
                soup = BeautifulSoup(resp.content, "lxml")
            except Exception:
                soup = BeautifulSoup(resp.content, "html.parser")

            # Strategy 1: Prep Hub Structure (https://takeuforward.org/prep-hub/strivers-a2z-dsa-sheet)
            problems = _parse_prep_hub_structure(soup)
            if problems:
                logger.info("Parsed %d problems from Prep Hub structure on %s", len(problems), url)
                return _format_and_dedup_problems(problems)

            # Strategy 2: Next.js App Router RSC payload
            problems = _parse_next_rsc_data(soup)
            if problems:
                logger.info("Parsed %d problems from Next.js RSC payload on %s", len(problems), url)
                return _format_and_dedup_problems(problems)

            # Strategy 3: __NEXT_DATA__
            problems = _parse_next_data(soup)
            if problems:
                logger.info("Parsed %d problems from __NEXT_DATA__ on %s", len(problems), url)
                return _format_and_dedup_problems(problems)

            # Strategy 4: HTML structure (tables/accordions)
            problems = _parse_html_structure(soup)
            if problems:
                logger.info("Parsed %d problems from HTML structure on %s", len(problems), url)
                return _format_and_dedup_problems(problems)

            # Strategy 5: Links
            problems = _parse_links(soup)
            if problems:
                logger.info("Parsed %d problems from link tags on %s", len(problems), url)
                return _format_and_dedup_problems(problems)

        except Exception as e:
            logger.warning("Scraping %s failed: %s", url, e)

    return []


def _get_builtin_fallback_problems() -> List[Dict[str, str]]:
    """
    Returns a comprehensive, curated list of authentic Striver A2Z DSA Sheet problems
    covering all 19 unified topics across Easy, Medium, and Hard difficulties.
    """
    curated = [
        # ── Arrays ───────────────────────────────────────────
        {"title": "Largest Element in an Array", "topic": "Arrays", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/largest-element-in-array/0"},
        {"title": "Second Largest Element in an Array", "topic": "Arrays", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/second-largest3735/1"},
        {"title": "Check if Array Is Sorted and Rotated", "topic": "Arrays", "difficulty": "Easy", "url": "https://leetcode.com/problems/check-if-array-is-sorted-and-rotated/"},
        {"title": "Remove Duplicates from Sorted Array", "topic": "Arrays", "difficulty": "Easy", "url": "https://leetcode.com/problems/remove-duplicates-from-sorted-array/"},
        {"title": "Left Rotate an Array by One", "topic": "Arrays", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/cyclically-rotate-an-array-by-one2614/1"},
        {"title": "Move Zeroes", "topic": "Arrays", "difficulty": "Easy", "url": "https://leetcode.com/problems/move-zeroes/"},
        {"title": "Two Sum", "topic": "Arrays", "difficulty": "Easy", "url": "https://leetcode.com/problems/two-sum/"},
        {"title": "Sort Colors", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/sort-colors/"},
        {"title": "Majority Element", "topic": "Arrays", "difficulty": "Easy", "url": "https://leetcode.com/problems/majority-element/"},
        {"title": "Maximum Subarray (Kadane's Algorithm)", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/maximum-subarray/"},
        {"title": "Best Time to Buy and Sell Stock", "topic": "Arrays", "difficulty": "Easy", "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock/"},
        {"title": "Rearrange Array Elements by Sign", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/rearrange-array-elements-by-sign/"},
        {"title": "Next Permutation", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/next-permutation/"},
        {"title": "Longest Consecutive Sequence", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/longest-consecutive-sequence/"},
        {"title": "Set Matrix Zeroes", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/set-matrix-zeroes/"},
        {"title": "Rotate Image", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/rotate-image/"},
        {"title": "Spiral Matrix", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/spiral-matrix/"},
        {"title": "Subarray Sum Equals K", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/subarray-sum-equals-k/"},
        {"title": "3Sum", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/3sum/"},
        {"title": "4Sum", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/4sum/"},
        {"title": "Merge Intervals", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/merge-intervals/"},
        {"title": "Merge Sorted Array", "topic": "Arrays", "difficulty": "Easy", "url": "https://leetcode.com/problems/merge-sorted-array/"},
        {"title": "Find Missing And Repeating", "topic": "Arrays", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/find-missing-and-repeating2512/1"},
        {"title": "Count Inversions in Array", "topic": "Arrays", "difficulty": "Hard", "url": "https://www.geeksforgeeks.org/problems/inversion-of-array-1587115620/1"},
        {"title": "Reverse Pairs", "topic": "Arrays", "difficulty": "Hard", "url": "https://leetcode.com/problems/reverse-pairs/"},
        {"title": "Maximum Product Subarray", "topic": "Arrays", "difficulty": "Medium", "url": "https://leetcode.com/problems/maximum-product-subarray/"},

        # ── Strings ──────────────────────────────────────────
        {"title": "Remove Outermost Parentheses", "topic": "Strings", "difficulty": "Easy", "url": "https://leetcode.com/problems/remove-outermost-parentheses/"},
        {"title": "Reverse Words in a String", "topic": "Strings", "difficulty": "Medium", "url": "https://leetcode.com/problems/reverse-words-in-a-string/"},
        {"title": "Largest Odd Number in String", "topic": "Strings", "difficulty": "Easy", "url": "https://leetcode.com/problems/largest-odd-number-in-string/"},
        {"title": "Longest Common Prefix", "topic": "Strings", "difficulty": "Easy", "url": "https://leetcode.com/problems/longest-common-prefix/"},
        {"title": "Isomorphic Strings", "topic": "Strings", "difficulty": "Easy", "url": "https://leetcode.com/problems/isomorphic-strings/"},
        {"title": "Valid Anagram", "topic": "Strings", "difficulty": "Easy", "url": "https://leetcode.com/problems/valid-anagram/"},
        {"title": "Sort Characters By Frequency", "topic": "Strings", "difficulty": "Medium", "url": "https://leetcode.com/problems/sort-characters-by-frequency/"},
        {"title": "Maximum Nesting Depth of Parentheses", "topic": "Strings", "difficulty": "Easy", "url": "https://leetcode.com/problems/maximum-nesting-depth-of-the-parentheses/"},
        {"title": "Roman to Integer", "topic": "Strings", "difficulty": "Easy", "url": "https://leetcode.com/problems/roman-to-integer/"},
        {"title": "String to Integer (atoi)", "topic": "Strings", "difficulty": "Medium", "url": "https://leetcode.com/problems/string-to-integer-atoi/"},
        {"title": "Longest Palindromic Substring", "topic": "Strings", "difficulty": "Medium", "url": "https://leetcode.com/problems/longest-palindromic-substring/"},

        # ── Binary Search ────────────────────────────────────
        {"title": "Binary Search", "topic": "Binary Search", "difficulty": "Easy", "url": "https://leetcode.com/problems/binary-search/"},
        {"title": "Search Insert Position", "topic": "Binary Search", "difficulty": "Easy", "url": "https://leetcode.com/problems/search-insert-position/"},
        {"title": "Find First and Last Position of Element in Sorted Array", "topic": "Binary Search", "difficulty": "Medium", "url": "https://leetcode.com/problems/find-first-and-last-position-of-element-in-sorted-array/"},
        {"title": "Search in Rotated Sorted Array", "topic": "Binary Search", "difficulty": "Medium", "url": "https://leetcode.com/problems/search-in-rotated-sorted-array/"},
        {"title": "Search in Rotated Sorted Array II", "topic": "Binary Search", "difficulty": "Medium", "url": "https://leetcode.com/problems/search-in-rotated-sorted-array-ii/"},
        {"title": "Find Minimum in Rotated Sorted Array", "topic": "Binary Search", "difficulty": "Medium", "url": "https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/"},
        {"title": "Find Peak Element", "topic": "Binary Search", "difficulty": "Medium", "url": "https://leetcode.com/problems/find-peak-element/"},
        {"title": "Square Root of a Number", "topic": "Binary Search", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/square-root/1"},
        {"title": "Koko Eating Bananas", "topic": "Binary Search", "difficulty": "Medium", "url": "https://leetcode.com/problems/koko-eating-bananas/"},
        {"title": "Capacity To Ship Packages Within D Days", "topic": "Binary Search", "difficulty": "Medium", "url": "https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/"},
        {"title": "Allocate Minimum Pages", "topic": "Binary Search", "difficulty": "Hard", "url": "https://www.geeksforgeeks.org/problems/allocate-minimum-number-of-pages0937/1"},
        {"title": "Median of Two Sorted Arrays", "topic": "Binary Search", "difficulty": "Hard", "url": "https://leetcode.com/problems/median-of-two-sorted-arrays/"},

        # ── Linked Lists ─────────────────────────────────────
        {"title": "Introduction to Linked List", "topic": "Linked Lists", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/introduction-to-linked-list/1"},
        {"title": "Delete Node in a Linked List", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/delete-node-in-a-linked-list/"},
        {"title": "Reverse Linked List", "topic": "Linked Lists", "difficulty": "Easy", "url": "https://leetcode.com/problems/reverse-linked-list/"},
        {"title": "Middle of the Linked List", "topic": "Linked Lists", "difficulty": "Easy", "url": "https://leetcode.com/problems/middle-of-the-linked-list/"},
        {"title": "Linked List Cycle", "topic": "Linked Lists", "difficulty": "Easy", "url": "https://leetcode.com/problems/linked-list-cycle/"},
        {"title": "Linked List Cycle II", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/linked-list-cycle-ii/"},
        {"title": "Palindrome Linked List", "topic": "Linked Lists", "difficulty": "Easy", "url": "https://leetcode.com/problems/palindrome-linked-list/"},
        {"title": "Odd Even Linked List", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/odd-even-linked-list/"},
        {"title": "Remove Nth Node From End of List", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/remove-nth-node-from-end-of-list/"},
        {"title": "Delete the Middle Node of a Linked List", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/delete-the-middle-node-of-a-linked-list/"},
        {"title": "Sort List", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/sort-list/"},
        {"title": "Intersection of Two Linked Lists", "topic": "Linked Lists", "difficulty": "Easy", "url": "https://leetcode.com/problems/intersection-of-two-linked-lists/"},
        {"title": "Add Two Numbers", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/add-two-numbers/"},
        {"title": "Reverse Nodes in k-Group", "topic": "Linked Lists", "difficulty": "Hard", "url": "https://leetcode.com/problems/reverse-nodes-in-k-group/"},
        {"title": "Copy List with Random Pointer", "topic": "Linked Lists", "difficulty": "Medium", "url": "https://leetcode.com/problems/copy-list-with-random-pointer/"},

        # ── Stacks & Queues ──────────────────────────────────
        {"title": "Valid Parentheses", "topic": "Stacks & Queues", "difficulty": "Easy", "url": "https://leetcode.com/problems/valid-parentheses/"},
        {"title": "Implement Queue using Stacks", "topic": "Stacks & Queues", "difficulty": "Easy", "url": "https://leetcode.com/problems/implement-queue-using-stacks/"},
        {"title": "Implement Stack using Queues", "topic": "Stacks & Queues", "difficulty": "Easy", "url": "https://leetcode.com/problems/implement-stack-using-queues/"},
        {"title": "Next Greater Element I", "topic": "Stacks & Queues", "difficulty": "Easy", "url": "https://leetcode.com/problems/next-greater-element-i/"},
        {"title": "Next Greater Element II", "topic": "Stacks & Queues", "difficulty": "Medium", "url": "https://leetcode.com/problems/next-greater-element-ii/"},
        {"title": "Trapping Rain Water", "topic": "Stacks & Queues", "difficulty": "Hard", "url": "https://leetcode.com/problems/trapping-rain-water/"},
        {"title": "Largest Rectangle in Histogram", "topic": "Stacks & Queues", "difficulty": "Hard", "url": "https://leetcode.com/problems/largest-rectangle-in-histogram/"},
        {"title": "Sliding Window Maximum", "topic": "Stacks & Queues", "difficulty": "Hard", "url": "https://leetcode.com/problems/sliding-window-maximum/"},
        {"title": "Min Stack", "topic": "Stacks & Queues", "difficulty": "Medium", "url": "https://leetcode.com/problems/min-stack/"},
        {"title": "Asteroid Collision", "topic": "Stacks & Queues", "difficulty": "Medium", "url": "https://leetcode.com/problems/asteroid-collision/"},

        # ── Sliding Window ───────────────────────────────────
        {"title": "Longest Substring Without Repeating Characters", "topic": "Sliding Window", "difficulty": "Medium", "url": "https://leetcode.com/problems/longest-substring-without-repeating-characters/"},
        {"title": "Max Consecutive Ones III", "topic": "Sliding Window", "difficulty": "Medium", "url": "https://leetcode.com/problems/max-consecutive-ones-iii/"},
        {"title": "Fruit Into Baskets", "topic": "Sliding Window", "difficulty": "Medium", "url": "https://leetcode.com/problems/fruit-into-baskets/"},
        {"title": "Longest Repeating Character Replacement", "topic": "Sliding Window", "difficulty": "Medium", "url": "https://leetcode.com/problems/longest-repeating-character-replacement/"},
        {"title": "Binary Subarrays With Sum", "topic": "Sliding Window", "difficulty": "Medium", "url": "https://leetcode.com/problems/binary-subarrays-with-sum/"},
        {"title": "Subarrays with K Different Integers", "topic": "Sliding Window", "difficulty": "Hard", "url": "https://leetcode.com/problems/subarrays-with-k-different-integers/"},
        {"title": "Minimum Window Substring", "topic": "Sliding Window", "difficulty": "Hard", "url": "https://leetcode.com/problems/minimum-window-substring/"},

        # ── Two Pointers ─────────────────────────────────────
        {"title": "Two Sum II - Input Array Is Sorted", "topic": "Two Pointers", "difficulty": "Medium", "url": "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/"},
        {"title": "Container With Most Water", "topic": "Two Pointers", "difficulty": "Medium", "url": "https://leetcode.com/problems/container-with-most-water/"},
        {"title": "Trapping Rain Water (Two Pointer)", "topic": "Two Pointers", "difficulty": "Hard", "url": "https://leetcode.com/problems/trapping-rain-water/"},

        # ── Heaps ────────────────────────────────────────────
        {"title": "Kth Largest Element in an Array", "topic": "Heaps", "difficulty": "Medium", "url": "https://leetcode.com/problems/kth-largest-element-in-an-array/"},
        {"title": "Top K Frequent Elements", "topic": "Heaps", "difficulty": "Medium", "url": "https://leetcode.com/problems/top-k-frequent-elements/"},
        {"title": "Find Median from Data Stream", "topic": "Heaps", "difficulty": "Hard", "url": "https://leetcode.com/problems/find-median-from-data-stream/"},
        {"title": "Merge k Sorted Lists", "topic": "Heaps", "difficulty": "Hard", "url": "https://leetcode.com/problems/merge-k-sorted-lists/"},
        {"title": "Task Scheduler", "topic": "Heaps", "difficulty": "Medium", "url": "https://leetcode.com/problems/task-scheduler/"},

        # ── Greedy ───────────────────────────────────────────
        {"title": "Assign Cookies", "topic": "Greedy", "difficulty": "Easy", "url": "https://leetcode.com/problems/assign-cookies/"},
        {"title": "Fractional Knapsack", "topic": "Greedy", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/fractional-knapsack-1587115620/1"},
        {"title": "Lemonade Change", "topic": "Greedy", "difficulty": "Easy", "url": "https://leetcode.com/problems/lemonade-change/"},
        {"title": "Jump Game", "topic": "Greedy", "difficulty": "Medium", "url": "https://leetcode.com/problems/jump-game/"},
        {"title": "Jump Game II", "topic": "Greedy", "difficulty": "Medium", "url": "https://leetcode.com/problems/jump-game-ii/"},
        {"title": "Non-overlapping Intervals", "topic": "Greedy", "difficulty": "Medium", "url": "https://leetcode.com/problems/non-overlapping-intervals/"},
        {"title": "Candy", "topic": "Greedy", "difficulty": "Hard", "url": "https://leetcode.com/problems/candy/"},

        # ── Trees ────────────────────────────────────────────
        {"title": "Binary Tree Inorder Traversal", "topic": "Trees", "difficulty": "Easy", "url": "https://leetcode.com/problems/binary-tree-inorder-traversal/"},
        {"title": "Binary Tree Preorder Traversal", "topic": "Trees", "difficulty": "Easy", "url": "https://leetcode.com/problems/binary-tree-preorder-traversal/"},
        {"title": "Binary Tree Level Order Traversal", "topic": "Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/binary-tree-level-order-traversal/"},
        {"title": "Maximum Depth of Binary Tree", "topic": "Trees", "difficulty": "Easy", "url": "https://leetcode.com/problems/maximum-depth-of-binary-tree/"},
        {"title": "Balanced Binary Tree", "topic": "Trees", "difficulty": "Easy", "url": "https://leetcode.com/problems/balanced-binary-tree/"},
        {"title": "Diameter of Binary Tree", "topic": "Trees", "difficulty": "Easy", "url": "https://leetcode.com/problems/diameter-of-binary-tree/"},
        {"title": "Binary Tree Maximum Path Sum", "topic": "Trees", "difficulty": "Hard", "url": "https://leetcode.com/problems/binary-tree-maximum-path-sum/"},
        {"title": "Same Tree", "topic": "Trees", "difficulty": "Easy", "url": "https://leetcode.com/problems/same-tree/"},
        {"title": "Binary Tree Zigzag Level Order Traversal", "topic": "Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/binary-tree-zigzag-level-order-traversal/"},
        {"title": "Lowest Common Ancestor of a Binary Tree", "topic": "Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/lowest-common-ancestor-of-a-binary-tree/"},
        {"title": "Construct Binary Tree from Preorder and Inorder Traversal", "topic": "Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/construct-binary-tree-from-preorder-and-inorder-traversal/"},

        # ── Binary Search Trees ──────────────────────────────
        {"title": "Search in a Binary Search Tree", "topic": "Binary Search Trees", "difficulty": "Easy", "url": "https://leetcode.com/problems/search-in-a-binary-search-tree/"},
        {"title": "Ceil in a BST", "topic": "Binary Search Trees", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/implementing-ceil-in-bst/1"},
        {"title": "Floor in a BST", "topic": "Binary Search Trees", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/floor-in-bst/1"},
        {"title": "Insert into a Binary Search Tree", "topic": "Binary Search Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/insert-into-a-binary-search-tree/"},
        {"title": "Delete Node in a BST", "topic": "Binary Search Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/delete-node-in-a-bst/"},
        {"title": "Kth Smallest Element in a BST", "topic": "Binary Search Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/kth-smallest-element-in-a-bst/"},
        {"title": "Validate Binary Search Tree", "topic": "Binary Search Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/validate-binary-search-tree/"},
        {"title": "Lowest Common Ancestor of a BST", "topic": "Binary Search Trees", "difficulty": "Medium", "url": "https://leetcode.com/problems/lowest-common-ancestor-of-a-binary-search-tree/"},

        # ── Graphs ───────────────────────────────────────────
        {"title": "BFS of Graph", "topic": "Graphs", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/bfs-traversal-of-graph/1"},
        {"title": "DFS of Graph", "topic": "Graphs", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/depth-first-traversal-for-a-graph/1"},
        {"title": "Number of Provinces", "topic": "Graphs", "difficulty": "Medium", "url": "https://leetcode.com/problems/number-of-provinces/"},
        {"title": "Rotting Oranges", "topic": "Graphs", "difficulty": "Medium", "url": "https://leetcode.com/problems/rotting-oranges/"},
        {"title": "Flood Fill", "topic": "Graphs", "difficulty": "Easy", "url": "https://leetcode.com/problems/flood-fill/"},
        {"title": "01 Matrix", "topic": "Graphs", "difficulty": "Medium", "url": "https://leetcode.com/problems/01-matrix/"},
        {"title": "Word Ladder", "topic": "Graphs", "difficulty": "Hard", "url": "https://leetcode.com/problems/word-ladder/"},
        {"title": "Course Schedule", "topic": "Graphs", "difficulty": "Medium", "url": "https://leetcode.com/problems/course-schedule/"},
        {"title": "Course Schedule II", "topic": "Graphs", "difficulty": "Medium", "url": "https://leetcode.com/problems/course-schedule-ii/"},
        {"title": "Dijkstra's Shortest Path", "topic": "Graphs", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/implementing-dijkstra-set-1-adjacency-matrix/1"},
        {"title": "Bellman-Ford Algorithm", "topic": "Graphs", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/distance-from-the-source-bellman-ford-algorithm/1"},
        {"title": "Floyd Warshall Algorithm", "topic": "Graphs", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/implementing-floyd-warshall2042/1"},
        {"title": "Minimum Spanning Tree (Kruskal/Prim)", "topic": "Graphs", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/minimum-spanning-tree/1"},

        # ── Dynamic Programming ──────────────────────────────
        {"title": "Climbing Stairs", "topic": "Dynamic Programming", "difficulty": "Easy", "url": "https://leetcode.com/problems/climbing-stairs/"},
        {"title": "Frog Jump", "topic": "Dynamic Programming", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/geek-jump/1"},
        {"title": "House Robber", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/house-robber/"},
        {"title": "House Robber II", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/house-robber-ii/"},
        {"title": "Ninja's Training", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/geeks-training/1"},
        {"title": "Unique Paths", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/unique-paths/"},
        {"title": "Unique Paths II", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/unique-paths-ii/"},
        {"title": "Minimum Path Sum", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/minimum-path-sum/"},
        {"title": "Partition Equal Subset Sum", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/partition-equal-subset-sum/"},
        {"title": "0/1 Knapsack Problem", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/0-1-knapsack-problem0945/1"},
        {"title": "Coin Change", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/coin-change/"},
        {"title": "Target Sum", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/target-sum/"},
        {"title": "Longest Common Subsequence", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/longest-common-subsequence/"},
        {"title": "Longest Palindromic Subsequence", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/longest-palindromic-subsequence/"},
        {"title": "Edit Distance", "topic": "Dynamic Programming", "difficulty": "Hard", "url": "https://leetcode.com/problems/edit-distance/"},
        {"title": "Best Time to Buy and Sell Stock III", "topic": "Dynamic Programming", "difficulty": "Hard", "url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock-iii/"},
        {"title": "Longest Increasing Subsequence", "topic": "Dynamic Programming", "difficulty": "Medium", "url": "https://leetcode.com/problems/longest-increasing-subsequence/"},
        {"title": "Matrix Chain Multiplication", "topic": "Dynamic Programming", "difficulty": "Hard", "url": "https://www.geeksforgeeks.org/problems/matrix-chain-multiplication0303/1"},

        # ── Tries ────────────────────────────────────────────
        {"title": "Implement Trie (Prefix Tree)", "topic": "Tries", "difficulty": "Medium", "url": "https://leetcode.com/problems/implement-trie-prefix-tree/"},
        {"title": "Implement Trie II", "topic": "Tries", "difficulty": "Medium", "url": "https://www.naukri.com/code360/problems/implement-trie_1387095"},
        {"title": "Complete String", "topic": "Tries", "difficulty": "Medium", "url": "https://www.naukri.com/code360/problems/complete-string_2687860"},
        {"title": "Count Distinct Substrings", "topic": "Tries", "difficulty": "Medium", "url": "https://www.naukri.com/code360/problems/count-distinct-substrings_985292"},
        {"title": "Maximum XOR of Two Numbers in an Array", "topic": "Tries", "difficulty": "Medium", "url": "https://leetcode.com/problems/maximum-xor-of-two-numbers-in-an-array/"},

        # ── Recursion ────────────────────────────────────────
        {"title": "Print 1 to N Without Loop", "topic": "Recursion", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/print-1-to-n-without-using-loops-1587115620/1"},
        {"title": "Fibonacci Number", "topic": "Recursion", "difficulty": "Easy", "url": "https://leetcode.com/problems/fibonacci-number/"},
        {"title": "Pow(x, n)", "topic": "Recursion", "difficulty": "Medium", "url": "https://leetcode.com/problems/powx-n/"},
        {"title": "Generate Parentheses", "topic": "Recursion", "difficulty": "Medium", "url": "https://leetcode.com/problems/generate-parentheses/"},
        {"title": "Subsets", "topic": "Recursion", "difficulty": "Medium", "url": "https://leetcode.com/problems/subsets/"},
        {"title": "Combination Sum", "topic": "Recursion", "difficulty": "Medium", "url": "https://leetcode.com/problems/combination-sum/"},
        {"title": "Combination Sum II", "topic": "Recursion", "difficulty": "Medium", "url": "https://leetcode.com/problems/combination-sum-ii/"},
        {"title": "Subset Sums", "topic": "Recursion", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/subset-sums2234/1"},
        {"title": "Subsets II", "topic": "Recursion", "difficulty": "Medium", "url": "https://leetcode.com/problems/subsets-ii/"},

        # ── Backtracking ─────────────────────────────────────
        {"title": "Palindrome Partitioning", "topic": "Backtracking", "difficulty": "Medium", "url": "https://leetcode.com/problems/palindrome-partitioning/"},
        {"title": "Word Search", "topic": "Backtracking", "difficulty": "Medium", "url": "https://leetcode.com/problems/word-search/"},
        {"title": "N-Queens", "topic": "Backtracking", "difficulty": "Hard", "url": "https://leetcode.com/problems/n-queens/"},
        {"title": "Rat in a Maze Problem", "topic": "Backtracking", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/rat-in-a-maze-problem/1"},
        {"title": "Sudoku Solver", "topic": "Backtracking", "difficulty": "Hard", "url": "https://leetcode.com/problems/sudoku-solver/"},

        # ── Bit Manipulation ─────────────────────────────────
        {"title": "Check whether K-th bit is set or not", "topic": "Bit Manipulation", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/check-whether-k-th-bit-is-set-or-not-1587115620/1"},
        {"title": "Counting Bits", "topic": "Bit Manipulation", "difficulty": "Easy", "url": "https://leetcode.com/problems/counting-bits/"},
        {"title": "Single Number", "topic": "Bit Manipulation", "difficulty": "Easy", "url": "https://leetcode.com/problems/single-number/"},
        {"title": "Single Number II", "topic": "Bit Manipulation", "difficulty": "Medium", "url": "https://leetcode.com/problems/single-number-ii/"},
        {"title": "Single Number III", "topic": "Bit Manipulation", "difficulty": "Medium", "url": "https://leetcode.com/problems/single-number-iii/"},

        # ── Math ─────────────────────────────────────────────
        {"title": "Count Digits", "topic": "Math", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/count-digits5716/1"},
        {"title": "Reverse Integer", "topic": "Math", "difficulty": "Medium", "url": "https://leetcode.com/problems/reverse-integer/"},
        {"title": "Palindrome Number", "topic": "Math", "difficulty": "Easy", "url": "https://leetcode.com/problems/palindrome-number/"},
        {"title": "GCD or HCF", "topic": "Math", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/lcm-and-gcd4516/1"},
        {"title": "Armstrong Numbers", "topic": "Math", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/armstrong-numbers2727/1"},
        {"title": "Check for Prime", "topic": "Math", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/prime-number2314/1"},
        {"title": "Sieve of Eratosthenes", "topic": "Math", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/sieve-of-eratosthenes5242/1"},

        # ── Sorting ──────────────────────────────────────────
        {"title": "Selection Sort", "topic": "Sorting", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/selection-sort/1"},
        {"title": "Bubble Sort", "topic": "Sorting", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/bubble-sort/1"},
        {"title": "Insertion Sort", "topic": "Sorting", "difficulty": "Easy", "url": "https://www.geeksforgeeks.org/problems/insertion-sort/1"},
        {"title": "Merge Sort", "topic": "Sorting", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/merge-sort/1"},
        {"title": "Quick Sort", "topic": "Sorting", "difficulty": "Medium", "url": "https://www.geeksforgeeks.org/problems/quick-sort/1"},
    ]

    return _format_and_dedup_problems(curated)


def _load_fallback(fallback_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    """
    Loads problem list from fallback JSON file.
    If the file does not exist or fails to load, returns built-in curated problems
    and initializes the fallback file.

    Args:
        fallback_path: Path to the fallback JSON file.

    Returns:
        List of formatted problem dictionaries.
    """
    target_path = Path(fallback_path) if fallback_path else Path(A2Z_FALLBACK_FILE)

    if target_path.exists():
        try:
            logger.info("Loading fallback problems from %s", target_path)
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list) and data:
                normalized = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url", "").strip()
                    title = item.get("title", "").strip()
                    if not title:
                        continue

                    normalized.append({
                        "id": item.get("id"),
                        "title": title,
                        "topic": normalize_topic(item.get("topic")),
                        "difficulty": _normalize_difficulty(item.get("difficulty")),
                        "source": "a2z_sheet",
                        "url": url,
                        "platform": item.get("platform") or _extract_platform(url),
                    })

                # Ensure IDs follow the a2z-NNNN format
                formatted = []
                for idx, p in enumerate(normalized, start=1):
                    p["id"] = _format_id(p.get("id"), idx)
                    formatted.append(p)

                logger.info("Successfully loaded %d problems from %s", len(formatted), target_path)
                return formatted
            else:
                logger.warning("Fallback file %s contains empty or invalid data format", target_path)
        except Exception as e:
            logger.error("Failed to read fallback file %s: %s", target_path, e)

    # If file did not exist or failed, use built-in curated list
    logger.info("Using built-in curated A2Z problems as fallback")
    builtin_problems = _get_builtin_fallback_problems()

    # Automatically persist built-in list to target_path so subsequent runs have the file
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(builtin_problems, f, indent=2)
        logger.info("Saved %d built-in fallback problems to %s", len(builtin_problems), target_path)
    except Exception as e:
        logger.debug("Could not write fallback file to %s: %s", target_path, e)

    return builtin_problems


def fetch_a2z_problems(fallback_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    """
    Fetches Striver's A2Z DSA Sheet problems.

    Strategy:
    1. Try scraping takeuforward.org (looks for __NEXT_DATA__ embedded JSON,
       then HTML structure like tables/accordions, then direct links).
    2. If scraping fails (network error, timeout, HTTP failure, or empty),
       falls back to fallback_path (defaults to A2Z_FALLBACK_FILE in config).

    Args:
        fallback_path: Optional path to fallback JSON file. If None, defaults to
                       A2Z_FALLBACK_FILE from config module.

    Returns:
        List of problem dictionaries matching schema:
        {
            "id": "a2z-NNNN",
            "title": str,
            "topic": str,
            "difficulty": str,
            "source": "a2z_sheet",
            "url": str,
            "platform": str
        }
    """
    if fallback_path is None:
        try:
            from config import A2Z_FALLBACK_FILE as CONFIG_FALLBACK_FILE  # type: ignore
            fallback_path = CONFIG_FALLBACK_FILE
        except Exception as e:
            logger.debug("Falling back to default A2Z_FALLBACK_FILE: %s", e)
            fallback_path = A2Z_FALLBACK_FILE

    logger.info("Fetching Striver A2Z problems...")
    scraped_problems: List[Dict[str, str]] = []

    try:
        scraped_problems = _scrape_takeuforward()
    except Exception as e:
        logger.warning("Scraping Striver A2Z sheet failed: %s", e)
        scraped_problems = []

    if scraped_problems:
        logger.info("Scraping succeeded with %d problems", len(scraped_problems))
        # Update fallback cache if writable
        try:
            target_path = Path(fallback_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(scraped_problems, f, indent=2)
            logger.info("Cached %d problems to %s", len(scraped_problems), target_path)
        except Exception as e:
            logger.debug("Could not cache scraped problems to %s: %s", fallback_path, e)
        return scraped_problems

    logger.warning("Scraping returned no problems; falling back to %s", fallback_path)
    try:
        return _load_fallback(fallback_path)
    except Exception as e:
        logger.error("Failed to load fallback: %s. Returning emergency built-in list.", e)
        return _get_builtin_fallback_problems()
