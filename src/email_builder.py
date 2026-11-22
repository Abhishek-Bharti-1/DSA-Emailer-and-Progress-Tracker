"""
Email builder for the DSA Problems Daily Emailer.

Constructs styled, responsive HTML emails for:
1. Daily DSA problems (clean, distraction-free, metadata-hidden)
2. Weekly DSA progress reports (stats summary, difficulty breakdown, A2Z progress, AI insights)
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Any, Optional

__all__ = ["build_daily_email", "build_weekly_email"]

# ── Color Palette & Theme Constants ──────────────────────────────────────────
# Dark navy primary background, white text, and vibrant red-pink accent color.
COLOR_BG_MAIN = "#1a1a2e"
COLOR_BG_CARD = "#16213e"
COLOR_BG_BAR_TRACK = "#222646"
COLOR_BORDER = "#282b4a"
COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_MUTED = "#a2a8d3"
COLOR_TEXT_BODY = "#dcdde1"
COLOR_ACCENT = "#e94560"

# Difficulty bar colors
COLOR_EASY = "#00b894"
COLOR_MEDIUM = "#f39c12"
COLOR_HARD = "#e94560"

# Typography
FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)


# ── Helper Functions ─────────────────────────────────────────────────────────

def _extract_day_number(stats: dict[str, Any]) -> int:
    """
    Extract or infer current day number from the stats dictionary.

    Checks 'day', then 'streak_days', then calculates from 'total_sent' (4 problems/day).
    Defaults to 1 if no valid value is found.
    """
    if not isinstance(stats, dict):
        return 1

    if stats.get("day") is not None:
        try:
            return max(1, int(stats["day"]))
        except (ValueError, TypeError):
            pass

    if stats.get("streak_days") is not None:
        try:
            return max(1, int(stats["streak_days"]))
        except (ValueError, TypeError):
            pass

    total = stats.get("total_sent")
    if total is not None:
        try:
            total_int = int(total)
            if total_int >= 4:
                return total_int // 4
            elif total_int > 0:
                return total_int
        except (ValueError, TypeError):
            pass

    return 1


def _render_progress_bar(percentage: float, fill_color: str, height: int = 10) -> str:
    """
    Render an email-client-safe horizontal progress bar using nested HTML tables.
    Works reliably across Outlook, Gmail, Apple Mail, and mobile clients.
    """
    clamped_pct = max(0.0, min(100.0, float(percentage)))
    rem_pct = round(100.0 - clamped_pct, 1)
    radius = max(3, height // 2)

    if clamped_pct <= 0.0:
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="background-color: {COLOR_BG_BAR_TRACK}; border-radius: {radius}px; '
            f'overflow: hidden; height: {height}px; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">'
            f'<tr><td style="background-color: {COLOR_BG_BAR_TRACK}; height: {height}px; '
            f'border-radius: {radius}px; font-size: 0; line-height: 0;">&nbsp;</td></tr>'
            f'</table>'
        )
    elif clamped_pct >= 100.0:
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="background-color: {COLOR_BG_BAR_TRACK}; border-radius: {radius}px; '
            f'overflow: hidden; height: {height}px; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">'
            f'<tr><td width="100%" bgcolor="{fill_color}" style="background-color: {fill_color}; '
            f'height: {height}px; border-radius: {radius}px; font-size: 0; line-height: 0;">&nbsp;</td></tr>'
            f'</table>'
        )
    else:
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="background-color: {COLOR_BG_BAR_TRACK}; border-radius: {radius}px; '
            f'overflow: hidden; height: {height}px; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">'
            f'<tr>'
            f'<td width="{clamped_pct:.1f}%" bgcolor="{fill_color}" '
            f'style="background-color: {fill_color}; height: {height}px; border-radius: {radius}px 0 0 {radius}px; '
            f'font-size: 0; line-height: 0;">&nbsp;</td>'
            f'<td width="{rem_pct:.1f}%" style="height: {height}px; font-size: 0; line-height: 0;">&nbsp;</td>'
            f'</tr>'
            f'</table>'
        )


def _format_ai_insights(insights: str) -> str:
    """
    Format raw AI insights text into email-safe HTML paragraphs and lists.
    Safely escapes HTML and formats bold markdown (**text**).
    """
    if not insights or not str(insights).strip():
        return (
            f'<p style="margin: 0; color: {COLOR_TEXT_MUTED}; font-size: 14px; line-height: 1.6;">'
            f'Consistent practice builds deep mastery. Keep solving daily to sharpen your problem-solving intuition!'
            f'</p>'
        )

    escaped = html.escape(str(insights).strip())
    # Format markdown bold **text** -> <strong>text</strong>
    bold_pattern = re.compile(r"\*\*(.+?)\*\*")
    escaped = bold_pattern.sub(r'<strong style="color: #ffffff;">\1</strong>', escaped)

    chunks = escaped.split("\n\n")
    html_sections: list[str] = []

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        # Check if all lines look like bullet points
        if lines and all(re.match(r"^[-*•]\s+", line) or re.match(r"^\d+\.\s+", line) for line in lines):
            list_items: list[str] = []
            for line in lines:
                cleaned_line = re.sub(r"^[-*•]\s+|\d+\.\s+", "", line)
                list_items.append(
                    f'<li style="margin-bottom: 6px; color: {COLOR_TEXT_BODY}; line-height: 1.5;">'
                    f'{cleaned_line}</li>'
                )
            html_sections.append(
                f'<ul style="margin: 8px 0 12px 0; padding-left: 20px; color: {COLOR_ACCENT};">'
                f'{"".join(list_items)}'
                f'</ul>'
            )
        else:
            p_content = "<br>".join(lines)
            html_sections.append(
                f'<p style="margin: 0 0 12px 0; font-size: 14px; line-height: 1.6; color: {COLOR_TEXT_BODY};">'
                f'{p_content}'
                f'</p>'
            )

    return "".join(html_sections)


# ── Daily Email Builder ──────────────────────────────────────────────────────

def build_daily_email(
    problems: list[dict[str, Any]],
    stats: dict[str, Any],
    current_date: Optional[datetime] = None,
) -> tuple[str, str]:
    """
    Build styled HTML email for daily DSA practice problems.

    Requirements:
    - Subject: "🧩 Daily DSA Practice — {Month Day, Year}"
    - Body:
      - Title: "🧩 Today's DSA Challenges"
      - Date in readable format
      - 4 problems listed as "Problem 1" through "Problem 4" showing ONLY:
        - Problem title
        - Clickable URL link
        - Note: Topic, difficulty, and source are intentionally HIDDEN
      - Footer: "Day {X} • {Y}/{Z} A2Z problems completed"
      - "Happy Coding! 🚀"
    - Inline CSS, dark navy (#1a1a2e) background, white text, accent #e94560
    - Responsive mobile-friendly design

    Args:
        problems: List of problem dictionaries (typically 4 problems).
        stats: Dictionary containing 'total_sent', 'a2z_sent', 'a2z_total', and optional 'day'.
        current_date: Optional datetime override (defaults to datetime.now()).

    Returns:
        tuple[str, str]: (subject, html_body)
    """
    if current_date is None:
        current_date = datetime.now()

    # Format dates
    date_subject = f"{current_date.strftime('%B')} {current_date.day}, {current_date.year}"
    subject = f"🧩 Daily DSA Practice — {date_subject}"
    readable_date = f"{current_date.strftime('%A, %B')} {current_date.day}, {current_date.year}"

    # Extract stats
    day_num = _extract_day_number(stats)
    a2z_sent = stats.get("a2z_sent", 0) if isinstance(stats, dict) else 0
    a2z_total = stats.get("a2z_total", 0) if isinstance(stats, dict) else 0

    # Build problem cards (ONLY Problem title & Clickable URL link; NO topic/difficulty/source)
    problem_cards: list[str] = []
    if problems:
        for idx, problem in enumerate(problems, 1):
            raw_title = (
                problem.get("title")
                or problem.get("problem_title")
                or problem.get("name")
                or f"Problem {idx}"
            )
            raw_url = problem.get("url") or problem.get("link") or "#"

            escaped_title = html.escape(str(raw_title).strip())
            escaped_url = html.escape(str(raw_url).strip())

            card_html = f"""
        <!-- Problem Card {idx} -->
        <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-left: 4px solid {COLOR_ACCENT}; border-radius: 12px; margin-bottom: 16px;">
          <tr>
            <td style="padding: 22px 24px;">
              <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; color: {COLOR_ACCENT}; margin-bottom: 10px;">
                Problem {idx}
              </div>
              <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; line-height: 1.4; color: {COLOR_TEXT_PRIMARY};">
                <a href="{escaped_url}" target="_blank" rel="noopener noreferrer" style="color: {COLOR_TEXT_PRIMARY}; text-decoration: none;">
                  {escaped_title}
                </a>
              </h2>
              <div>
                <a href="{escaped_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: {COLOR_ACCENT}; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; padding: 10px 22px; border-radius: 6px; letter-spacing: 0.3px;">
                  Solve Problem &rarr;
                </a>
              </div>
            </td>
          </tr>
        </table>"""
            problem_cards.append(card_html.strip())
    else:
        fallback_card = f"""
        <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px; margin-bottom: 16px;">
          <tr>
            <td style="padding: 24px; text-align: center; color: {COLOR_TEXT_MUTED}; font-size: 15px;">
              No problems scheduled for today. Check back tomorrow!
            </td>
          </tr>
        </table>"""
        problem_cards.append(fallback_card.strip())

    problems_markup = "\n".join(problem_cards)

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>🧩 Today's DSA Challenges</title>
  <!--[if mso]>
  <style type="text/css">
    body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
  </style>
  <![endif]-->
  <style type="text/css">
    body {{
      margin: 0;
      padding: 0;
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
      background-color: {COLOR_BG_MAIN};
    }}
    table {{
      border-collapse: separate;
    }}
    a, a:visited {{
      color: {COLOR_ACCENT};
    }}
    @media only screen and (max-width: 620px) {{
      .wrapper {{
        width: 100% !important;
        padding: 16px 12px !important;
      }}
      .card-body {{
        padding: 18px 16px !important;
      }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: {COLOR_BG_MAIN}; font-family: {FONT_STACK}; color: {COLOR_TEXT_PRIMARY}; -webkit-font-smoothing: antialiased;">
  <!-- Main Container -->
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_MAIN};">
    <tr>
      <td align="center" style="padding: 32px 16px;">
        <table width="100%" cellspacing="0" cellpadding="0" border="0" class="wrapper" style="max-width: 600px; margin: 0 auto; width: 100%;">
          
          <!-- Header Banner -->
          <tr>
            <td style="padding-bottom: 24px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 14px; overflow: hidden;">
                <tr>
                  <td align="center" style="padding: 30px 24px; text-align: center;">
                    <div style="display: inline-block; background-color: rgba(233, 69, 96, 0.15); border: 1px solid {COLOR_ACCENT}; border-radius: 20px; padding: 4px 14px; margin-bottom: 12px;">
                      <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: {COLOR_ACCENT};">Daily Challenge</span>
                    </div>
                    <h1 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; letter-spacing: -0.5px;">
                      🧩 Today's DSA Challenges
                    </h1>
                    <p style="margin: 0; font-size: 14px; color: {COLOR_TEXT_MUTED}; font-weight: 500;">
                      {readable_date}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Problems Section -->
          <tr>
            <td style="padding-bottom: 12px;">
              {problems_markup}
            </td>
          </tr>

          <!-- Footer Section -->
          <tr>
            <td style="padding-top: 12px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 14px;">
                <tr>
                  <td align="center" style="padding: 26px 24px; text-align: center;">
                    <p style="margin: 0 0 10px 0; font-size: 15px; font-weight: 600; color: {COLOR_ACCENT}; letter-spacing: 0.3px;">
                      Day {day_num} • {a2z_sent}/{a2z_total} A2Z problems completed
                    </p>
                    <p style="margin: 0; font-size: 17px; font-weight: 700; color: {COLOR_TEXT_PRIMARY};">
                      Happy Coding! 🚀
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, html_body


# ── Weekly Email Builder ─────────────────────────────────────────────────────

def build_weekly_email(
    stats: dict[str, Any],
    ai_insights: str,
    current_date: Optional[datetime] = None,
) -> tuple[str, str]:
    """
    Build styled HTML email for weekly DSA progress reports.

    Requirements:
    - Subject: "📊 Weekly DSA Progress — Week {N}"
    - Body:
      - Title: "📊 Your Weekly DSA Progress"
      - Week date range
      - This week's stats: problems sent, topics covered (list)
      - Difficulty breakdown with visual bars (Easy/Medium/Hard counts)
      - Overall A2Z progress with percentage bar
      - AI Insights section with the ai_insights text
      - "Keep going! 💪"
    - Inline CSS, dark navy (#1a1a2e) background, white text, accent #e94560
    - Responsive mobile-friendly design

    Args:
        stats: Dictionary containing:
            - 'problems_sent': int
            - 'topics_covered': list[str]
            - 'difficulty_breakdown': dict (e.g. {'Easy': 7, 'Medium': 14, 'Hard': 7})
            - 'total_sent': int
            - 'a2z_sent': int
            - 'a2z_total': int
            - 'streak_days': int
            - optional 'week': int
            - optional 'date_range': str
        ai_insights: String containing AI-generated review, insights, and recommendations.
        current_date: Optional datetime override (defaults to datetime.now()).

    Returns:
        tuple[str, str]: (subject, html_body)
    """
    if current_date is None:
        current_date = datetime.now()

    # Determine week number
    week_num = None
    if isinstance(stats, dict):
        week_num = stats.get("week") or stats.get("week_number")
    if not week_num:
        week_num = current_date.isocalendar()[1]

    subject = f"📊 Weekly DSA Progress — Week {week_num}"

    # Determine date range
    if isinstance(stats, dict) and stats.get("date_range"):
        date_range = str(stats["date_range"])
    elif isinstance(stats, dict) and stats.get("week_range"):
        date_range = str(stats["week_range"])
    else:
        start_date = current_date - timedelta(days=6)
        start_str = f"{start_date.strftime('%B')} {start_date.day}, {start_date.year}"
        end_str = f"{current_date.strftime('%B')} {current_date.day}, {current_date.year}"
        date_range = f"{start_str} – {end_str}"

    # Extract numerical stats
    problems_sent = stats.get("problems_sent", 0) if isinstance(stats, dict) else 0
    streak_days = stats.get("streak_days", 0) if isinstance(stats, dict) else 0
    total_sent = stats.get("total_sent", 0) if isinstance(stats, dict) else 0
    a2z_sent = stats.get("a2z_sent", 0) if isinstance(stats, dict) else 0
    a2z_total = stats.get("a2z_total", 0) if isinstance(stats, dict) else 0

    # Extract & format topics covered
    topics_raw = stats.get("topics_covered", []) if isinstance(stats, dict) else []
    if isinstance(topics_raw, str):
        topics_list = [t.strip() for t in topics_raw.split(",") if t.strip()]
    elif isinstance(topics_raw, (list, tuple, set)):
        topics_list = [str(t).strip() for t in topics_raw if str(t).strip()]
    else:
        topics_list = []

    if topics_list:
        topics_items = "".join(
            f'<li style="margin-bottom: 8px; font-size: 14px; color: {COLOR_TEXT_PRIMARY}; line-height: 1.5;">'
            f'{html.escape(topic)}'
            f'</li>'
            for topic in topics_list
        )
        topics_markup = f"""
        <ul style="margin: 0; padding-left: 20px; color: {COLOR_ACCENT};">
          {topics_items}
        </ul>"""
    else:
        topics_markup = (
            f'<p style="margin: 0; font-size: 14px; color: {COLOR_TEXT_MUTED}; font-style: italic;">'
            f'No topics recorded this week.'
            f'</p>'
        )

    # Difficulty breakdown
    diff_data = stats.get("difficulty_breakdown", {}) if isinstance(stats, dict) else {}
    easy_count = 0
    medium_count = 0
    hard_count = 0

    if isinstance(diff_data, dict):
        for k, v in diff_data.items():
            k_lower = str(k).strip().lower()
            try:
                cnt = int(v)
            except (ValueError, TypeError):
                cnt = 0
            if "easy" in k_lower:
                easy_count += cnt
            elif "med" in k_lower:
                medium_count += cnt
            elif "hard" in k_lower:
                hard_count += cnt

    diff_total = easy_count + medium_count + hard_count
    easy_pct = (easy_count / diff_total * 100.0) if diff_total > 0 else 0.0
    medium_pct = (medium_count / diff_total * 100.0) if diff_total > 0 else 0.0
    hard_pct = (hard_count / diff_total * 100.0) if diff_total > 0 else 0.0

    easy_bar_html = _render_progress_bar(easy_pct, COLOR_EASY, height=10)
    medium_bar_html = _render_progress_bar(medium_pct, COLOR_MEDIUM, height=10)
    hard_bar_html = _render_progress_bar(hard_pct, COLOR_HARD, height=10)

    # A2Z Overall progress
    a2z_pct = (a2z_sent / a2z_total * 100.0) if a2z_total > 0 else 0.0
    a2z_bar_html = _render_progress_bar(a2z_pct, COLOR_ACCENT, height=12)

    # AI Insights formatting
    insights_html = _format_ai_insights(ai_insights)

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>📊 Your Weekly DSA Progress</title>
  <!--[if mso]>
  <style type="text/css">
    body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
  </style>
  <![endif]-->
  <style type="text/css">
    body {{
      margin: 0;
      padding: 0;
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
      background-color: {COLOR_BG_MAIN};
    }}
    table {{
      border-collapse: separate;
    }}
    a, a:visited {{
      color: {COLOR_ACCENT};
    }}
    @media only screen and (max-width: 620px) {{
      .wrapper {{
        width: 100% !important;
        padding: 16px 12px !important;
      }}
      .stat-cell {{
        display: block !important;
        width: 100% !important;
        margin-bottom: 12px !important;
      }}
      .stat-spacer {{
        display: none !important;
      }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: {COLOR_BG_MAIN}; font-family: {FONT_STACK}; color: {COLOR_TEXT_PRIMARY}; -webkit-font-smoothing: antialiased;">
  <!-- Main Container -->
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_MAIN};">
    <tr>
      <td align="center" style="padding: 32px 16px;">
        <table width="100%" cellspacing="0" cellpadding="0" border="0" class="wrapper" style="max-width: 600px; margin: 0 auto; width: 100%;">

          <!-- Header Banner -->
          <tr>
            <td style="padding-bottom: 24px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 14px; overflow: hidden;">
                <tr>
                  <td align="center" style="padding: 30px 24px; text-align: center;">
                    <div style="display: inline-block; background-color: rgba(233, 69, 96, 0.15); border: 1px solid {COLOR_ACCENT}; border-radius: 20px; padding: 4px 14px; margin-bottom: 12px;">
                      <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: {COLOR_ACCENT};">Weekly Report &bull; Week {week_num}</span>
                    </div>
                    <h1 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; letter-spacing: -0.5px;">
                      📊 Your Weekly DSA Progress
                    </h1>
                    <p style="margin: 0; font-size: 14px; color: {COLOR_TEXT_MUTED}; font-weight: 500;">
                      {date_range}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Summary Metric Boxes -->
          <tr>
            <td style="padding-bottom: 24px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td width="32%" class="stat-cell" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px; padding: 18px 12px; text-align: center; vertical-align: top;">
                    <div style="font-size: 28px; font-weight: 700; color: {COLOR_ACCENT}; line-height: 1.2;">
                      {problems_sent}
                    </div>
                    <div style="font-size: 11px; color: {COLOR_TEXT_MUTED}; text-transform: uppercase; font-weight: 700; margin-top: 6px; letter-spacing: 0.8px;">
                      Problems Sent
                    </div>
                  </td>
                  <td width="2%" class="stat-spacer">&nbsp;</td>
                  <td width="32%" class="stat-cell" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px; padding: 18px 12px; text-align: center; vertical-align: top;">
                    <div style="font-size: 28px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; line-height: 1.2;">
                      {streak_days}
                    </div>
                    <div style="font-size: 11px; color: {COLOR_TEXT_MUTED}; text-transform: uppercase; font-weight: 700; margin-top: 6px; letter-spacing: 0.8px;">
                      Streak Days 🔥
                    </div>
                  </td>
                  <td width="2%" class="stat-spacer">&nbsp;</td>
                  <td width="32%" class="stat-cell" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px; padding: 18px 12px; text-align: center; vertical-align: top;">
                    <div style="font-size: 28px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; line-height: 1.2;">
                      {total_sent}
                    </div>
                    <div style="font-size: 11px; color: {COLOR_TEXT_MUTED}; text-transform: uppercase; font-weight: 700; margin-top: 6px; letter-spacing: 0.8px;">
                      Total Sent
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Topics Covered -->
          <tr>
            <td style="padding-bottom: 24px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px;">
                <tr>
                  <td style="padding: 22px 24px;">
                    <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: {COLOR_ACCENT}; margin-bottom: 14px;">
                      📚 Topics Covered ({len(topics_list)})
                    </div>
                    {topics_markup}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Difficulty Breakdown -->
          <tr>
            <td style="padding-bottom: 24px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px;">
                <tr>
                  <td style="padding: 22px 24px;">
                    <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: {COLOR_ACCENT}; margin-bottom: 18px;">
                      🎯 Difficulty Breakdown
                    </div>

                    <!-- Easy Bar -->
                    <div style="margin-bottom: 16px;">
                      <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 6px;">
                        <tr>
                          <td align="left" style="font-size: 14px; font-weight: 600; color: {COLOR_EASY};">
                            Easy
                          </td>
                          <td align="right" style="font-size: 13px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};">
                            {easy_count} ({easy_pct:.1f}%)
                          </td>
                        </tr>
                      </table>
                      {easy_bar_html}
                    </div>

                    <!-- Medium Bar -->
                    <div style="margin-bottom: 16px;">
                      <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 6px;">
                        <tr>
                          <td align="left" style="font-size: 14px; font-weight: 600; color: {COLOR_MEDIUM};">
                            Medium
                          </td>
                          <td align="right" style="font-size: 13px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};">
                            {medium_count} ({medium_pct:.1f}%)
                          </td>
                        </tr>
                      </table>
                      {medium_bar_html}
                    </div>

                    <!-- Hard Bar -->
                    <div>
                      <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 6px;">
                        <tr>
                          <td align="left" style="font-size: 14px; font-weight: 600; color: {COLOR_HARD};">
                            Hard
                          </td>
                          <td align="right" style="font-size: 13px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};">
                            {hard_count} ({hard_pct:.1f}%)
                          </td>
                        </tr>
                      </table>
                      {hard_bar_html}
                    </div>

                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Overall A2Z Progress -->
          <tr>
            <td style="padding-bottom: 24px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 12px;">
                <tr>
                  <td style="padding: 22px 24px;">
                    <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: {COLOR_ACCENT}; margin-bottom: 14px;">
                      🚀 Overall A2Z Progress
                    </div>
                    <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 10px;">
                      <tr>
                        <td align="left" style="font-size: 14px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};">
                          Striver's A2Z Sheet
                        </td>
                        <td align="right" style="font-size: 14px; font-weight: 700; color: {COLOR_ACCENT};">
                          {a2z_sent}/{a2z_total} ({a2z_pct:.1f}%)
                        </td>
                      </tr>
                    </table>
                    {a2z_bar_html}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- AI Insights Section -->
          <tr>
            <td style="padding-bottom: 24px;">
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-left: 4px solid {COLOR_ACCENT}; border-radius: 12px;">
                <tr>
                  <td style="padding: 22px 24px;">
                    <div style="font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: {COLOR_ACCENT}; margin-bottom: 14px;">
                      🤖 AI Insights & Recommendations
                    </div>
                    <div>
                      {insights_html}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer Section -->
          <tr>
            <td>
              <table width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLOR_BG_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 14px;">
                <tr>
                  <td align="center" style="padding: 26px 24px; text-align: center;">
                    <p style="margin: 0; font-size: 18px; font-weight: 700; color: {COLOR_TEXT_PRIMARY};">
                      Keep going! 💪
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, html_body
