"""
Configuration loader for the DSA Problems Daily Emailer.
Loads settings from .env file and provides path constants.
"""

import os
import pathlib
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Minimal fallback parser if python-dotenv is not installed
    env_file = pathlib.Path(__file__).parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

# ── Gemini AI ──────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# ── Email / SMTP ──────────────────────────────────────
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")

# ── Paths ─────────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SRC_DIR = BASE_DIR / "src"

PROBLEM_CACHE_FILE = DATA_DIR / "problem_cache.json"
SENT_LOG_FILE = DATA_DIR / "sent_log.json"
PROGRESS_FILE = DATA_DIR / "progress.json"
GFG_FALLBACK_FILE = DATA_DIR / "gfg_problems.json"
A2Z_FALLBACK_FILE = DATA_DIR / "a2z_fallback.json"

# ── Selection Rules ───────────────────────────────────
DAILY_EASY = 1
DAILY_MEDIUM = 2
DAILY_HARD = 1
DAILY_TOTAL = DAILY_EASY + DAILY_MEDIUM + DAILY_HARD  # 4

# ── Source Priority ───────────────────────────────────
# Problems from higher-priority sources are used first.
SOURCE_PRIORITY = ["a2z_sheet", "leetcode", "gfg", "codeforces"]

# ── Unified Topic List ────────────────────────────────
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
