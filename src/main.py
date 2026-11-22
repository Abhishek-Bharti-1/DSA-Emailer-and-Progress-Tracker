"""
DSA Problems Daily Emailer — Main CLI Entry Point.

Orchestrates daily problem selection & dispatch, weekly progress reports,
problem cache refreshing with multi-source deduplication, progress statistics,
and SMTP email verification.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Configure logging: INFO level, format "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

# Ensure project root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Project module imports
import config
from src.state import StateManager
from src.fetchers import (
    fetch_a2z_problems,
    fetch_leetcode_problems,
    fetch_codeforces_problems,
    fetch_gfg_problems,
)
from src.mailer import send_email
from src.selector import select_daily_problems, get_selection_stats

# Import AI agent module with fallback registration if src.agent is not yet implemented
try:
    import src.agent
except ImportError:
    import types

    _agent_mod = types.ModuleType("src.agent")

    def _default_daily_agent() -> bool:
        logger.warning("src.agent.run_daily_agent is not implemented; falling back to rule-based selector.")
        return False

    def _default_daily_fallback() -> bool:
        logger.info("Executing rule-based daily selector fallback...")
        try:
            from src.email_builder import build_daily_email

            state_mgr = StateManager()
            cache = state_mgr.load_cache()
            if not cache and hasattr(config, "A2Z_FALLBACK_FILE") and Path(config.A2Z_FALLBACK_FILE).exists():
                import json

                with open(config.A2Z_FALLBACK_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)

            if not cache:
                logger.error("No problems available in cache or fallback data to select from.")
                return False

            sent_ids = state_mgr.get_sent_ids()
            progress = state_mgr.get_progress()
            selected = select_daily_problems(
                all_problems=cache,
                sent_ids=sent_ids,
                a2z_total=progress.get("a2z_total", 455),
            )
            if not selected:
                logger.error("Failed to select daily problems from pool.")
                return False

            subject, html_body = build_daily_email(problems=selected, stats=progress)
            recipient = getattr(config, "RECIPIENT_EMAIL", "") or os.getenv("RECIPIENT_EMAIL", "")
            if not recipient:
                logger.error("RECIPIENT_EMAIL is not configured.")
                return False

            sent = send_email(recipient=recipient, subject=subject, html_body=html_body)
            if sent:
                state_mgr.mark_sent(selected)
                logger.info("Daily problems email sent successfully to %s", recipient)
                return True
            else:
                logger.error("Failed to send daily problems email via SMTP.")
                return False
        except Exception as exc:
            logger.error("Exception in rule-based daily fallback: %s", exc, exc_info=True)
            return False

    def _default_weekly_agent() -> bool:
        logger.warning("src.agent.run_weekly_agent is not implemented; falling back to template report.")
        return False

    def _default_weekly_fallback() -> bool:
        logger.info("Executing weekly progress report fallback...")
        try:
            from src.email_builder import build_weekly_email

            state_mgr = StateManager()
            weekly_stats = state_mgr.get_weekly_stats(weeks_back=1)
            overall_progress = state_mgr.get_progress()
            merged_stats = {**overall_progress, **weekly_stats}

            default_insights = (
                "**Consistency Wins**:\n"
                "- Great job practicing this week! Regular problem solving strengthens fundamental patterns.\n"
                "- Continue focusing on topics with fewer solved problems to build comprehensive mastery."
            )
            subject, html_body = build_weekly_email(stats=merged_stats, ai_insights=default_insights)
            recipient = getattr(config, "RECIPIENT_EMAIL", "") or os.getenv("RECIPIENT_EMAIL", "")
            if not recipient:
                logger.error("RECIPIENT_EMAIL is not configured.")
                return False

            sent = send_email(recipient=recipient, subject=subject, html_body=html_body)
            if sent:
                logger.info("Weekly progress report email sent successfully to %s", recipient)
                return True
            else:
                logger.error("Failed to send weekly progress report email via SMTP.")
                return False
        except Exception as exc:
            logger.error("Exception in weekly progress report fallback: %s", exc, exc_info=True)
            return False

    _agent_mod.run_daily_agent = _default_daily_agent
    _agent_mod.run_daily_fallback = _default_daily_fallback
    _agent_mod.run_weekly_agent = _default_weekly_agent
    _agent_mod.run_weekly_fallback = _default_weekly_fallback

    sys.modules["src.agent"] = _agent_mod
    import src

    setattr(src, "agent", _agent_mod)
    import src.agent


# ── Problem Deduplication Helpers ────────────────────────────────────────────

def _extract_url_slug(url: Optional[str]) -> Optional[str]:
    """
    Extracts canonical problem slug or identifier from a problem URL.
    Handles LeetCode, GeeksforGeeks, Codeforces, and TakeUForward formats.
    """
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if not cleaned:
        return None

    # Codeforces: /problemset/problem/<contest>/<index> or /contest/<contest>/problem/<index>
    cf_match = re.search(
        r"codeforces\.com/(?:problemset/problem|contest)/(\d+)/problem/([A-Za-z0-9]+)",
        cleaned,
        re.IGNORECASE,
    )
    if not cf_match:
        cf_match = re.search(
            r"codeforces\.com/problemset/problem/(\d+)/([A-Za-z0-9]+)",
            cleaned,
            re.IGNORECASE,
        )
    if cf_match:
        return f"cf-{cf_match.group(1)}-{cf_match.group(2).lower()}"

    # LeetCode or GFG: /problems/<slug>/...
    problems_match = re.search(r"/problems/([^/?#]+)", cleaned, re.IGNORECASE)
    if problems_match:
        slug = problems_match.group(1).lower().strip()
        slug = re.sub(r"\.(html|php|jsp)$", "", slug)
        if slug and slug not in ("problem", "problems"):
            return slug

    # Path fallback for takeuforward or generic problem links
    try:
        parsed = urlparse(cleaned)
        path = parsed.path.strip("/")
        if path:
            segments = [s.lower() for s in path.split("/") if s]
            if len(segments) >= 2 and segments[-1].isdigit():
                return segments[-2]
            if segments:
                last_seg = segments[-1]
                last_seg = re.sub(r"\.(html|php|jsp)$", "", last_seg)
                if last_seg and len(last_seg) > 1 and not last_seg.isdigit():
                    return last_seg
    except Exception:
        pass

    return None


def _normalize_title(title: Optional[str]) -> str:
    """
    Normalizes a problem title for duplicate detection.
    Converts to lowercase, removes leading problem numbers, and strips punctuation.
    """
    if not title or not isinstance(title, str):
        return ""
    t = title.strip().lower()
    # Strip leading problem numbering like '1. ', '#1 ', '001 - '
    t = re.sub(r"^[#\d\.\-\s:]+", "", t)
    # Remove all non-alphanumeric characters
    return re.sub(r"[^a-z0-9]", "", t)


def deduplicate_problems(all_problems: list[dict]) -> list[dict]:
    # Remove duplicates across sources by matching URL slug or normalized title
    # Keep the version from the highest-priority source (a2z_sheet > leetcode > gfg > codeforces)
    if not all_problems:
        return []

    priority_order = getattr(
        config, "SOURCE_PRIORITY", ["a2z_sheet", "leetcode", "gfg", "codeforces"]
    )
    priority_map = {src.lower(): idx for idx, src in enumerate(priority_order)}

    def get_priority(problem: dict) -> int:
        src = str(problem.get("source", "")).strip().lower()
        return priority_map.get(src, len(priority_map) + 1)

    # Stable sort by priority so highest-priority problems appear first
    sorted_problems = sorted(all_problems, key=get_priority)

    seen_slugs: set[str] = set()
    seen_titles: set[str] = set()
    seen_ids: set[str] = set()
    unique_problems: list[dict] = []

    for p in sorted_problems:
        if not isinstance(p, dict):
            continue

        pid = str(p.get("id", "")).strip()
        if pid and pid in seen_ids:
            continue

        slug = _extract_url_slug(p.get("url", ""))
        norm_title = _normalize_title(p.get("title", ""))

        is_duplicate = False
        if slug and slug in seen_slugs:
            is_duplicate = True
        if norm_title and norm_title in seen_titles:
            is_duplicate = True

        if is_duplicate:
            # Record identifiers of duplicate to catch transitive aliases
            if slug:
                seen_slugs.add(slug)
            if norm_title:
                seen_titles.add(norm_title)
            continue

        unique_problems.append(p)
        if pid:
            seen_ids.add(pid)
        if slug:
            seen_slugs.add(slug)
        if norm_title:
            seen_titles.add(norm_title)

    return unique_problems


# ── Subcommand Handlers ──────────────────────────────────────────────────────

def handle_daily() -> int:
    """
    Send the daily 4 problems email.
    1. Try running the AI agent (src.agent.run_daily_agent())
    2. If agent fails (exception or returns False), fall back to src.agent.run_daily_fallback()
    3. Exit code 0 on success, 1 on failure
    """
    logger.info("Executing daily problem dispatch routine...")
    success = False

    # 1. Try running the AI agent
    try:
        if hasattr(src.agent, "run_daily_agent") and callable(src.agent.run_daily_agent):
            logger.info("Running AI daily agent (src.agent.run_daily_agent)...")
            result = src.agent.run_daily_agent()
            if result:
                logger.info("AI daily agent completed successfully.")
                success = True
            else:
                logger.warning("AI daily agent returned False or empty result.")
        else:
            logger.warning("src.agent.run_daily_agent is not available.")
    except Exception as exc:
        logger.error("AI daily agent failed with exception: %s", exc, exc_info=True)

    # 2. If agent fails, fall back to rule-based fallback
    if not success:
        logger.warning("Falling back to daily fallback routine (src.agent.run_daily_fallback)...")
        try:
            if hasattr(src.agent, "run_daily_fallback") and callable(src.agent.run_daily_fallback):
                fallback_result = src.agent.run_daily_fallback()
                if fallback_result:
                    logger.info("Daily fallback completed successfully.")
                    success = True
                else:
                    logger.error("Daily fallback returned False or empty result.")
            else:
                logger.error("src.agent.run_daily_fallback is not available.")
        except Exception as exc:
            logger.error("Daily fallback failed with exception: %s", exc, exc_info=True)

    # 3. Exit code 0 on success, 1 on failure
    if success:
        logger.info("Daily problems routine completed successfully.")
        return 0
    else:
        logger.error("Daily problems routine failed.")
        return 1


def handle_weekly() -> int:
    """
    Send the weekly progress report.
    1. Try running the AI agent (src.agent.run_weekly_agent())
    2. If agent fails, fall back to src.agent.run_weekly_fallback()
    3. Exit code 0 on success, 1 on failure
    """
    logger.info("Executing weekly progress report routine...")
    success = False

    # 1. Try running the AI agent
    try:
        if hasattr(src.agent, "run_weekly_agent") and callable(src.agent.run_weekly_agent):
            logger.info("Running AI weekly agent (src.agent.run_weekly_agent)...")
            result = src.agent.run_weekly_agent()
            if result:
                logger.info("AI weekly agent completed successfully.")
                success = True
            else:
                logger.warning("AI weekly agent returned False or empty result.")
        else:
            logger.warning("src.agent.run_weekly_agent is not available.")
    except Exception as exc:
        logger.error("AI weekly agent failed with exception: %s", exc, exc_info=True)

    # 2. If agent fails, fall back to weekly fallback
    if not success:
        logger.warning("Falling back to weekly fallback routine (src.agent.run_weekly_fallback)...")
        try:
            if hasattr(src.agent, "run_weekly_fallback") and callable(src.agent.run_weekly_fallback):
                fallback_result = src.agent.run_weekly_fallback()
                if fallback_result:
                    logger.info("Weekly fallback completed successfully.")
                    success = True
                else:
                    logger.error("Weekly fallback returned False or empty result.")
            else:
                logger.error("src.agent.run_weekly_fallback is not available.")
        except Exception as exc:
            logger.error("Weekly fallback failed with exception: %s", exc, exc_info=True)

    # 3. Exit code 0 on success, 1 on failure
    if success:
        logger.info("Weekly progress report routine completed successfully.")
        return 0
    else:
        logger.error("Weekly progress report routine failed.")
        return 1


def handle_refresh() -> int:
    """
    Refresh the problem cache from all sources.
    1. Import all fetchers
    2. Fetch from each source (with error handling per source)
    3. Merge + deduplicate all problems
    4. Save to cache via StateManager
    5. Print summary of fetched counts
    """
    logger.info("Refreshing problem cache from all sources...")

    fetchers = [
        ("a2z_sheet", "A2Z Sheet", fetch_a2z_problems),
        ("leetcode", "LeetCode", fetch_leetcode_problems),
        ("gfg", "GeeksforGeeks", fetch_gfg_problems),
        ("codeforces", "Codeforces", fetch_codeforces_problems),
    ]

    source_counts: dict[str, int] = {}
    all_problems: list[dict] = []

    # Fetch from each source with per-source error handling
    for source_key, display_name, fetcher_fn in fetchers:
        try:
            logger.info("Fetching problems from %s...", display_name)
            problems = fetcher_fn()
            if isinstance(problems, list):
                source_counts[source_key] = len(problems)
                all_problems.extend(problems)
                logger.info("Fetched %d problems from %s", len(problems), display_name)
            else:
                logger.warning("%s returned unexpected non-list data: %s", display_name, type(problems).__name__)
                source_counts[source_key] = 0
        except Exception as exc:
            logger.error("Error fetching from %s: %s", display_name, exc, exc_info=True)
            source_counts[source_key] = 0

    total_raw = len(all_problems)
    logger.info("Total raw problems fetched: %d", total_raw)

    # Merge and deduplicate
    deduped = deduplicate_problems(all_problems)
    total_deduped = len(deduped)
    logger.info("Total unique problems after deduplication: %d", total_deduped)

    # Save to cache via StateManager
    state_mgr = StateManager()
    state_mgr.save_cache(deduped)

    # Print summary of fetched counts
    print("\n" + "=" * 55)
    print("         Problem Cache Refresh Summary")
    print("=" * 55)
    for src_key, disp_name, _ in fetchers:
        cnt = source_counts.get(src_key, 0)
        print(f"  • {disp_name:<16}: {cnt:>5} problems")
    print("-" * 55)
    print(f"  Total Raw Fetched : {total_raw:>5} problems")
    print(f"  After Deduplication: {total_deduped:>5} unique problems")
    print("=" * 55 + "\n")

    return 0


def handle_stats() -> int:
    """
    Print current progress statistics.
    1. Load progress from StateManager
    2. Print formatted stats to console
    """
    logger.info("Loading progress statistics from StateManager...")
    state_mgr = StateManager()
    progress = state_mgr.get_progress()
    cache = state_mgr.load_cache()
    sent_ids = state_mgr.get_sent_ids()

    total_sent = progress.get("total_sent", 0)
    streak_days = progress.get("streak_days", 0)
    a2z_sent = progress.get("a2z_sent", 0)
    a2z_total = progress.get("a2z_total", 455)
    by_difficulty = progress.get("by_difficulty", {})
    by_source = progress.get("by_source", {})
    by_topic = progress.get("by_topic", {})

    pct_a2z = (a2z_sent / a2z_total * 100.0) if a2z_total > 0 else 0.0

    print("\n" + "=" * 55)
    print("           DSA Problems Progress Statistics")
    print("=" * 55)
    print(f"  🔥 Current Streak       : {streak_days} day(s)")
    print(f"  📨 Total Problems Sent  : {total_sent}")
    print(f"  📚 A2Z Sheet Progress   : {a2z_sent}/{a2z_total} ({pct_a2z:.1f}%)")
    print(f"  💾 Cached Problems      : {len(cache)}")
    print(f"  📬 Unique IDs Sent      : {len(sent_ids)}")
    print("-" * 55)

    print("  Difficulty Breakdown:")
    for diff in ("Easy", "Medium", "Hard"):
        cnt = by_difficulty.get(diff, 0)
        print(f"    • {diff:<10}: {cnt}")
    for diff, cnt in by_difficulty.items():
        if diff not in ("Easy", "Medium", "Hard"):
            print(f"    • {diff:<10}: {cnt}")

    print("\n  Source Breakdown:")
    for src in ("a2z_sheet", "leetcode", "gfg", "codeforces"):
        cnt = by_source.get(src, 0)
        print(f"    • {src:<12}: {cnt}")
    for src, cnt in by_source.items():
        if src not in ("a2z_sheet", "leetcode", "gfg", "codeforces"):
            print(f"    • {src:<12}: {cnt}")

    if by_topic:
        print("\n  Top Topics Practiced:")
        sorted_topics = sorted(by_topic.items(), key=lambda item: item[1], reverse=True)
        for topic, cnt in sorted_topics[:8]:
            print(f"    • {topic:<20}: {cnt}")
        if len(sorted_topics) > 8:
            print(f"    ... and {len(sorted_topics) - 8} more topics")

    print("=" * 55 + "\n")
    return 0


def handle_test_email(recipient_override: Optional[str] = None) -> int:
    """
    Send a test email to verify SMTP setup.
    1. Send a simple test email via mailer
    2. Print success/failure
    """
    recipient = (
        recipient_override
        or getattr(config, "RECIPIENT_EMAIL", "")
        or os.getenv("RECIPIENT_EMAIL", "")
    )
    recipient = recipient.strip() if recipient else ""

    if not recipient:
        print("\n[ERROR] No recipient email specified.")
        print("Please configure RECIPIENT_EMAIL in your .env file or pass --to <email>.\n")
        logger.error("Test email aborted: RECIPIENT_EMAIL is not configured.")
        return 1

    subject = "🧪 [Test] DSA Problems Emailer — SMTP Verification"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>SMTP Verification</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #1a1a2e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #ffffff;">
  <div style="max-width: 500px; margin: 0 auto; background-color: #16213e; border: 1px solid #282b4a; border-radius: 12px; padding: 28px; text-align: center;">
    <div style="font-size: 36px; margin-bottom: 12px;">🎉</div>
    <h1 style="color: #ffffff; font-size: 22px; margin: 0 0 10px 0;">SMTP Verification Successful</h1>
    <p style="color: #a2a8d3; font-size: 14px; line-height: 1.6; margin: 0 0 20px 0;">
      Your email delivery pipeline is configured correctly! You will receive daily DSA problems and weekly progress reports at this address.
    </p>
    <div style="background-color: #222646; border-radius: 8px; padding: 12px; font-size: 13px; color: #e94560; font-weight: 600;">
      Verified at: {timestamp}
    </div>
  </div>
</body>
</html>"""

    print(f"\nSending test verification email to: {recipient}...")
    logger.info("Dispatching test email to %s...", recipient)

    try:
        success = send_email(
            recipient=recipient,
            subject=subject,
            html_body=html_body,
        )
    except Exception as exc:
        logger.error("Unexpected exception sending test email: %s", exc, exc_info=True)
        success = False

    if success:
        print(f"\n[OK] SUCCESS: Test email successfully sent to {recipient}!\n")
        logger.info("Test email sent successfully to %s", recipient)
        return 0
    else:
        print(f"\n[FAIL] FAILURE: Failed to send test email to {recipient}.")
        print("Please check SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, and SENDER_PASSWORD in .env.\n")
        logger.error("Failed to send test email to %s", recipient)
        return 1


