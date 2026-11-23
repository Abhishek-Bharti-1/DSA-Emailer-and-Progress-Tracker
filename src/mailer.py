"""
SMTP Email Delivery Module for DSA Problems Daily Emailer.

Handles composing and sending multipart HTML emails with plain text fallbacks
via SMTP with STARTTLS (configured for Gmail or other standard SMTP providers).
"""

import html
import logging
import os
import re
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Attempt to load SMTP defaults from the project configuration module
try:
    import config
    SMTP_SERVER = getattr(config, "SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(getattr(config, "SMTP_PORT", 587))
    SENDER_EMAIL = getattr(config, "SENDER_EMAIL", "")
    SENDER_PASSWORD = getattr(config, "SENDER_PASSWORD", "")
except Exception:
    # If not found directly, ensure root directory is in sys.path
    root_dir = Path(__file__).resolve().parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    try:
        import config
        SMTP_SERVER = getattr(config, "SMTP_SERVER", "smtp.gmail.com")
        SMTP_PORT = int(getattr(config, "SMTP_PORT", 587))
        SENDER_EMAIL = getattr(config, "SENDER_EMAIL", "")
        SENDER_PASSWORD = getattr(config, "SENDER_PASSWORD", "")
    except Exception:
        config = None
        SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
        SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")


class _HTMLToPlainTextParser(HTMLParser):
    """
    HTML parser that extracts clean plain text while preserving hyperlinks.

    Transforms hyperlinks into 'Text (URL)' format, ignores script/style blocks,
    and structures headings, paragraphs, and list items with readable line breaks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._current_href: Optional[str] = None
        self._current_link_text: list[str] = []
        self._ignore_tags = {"style", "script", "title"}
        self._in_ignore = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in self._ignore_tags:
            self._in_ignore += 1
            return
        if self._in_ignore > 0:
            return

        if tag_lower in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "article", "section", "header", "footer"):
            self._pieces.append("\n")
        elif tag_lower == "br":
            self._pieces.append("\n")
        elif tag_lower == "li":
            self._pieces.append("\n- ")
        elif tag_lower == "hr":
            self._pieces.append("\n---\n")
        elif tag_lower in ("td", "th"):
            self._pieces.append(" ")
        elif tag_lower == "a":
            attrs_dict = dict(attrs)
            href = (attrs_dict.get("href") or "").strip()
            # Retain non-anchor/non-javascript links
            if href and not href.startswith(("#", "javascript:")):
                self._current_href = href
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self._ignore_tags:
            self._in_ignore = max(0, self._in_ignore - 1)
            return
        if self._in_ignore > 0:
            return

        if tag_lower == "a" and self._current_href is not None:
            raw_text = "".join(self._current_link_text).strip()
            link_text = " ".join(raw_text.split())
            href = self._current_href
            if link_text:
                if link_text == href or href in link_text:
                    self._pieces.append(link_text)
                else:
                    self._pieces.append(f"{link_text} ({href})")
            else:
                self._pieces.append(href)
            self._current_href = None
            self._current_link_text = []
        elif tag_lower in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "article", "section", "header", "footer"):
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_ignore > 0:
            return
        if self._current_href is not None:
            self._current_link_text.append(data)
        else:
            self._pieces.append(data)

    def get_text(self) -> str:
        # Flush any unclosed anchor link
        if self._current_href is not None:
            raw_text = "".join(self._current_link_text).strip()
            link_text = " ".join(raw_text.split())
            href = self._current_href
            if link_text:
                if link_text == href or href in link_text:
                    self._pieces.append(link_text)
                else:
                    self._pieces.append(f"{link_text} ({href})")
            else:
                self._pieces.append(href)
            self._current_href = None
            self._current_link_text = []

        raw_text = "".join(self._pieces)
        text = html.unescape(raw_text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in text.split("\n")]
        cleaned_lines = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank:
                    cleaned_lines.append("")
                    prev_blank = True
            else:
                cleaned_lines.append(line)
                prev_blank = False
        return "\n".join(cleaned_lines).strip()


def _html_to_plaintext(html: str) -> str:
    """
    Extract plain text content from HTML, keeping problem titles and URLs.

    Strips HTML markup while preserving text and formatting URLs into
    readable 'Title (URL)' representations suitable as an email fallback.

    Args:
        html: The raw HTML content string.

    Returns:
        A cleaned, human-readable plain text string.
    """
    if not html or not isinstance(html, str):
        return ""
    try:
        parser = _HTMLToPlainTextParser()
        parser.feed(html)
        parser.close()
        return parser.get_text()
    except Exception as exc:
        logger.warning("HTML parser error in _html_to_plaintext: %s; using regex fallback", exc)
        # Fallback using regular expressions if parser encounters unexpected issues
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
        text = re.sub(r'(?i)<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r"\2 (\1)", text)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</?(?:p|div|h[1-6]|li|tr)[^>]*>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)


def send_email(
    recipient: str,
    subject: str,
    html_body: str,
    sender_email: Optional[str] = None,
    sender_password: Optional[str] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[int] = None,
) -> bool:
    """
    Send an email via SMTP using STARTTLS.

    Constructs a multipart/alternative message with a plain text fallback
    and an HTML body, setting standard email headers, and safely communicates
    with the configured SMTP server (defaulting to Gmail).

    Args:
        recipient: The recipient's email address.
        subject: The email subject line.
        html_body: The HTML body content of the email.
        sender_email: Optional override for sender email. Defaults to config.SENDER_EMAIL.
        sender_password: Optional override for sender password/app password. Defaults to config.SENDER_PASSWORD.
        smtp_server: Optional override for SMTP server hostname. Defaults to config.SMTP_SERVER.
        smtp_port: Optional override for SMTP server port. Defaults to config.SMTP_PORT.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    # Resolve configuration defaults with runtime overrides
    actual_sender = sender_email if (sender_email is not None and sender_email.strip()) else (
        getattr(config, "SENDER_EMAIL", SENDER_EMAIL) if config else SENDER_EMAIL
    )
    actual_password = sender_password if sender_password is not None else (
        getattr(config, "SENDER_PASSWORD", SENDER_PASSWORD) if config else SENDER_PASSWORD
    )
    actual_server = smtp_server if (smtp_server is not None and smtp_server.strip()) else (
        getattr(config, "SMTP_SERVER", SMTP_SERVER) if config else SMTP_SERVER
    )
    raw_port = smtp_port if smtp_port is not None else (
        getattr(config, "SMTP_PORT", SMTP_PORT) if config else SMTP_PORT
    )
    try:
        actual_port = int(raw_port)
    except (ValueError, TypeError):
        actual_port = 587

    # Validate essential arguments
    if not recipient or not recipient.strip():
        logger.error("Failed to send email: recipient address is empty.")
        return False
    recipient = recipient.strip().replace("\ufeff", "")

    if not actual_sender or not actual_sender.strip():
        logger.error("Failed to send email: sender email is not configured.")
        return False
    actual_sender = actual_sender.strip().replace("\ufeff", "")

    if actual_password:
        actual_password = str(actual_password).strip().replace("\ufeff", "")

    if actual_server.lower() == "smtp.gmail.com" and actual_password:
        gmail_app_password = "".join(actual_password.split())
        if len(gmail_app_password) != 16:
            logger.error(
                "Gmail SMTP authentication requires a 16-character app password "
                "(generate one in Google Account Security settings)."
            )
            return False
        actual_password = gmail_app_password

    try:
        # Build multipart/alternative message
        msg = MIMEMultipart("alternative")
        msg["From"] = actual_sender
        msg["To"] = recipient.strip()
        msg["Subject"] = subject
        # Ensure MIME-Version header is explicitly set
        if "MIME-Version" not in msg:
            msg["MIME-Version"] = "1.0"

        # Generate plain text fallback (strips HTML and preserves titles and URLs)
        plain_text = _html_to_plaintext(html_body or "")

        # Attach plain text fallback first, then HTML alternative
        part_text = MIMEText(plain_text, "plain", "utf-8")
        part_html = MIMEText(html_body or "", "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        # Connect to SMTP server with STARTTLS on configured port (default 587)
        with smtplib.SMTP(actual_server, actual_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if actual_password:
                server.login(actual_sender, actual_password)
            else:
                logger.warning("No sender password provided; attempting to send without authentication.")
            server.send_message(msg)

        logger.info("Email successfully sent to %s with subject: '%s'", recipient.strip(), subject)
        return True

    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP authentication failed for %s: %s", actual_sender, exc)
        return False
    except smtplib.SMTPConnectError as exc:
        logger.error("Failed to connect to SMTP server %s:%s: %s", actual_server, actual_port, exc)
        return False
    except smtplib.SMTPServerDisconnected as exc:
        logger.error("SMTP server %s:%s disconnected unexpectedly: %s", actual_server, actual_port, exc)
        return False
    except smtplib.SMTPResponseException as exc:
        logger.error("SMTP response error (code %s): %s", exc.smtp_code, exc.smtp_error)
        return False
    except smtplib.SMTPException as exc:
        logger.error("SMTP error sending email to %s: %s", recipient, exc)
        return False
    except (OSError, TimeoutError) as exc:
        logger.error(
            "Network error sending email to %s via %s:%s: %s",
            recipient,
            actual_server,
            actual_port,
            exc,
        )
        return False
    except Exception as exc:
        logger.error("Unexpected error sending email to %s: %s", recipient, exc, exc_info=True)
        return False
