"""
DSA Problems Daily Emailer — Gemini AI Orchestrator Agent.

Orchestrates daily DSA problem curation, selection, email dispatch, logging,
and weekly progress reporting using Google Gemini Function Calling (`google-genai` SDK).
Provides robust direct Python fallback routines when AI services are unavailable.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

# Ensure project root directory is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Project module imports
import config
from src.state import StateManager
from src.selector import select_daily_problems, get_selection_stats
from src.email_builder import build_daily_email, build_weekly_email
from src.mailer import send_email
from src.fetchers import (
    fetch_a2z_problems,
    fetch_leetcode_problems,
    fetch_codeforces_problems,
    fetch_gfg_problems,
)

# Google GenAI SDK import with defensive fallback if package is not yet installed
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Module-level session state to safely bridge consecutive tool calls
_last_selected_problems: list[dict[str, Any]] = []
_last_email_sent: bool = False
_last_logged_sent: bool = False
_last_weekly_sent: bool = False


# ── AI Agent Tool Functions ───────────────────────────────────────────────────

def tool_fetch_problems(source: str = "a2z_sheet") -> str:
    """Fetch problems from a source: a2z_sheet, leetcode, codeforces, gfg. Returns count of problems fetched."""
    source_lower = str(source).strip().lower()
    logger.info("tool_fetch_problems called with source='%s'", source)

    fetcher_fn = None
    norm_source = "a2z_sheet"

    if "a2z" in source_lower or "striver" in source_lower:
        fetcher_fn = fetch_a2z_problems
        norm_source = "a2z_sheet"
    elif "leetcode" in source_lower:
        fetcher_fn = fetch_leetcode_problems
        norm_source = "leetcode"
    elif "codeforces" in source_lower:
        fetcher_fn = fetch_codeforces_problems
        norm_source = "codeforces"
    elif "gfg" in source_lower or "geeks" in source_lower:
        fetcher_fn = fetch_gfg_problems
        norm_source = "gfg"
    elif source_lower in ("all", "all_sources"):
        fetcher_fn = None
        norm_source = "all"
    else:
        logger.warning("Unrecognized source '%s'; defaulting to a2z_sheet", source)
        fetcher_fn = fetch_a2z_problems
        norm_source = "a2z_sheet"

    state_mgr = StateManager()
    cache = state_mgr.load_cache() or []
    existing_ids = {str(p.get("id")) for p in cache if p.get("id")}

    fetched_problems: list[dict[str, Any]] = []
    try:
        if norm_source == "all":
            for fn in (fetch_a2z_problems, fetch_leetcode_problems, fetch_gfg_problems, fetch_codeforces_problems):
                try:
                    probs = fn()
                    if probs:
                        fetched_problems.extend(probs)
                except Exception as exc:
                    logger.warning("Fetcher %s failed: %s", fn.__name__, exc)
        else:
            if fetcher_fn is not None:
                fetched_problems = fetcher_fn() or []
    except Exception as exc:
        logger.error("Failed fetching from source %s: %s", norm_source, exc, exc_info=True)
        return f"Failed to fetch problems from {source}: {exc}"

    newly_added = 0
    for p in fetched_problems:
        pid = str(p.get("id", "")).strip()
        if pid and pid not in existing_ids:
            cache.append(p)
            existing_ids.add(pid)
            newly_added += 1

    if newly_added > 0 or not state_mgr.cache_path.exists():
        state_mgr.save_cache(cache)

    result_msg = (
        f"Fetched {len(fetched_problems)} problems from {norm_source}. "
        f"Added {newly_added} new problems to cache (Total cached: {len(cache)})."
    )
    logger.info(result_msg)
    return result_msg


def tool_get_selection_stats() -> str:
    """Get statistics about available/sent problems. Returns JSON with counts."""
    logger.info("tool_get_selection_stats called")
    state_mgr = StateManager()
    cache = state_mgr.load_cache() or []
    sent_ids = state_mgr.get_sent_ids()
    stats = get_selection_stats(cache, sent_ids)
    return json.dumps(stats, indent=2)


def tool_select_daily_problems() -> str:
    """Select 4 problems for today (1 Easy, 2 Medium, 1 Hard, all different topics). Returns JSON array of selected problems."""
    global _last_selected_problems
    logger.info("tool_select_daily_problems called")
    state_mgr = StateManager()
    cache = state_mgr.load_cache() or []

    # If cache is empty, attempt to populate from fallback file or fetcher
    if not cache:
        logger.warning("Cache is empty during selection. Checking fallback file.")
        fallback_file = getattr(config, "A2Z_FALLBACK_FILE", None)
        if fallback_file and Path(fallback_file).exists():
            try:
                with open(fallback_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if cache:
                    state_mgr.save_cache(cache)
                    logger.info("Populated cache from fallback file (%d problems)", len(cache))
            except Exception as exc:
                logger.error("Failed loading fallback file %s: %s", fallback_file, exc)

        if not cache:
            try:
                cache = fetch_a2z_problems() or []
                if cache:
                    state_mgr.save_cache(cache)
                    logger.info("Populated cache from live fetcher (%d problems)", len(cache))
            except Exception as exc:
                logger.error("Failed fetching A2Z problems: %s", exc)

    sent_ids = state_mgr.get_sent_ids()
    progress = state_mgr.get_progress()
    a2z_total = progress.get("a2z_total", 455)

    selected = select_daily_problems(
        all_problems=cache,
        sent_ids=sent_ids,
        a2z_total=a2z_total,
    )

    _last_selected_problems = selected
    titles = [p.get("title", "Untitled") for p in selected]
    logger.info("Selected %d daily problems: %s", len(selected), titles)
    return json.dumps(selected, indent=2)


def tool_send_daily_email(problems_json: str = "") -> str:
    """Send the daily email with the given problems. Input is JSON array of problem dicts. Returns success/failure."""
    global _last_selected_problems, _last_email_sent
    logger.info("tool_send_daily_email called")

    problems: list[dict[str, Any]] = []
    if isinstance(problems_json, list):
        problems = problems_json
    elif isinstance(problems_json, str) and problems_json.strip():
        try:
            problems = json.loads(problems_json)
        except Exception as exc:
            logger.warning("Could not parse problems_json directly: %s. Checking last selected problems.", exc)

    if not problems and _last_selected_problems:
        logger.info("Using cached _last_selected_problems (%d problems)", len(_last_selected_problems))
        problems = _last_selected_problems

    if not problems:
        _last_email_sent = False
        return "Failure: No problems provided or available to send."

    recipient = getattr(config, "RECIPIENT_EMAIL", "") or os.getenv("RECIPIENT_EMAIL", "")
    if not recipient:
        _last_email_sent = False
        return "Failure: RECIPIENT_EMAIL is not configured."

    state_mgr = StateManager()
    stats = state_mgr.get_progress()

    try:
        subject, html_body = build_daily_email(problems=problems, stats=stats)
        sent = send_email(recipient=recipient, subject=subject, html_body=html_body)
        if sent:
            _last_email_sent = True
            logger.info("Daily email successfully sent to %s", recipient)
            return f"Success: Daily email sent successfully to {recipient} with {len(problems)} problems."
        else:
            _last_email_sent = False
            logger.error("send_email returned False during tool_send_daily_email")
            return "Failure: SMTP server failed to deliver daily email."
    except Exception as exc:
        _last_email_sent = False
        logger.error("Exception in tool_send_daily_email: %s", exc, exc_info=True)
        return f"Failure: Exception during email delivery: {exc}"


def tool_log_sent(problems_json: str = "") -> str:
    """Log the sent problems to the state file. Input is JSON array of problem dicts. Returns confirmation."""
    global _last_selected_problems, _last_logged_sent
    logger.info("tool_log_sent called")

    problems: list[dict[str, Any]] = []
    if isinstance(problems_json, list):
        problems = problems_json
    elif isinstance(problems_json, str) and problems_json.strip():
        try:
            problems = json.loads(problems_json)
        except Exception as exc:
            logger.warning("Could not parse problems_json in tool_log_sent: %s", exc)

    if not problems and _last_selected_problems:
        logger.info("Using cached _last_selected_problems for logging (%d problems)", len(_last_selected_problems))
        problems = _last_selected_problems

    if not problems:
        return "Warning: No problems provided to log."

    try:
        state_mgr = StateManager()
        state_mgr.mark_sent(problems)
        _last_logged_sent = True
        return f"Confirmation: Successfully logged {len(problems)} problem(s) as sent."
    except Exception as exc:
        logger.error("Exception in tool_log_sent: %s", exc, exc_info=True)
        return f"Failure: Could not log sent problems: {exc}"


def tool_get_progress() -> str:
    """Get overall progress stats for reporting. Returns JSON with stats."""
    logger.info("tool_get_progress called")
    state_mgr = StateManager()
    progress = state_mgr.get_progress()
    weekly_stats = state_mgr.get_weekly_stats(weeks_back=1)
    combined = {**progress, **weekly_stats}
    return json.dumps(combined, indent=2)


def tool_generate_weekly_report() -> str:
    """Generate and send the weekly progress report with AI insights. Returns success/failure."""
    global _last_weekly_sent
    logger.info("tool_generate_weekly_report called")

    recipient = getattr(config, "RECIPIENT_EMAIL", "") or os.getenv("RECIPIENT_EMAIL", "")
    if not recipient:
        _last_weekly_sent = False
        return "Failure: RECIPIENT_EMAIL is not configured."

    state_mgr = StateManager()
    weekly_stats = state_mgr.get_weekly_stats(weeks_back=1)
    progress = state_mgr.get_progress()
    merged_stats = {**progress, **weekly_stats}

    ai_insights = _generate_ai_weekly_insights(merged_stats)

    try:
        subject, html_body = build_weekly_email(stats=merged_stats, ai_insights=ai_insights)
        sent = send_email(recipient=recipient, subject=subject, html_body=html_body)
        if sent:
            _last_weekly_sent = True
            logger.info("Weekly report successfully sent to %s", recipient)
            return f"Success: Weekly progress report sent successfully to {recipient}."
        else:
            _last_weekly_sent = False
            logger.error("send_email returned False for weekly report")
            return "Failure: SMTP server failed to deliver weekly report email."
    except Exception as exc:
        _last_weekly_sent = False
        logger.error("Exception in tool_generate_weekly_report: %s", exc, exc_info=True)
        return f"Failure: Exception generating weekly report: {exc}"


# Map function call names to actual Python functions
TOOL_MAP: dict[str, Any] = {
    "tool_fetch_problems": tool_fetch_problems,
    "tool_get_selection_stats": tool_get_selection_stats,
    "tool_select_daily_problems": tool_select_daily_problems,
    "tool_send_daily_email": tool_send_daily_email,
    "tool_log_sent": tool_log_sent,
    "tool_get_progress": tool_get_progress,
    "tool_generate_weekly_report": tool_generate_weekly_report,
}


def _generate_ai_weekly_insights(stats: dict[str, Any]) -> str:
    """Generate concise AI coaching insights for the weekly report using Gemini."""
    default_insights = (
        "**Consistency Wins**:\n"
        "- Great job practicing this week! Regular problem solving strengthens fundamental patterns.\n"
        "- Continue focusing on topics with fewer solved problems to build comprehensive mastery."
    )

    api_key = getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if genai is None or not api_key:
        return default_insights

    try:
        client = genai.Client(api_key=api_key)
        model_name = getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")
        prompt = (
            f"You are an encouraging and strategic DSA mentor reviewing a student's weekly progress.\n"
            f"Here are their statistics for the week:\n{json.dumps(stats, indent=2)}\n\n"
            f"Write a concise weekly review (2-3 short bullet points) highlighting their progress, "
            f"topics covered, streak, and recommended areas of focus for next week. "
            f"Use markdown bolding like **Key Takeaway**."
        )
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            ) if types is not None else None,
        )
        if response and response.text:
            return response.text.strip()
    except Exception as exc:
        logger.warning("Failed to generate Gemini AI insights: %s; using default.", exc)

    return default_insights


# ── Main Agent Functions ──────────────────────────────────────────────────────

def run_daily_agent() -> bool:
    """Run the AI agent for daily problem selection and emailing. Returns True on success."""
    global _last_selected_problems, _last_email_sent, _last_logged_sent
    _last_selected_problems = []
    _last_email_sent = False
    _last_logged_sent = False

    logger.info("Initiating run_daily_agent...")

    api_key = getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("Cannot run daily agent: GEMINI_API_KEY is not configured.")
        return False

    if genai is None or types is None:
        logger.error("Cannot run daily agent: google-genai SDK is not installed.")
        return False

    try:
        # 1. Set up Gemini client with function calling tools
        client = genai.Client(api_key=api_key)
        model_name = getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")

        # 2. System prompt
        system_prompt = (
            "You are a DSA problem curator agent. Your job today is to:\n"
            "1. Check if the problem cache needs refreshing (fetch if cache is empty or stale)\n"
            "2. Select 4 DSA problems (1 Easy, 2 Medium, 1 Hard, all different topics)\n"
            "3. Send the daily email\n"
            "4. Log the sent problems\n"
            "Call the tools in this order and report the result."
        )

        daily_tools = [
            tool_fetch_problems,
            tool_get_selection_stats,
            tool_select_daily_problems,
            tool_send_daily_email,
            tool_log_sent,
        ]

        contents: list[Any] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=system_prompt)],
            )
        ]

        # 3. Run the agentic loop (while response has function_calls, execute and feed back)
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info("Daily agent turn %d executing...", iteration)

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=daily_tools,
                    temperature=0.2,
                ),
            )

            function_calls = getattr(response, "function_calls", None)
            if not function_calls:
                logger.info(
                    "Daily agent loop ended without function calls. Output: %s",
                    getattr(response, "text", ""),
                )
                break

            # Append model's response candidate content to history
            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            # Handle multiple function calls per response
            func_response_parts: list[Any] = []
            for call in function_calls:
                call_name = getattr(call, "name", "")
                raw_args = getattr(call, "args", {})
                call_args = dict(raw_args) if raw_args else {}

                logger.info("Executing function call '%s' with args %s", call_name, call_args)

                tool_fn = TOOL_MAP.get(call_name)
                if tool_fn is None:
                    tool_result = f"Error: Tool '{call_name}' is not recognized."
                    logger.error(tool_result)
                else:
                    try:
                        sig = inspect.signature(tool_fn)
                        filtered_args = {}
                        for p in sig.parameters.values():
                            if p.name in call_args:
                                filtered_args[p.name] = call_args[p.name]
                            elif p.name == "problems_json" and "problems" in call_args:
                                filtered_args["problems_json"] = call_args["problems"]
                            elif p.name == "source" and "source" not in call_args:
                                filtered_args["source"] = "a2z_sheet"

                        tool_result = tool_fn(**filtered_args)
                    except Exception as exc:
                        logger.error("Exception in tool %s: %s", call_name, exc, exc_info=True)
                        tool_result = f"Error: Tool '{call_name}' raised exception: {exc}"

                func_response_parts.append(
                    types.Part.from_function_response(
                        name=call_name,
                        response={"result": str(tool_result)},
                    )
                )

            # Feed function responses back to the model as user content
            contents.append(
                types.Content(
                    role="user",
                    parts=func_response_parts,
                )
            )

        # 4. Return success/failure
        if _last_email_sent:
            if not _last_logged_sent and _last_selected_problems:
                logger.info("Logging sent problems as safety precaution.")
                StateManager().mark_sent(_last_selected_problems)
            logger.info("run_daily_agent completed successfully.")
            return True
        else:
            logger.warning("run_daily_agent completed, but daily email was not dispatched.")
            return False

    except Exception as exc:
        logger.error("Exception encountered in run_daily_agent: %s", exc, exc_info=True)
        return False


def run_weekly_agent() -> bool:
    """Run the AI agent for weekly report generation. Returns True on success."""
    global _last_weekly_sent
    _last_weekly_sent = False

    logger.info("Initiating run_weekly_agent...")

    api_key = getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("Cannot run weekly agent: GEMINI_API_KEY is not configured.")
        return False

    if genai is None or types is None:
        logger.error("Cannot run weekly agent: google-genai SDK is not installed.")
        return False

    try:
        client = genai.Client(api_key=api_key)
        model_name = getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")

        system_prompt = (
            "You are a DSA weekly progress reporting agent. Your job today is to:\n"
            "1. Check the student's progress and weekly statistics\n"
            "2. Generate and send the weekly progress report with AI insights\n"
            "Call the tools in this order and report the result."
        )

        weekly_tools = [
            tool_get_progress,
            tool_generate_weekly_report,
        ]

        contents: list[Any] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=system_prompt)],
            )
        ]

        max_iterations = 8
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info("Weekly agent turn %d executing...", iteration)

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=weekly_tools,
                    temperature=0.2,
                ),
            )

            function_calls = getattr(response, "function_calls", None)
            if not function_calls:
                logger.info(
                    "Weekly agent loop ended without function calls. Output: %s",
                    getattr(response, "text", ""),
                )
                break

            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            func_response_parts: list[Any] = []
            for call in function_calls:
                call_name = getattr(call, "name", "")
                raw_args = getattr(call, "args", {})
                call_args = dict(raw_args) if raw_args else {}

                logger.info("Executing weekly function call '%s' with args %s", call_name, call_args)

                tool_fn = TOOL_MAP.get(call_name)
                if tool_fn is None:
                    tool_result = f"Error: Tool '{call_name}' is not recognized."
                    logger.error(tool_result)
                else:
                    try:
                        sig = inspect.signature(tool_fn)
                        filtered_args = {p.name: call_args[p.name] for p in sig.parameters.values() if p.name in call_args}
                        tool_result = tool_fn(**filtered_args)
                    except Exception as exc:
                        logger.error("Exception in tool %s: %s", call_name, exc, exc_info=True)
                        tool_result = f"Error: Tool '{call_name}' raised exception: {exc}"

                func_response_parts.append(
                    types.Part.from_function_response(
                        name=call_name,
                        response={"result": str(tool_result)},
                    )
                )

            contents.append(
                types.Content(
                    role="user",
                    parts=func_response_parts,
                )
            )

        if _last_weekly_sent:
            logger.info("run_weekly_agent completed successfully.")
            return True
        else:
            logger.warning("run_weekly_agent completed, but weekly report was not dispatched.")
            return False

    except Exception as exc:
        logger.error("Exception encountered in run_weekly_agent: %s", exc, exc_info=True)
        return False


def run_daily_fallback() -> bool:
    """Direct Python fallback if the Gemini agent fails. No AI needed."""
    logger.info("Executing run_daily_fallback...")
    try:
        state_mgr = StateManager()

        # 1. Load cache (or fetch if empty)
        cache = state_mgr.load_cache()
        if not cache:
            logger.info("Cache is empty in daily fallback; checking fallback file.")
            fallback_file = getattr(config, "A2Z_FALLBACK_FILE", None)
            if fallback_file and Path(fallback_file).exists():
                try:
                    with open(fallback_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                    if cache:
                        state_mgr.save_cache(cache)
                        logger.info("Loaded %d problems from A2Z fallback file into cache.", len(cache))
                except Exception as exc:
                    logger.error("Failed loading fallback file %s: %s", fallback_file, exc)

            if not cache:
                try:
                    cache = fetch_a2z_problems() or []
                    if cache:
                        state_mgr.save_cache(cache)
                        logger.info("Fetched %d problems via fetch_a2z_problems into cache.", len(cache))
                except Exception as exc:
                    logger.error("Failed fetching A2Z problems in fallback: %s", exc)

        if not cache:
            logger.error("No problems available in cache or fallback data to select from.")
            return False

        # 2. Select problems using selector.py
        sent_ids = state_mgr.get_sent_ids()
        progress = state_mgr.get_progress()
        a2z_total = progress.get("a2z_total", 455)

        selected = select_daily_problems(
            all_problems=cache,
            sent_ids=sent_ids,
            a2z_total=a2z_total,
        )
        if not selected:
            logger.error("Failed to select daily problems from problem pool.")
            return False

        # 3. Build email using email_builder.py
        subject, html_body = build_daily_email(problems=selected, stats=progress)

        recipient = getattr(config, "RECIPIENT_EMAIL", "") or os.getenv("RECIPIENT_EMAIL", "")
        if not recipient:
            logger.error("RECIPIENT_EMAIL is not configured.")
            return False

        # 4. Send email using mailer.py
        sent = send_email(recipient=recipient, subject=subject, html_body=html_body)
        if not sent:
            logger.error("Failed to deliver daily email via SMTP mailer.")
            return False

        # 5. Log sent problems
        state_mgr.mark_sent(selected)
        logger.info("Daily fallback successfully delivered and logged %d problem(s).", len(selected))
        return True

    except Exception as exc:
        logger.error("Exception in run_daily_fallback: %s", exc, exc_info=True)
        return False


def run_weekly_fallback() -> bool:
    """Direct Python fallback for weekly report. No AI insights."""
    logger.info("Executing run_weekly_fallback...")
    try:
        state_mgr = StateManager()
        weekly_stats = state_mgr.get_weekly_stats(weeks_back=1)
        progress = state_mgr.get_progress()
        merged_stats = {**progress, **weekly_stats}

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
            logger.info("Weekly fallback progress report sent successfully to %s.", recipient)
            return True
        else:
            logger.error("Failed to deliver weekly progress report via SMTP mailer.")
            return False

    except Exception as exc:
        logger.error("Exception in run_weekly_fallback: %s", exc, exc_info=True)
        return False


__all__ = [
    "tool_fetch_problems",
    "tool_get_selection_stats",
    "tool_select_daily_problems",
    "tool_send_daily_email",
    "tool_log_sent",
    "tool_get_progress",
    "tool_generate_weekly_report",
    "run_daily_agent",
    "run_weekly_agent",
    "run_daily_fallback",
    "run_weekly_fallback",
]