# ── Argument Parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the top-level CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="DSA Problems Daily Emailer — Command Line Interface",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        title="Subcommands",
        description="Available operations for the DSA Problems Daily Emailer",
        help="Subcommand to execute",
    )

    # daily — Send the daily 4 problems email
    subparsers.add_parser(
        "daily",
        help="Send the daily 4 problems email",
        description="Send the daily 4 problems email to the configured recipient.",
    )

    # weekly — Send the weekly progress report
    subparsers.add_parser(
        "weekly",
        help="Send the weekly progress report",
        description="Send the weekly progress report with statistics and insights.",
    )

    # refresh — Refresh the problem cache from all sources
    subparsers.add_parser(
        "refresh",
        help="Refresh the problem cache from all sources",
        description="Fetch problems from all sources, merge, deduplicate, and update cache.",
    )

    # stats — Print current progress statistics
    subparsers.add_parser(
        "stats",
        help="Print current progress statistics",
        description="Display overall user progress, difficulty distribution, and streak metrics.",
    )

    # test-email — Send a test email to verify SMTP setup
    test_parser = subparsers.add_parser(
        "test-email",
        help="Send a test email to verify SMTP setup",
        description="Send a verification email via SMTP to verify configuration and connectivity.",
    )
    test_parser.add_argument(
        "--to",
        dest="recipient",
        default=None,
        help="Recipient email address override (defaults to RECIPIENT_EMAIL in config)",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main CLI entry point function."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "daily":
        return handle_daily()
    elif args.command == "weekly":
        return handle_weekly()
    elif args.command == "refresh":
        return handle_refresh()
    elif args.command == "stats":
        return handle_stats()
    elif args.command == "test-email":
        return handle_test_email(recipient_override=getattr(args, "recipient", None))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
