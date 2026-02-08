"""Markdown conversion utilities for Google Workspace data.

Converts Gmail threads, Calendar events, and Contacts into structured
markdown documents for storage in MinIO and processing by the ingestor.
"""

import base64
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("echomind-connector.google_markdown")


def gmail_thread_to_markdown(thread: dict[str, Any]) -> str:
    """Convert a Gmail thread (with messages) to a markdown document.

    Args:
        thread: Gmail API thread object with expanded messages.
            Expected structure: {"id": str, "messages": [...]}
            Each message has "payload" with headers and body.

    Returns:
        Markdown string representing the full thread.
    """
    messages = thread.get("messages", [])
    if not messages:
        return ""

    subject = _get_header(messages[0], "Subject") or "(No Subject)"
    parts: list[str] = [f"# {subject}\n"]

    for msg in messages:
        from_addr = _get_header(msg, "From") or "Unknown"
        to_addr = _get_header(msg, "To") or ""
        cc_addr = _get_header(msg, "Cc") or ""
        date_str = _get_header(msg, "Date") or ""

        parts.append(f"**From:** {from_addr}")
        if to_addr:
            parts.append(f"**To:** {to_addr}")
        if cc_addr:
            parts.append(f"**Cc:** {cc_addr}")
        if date_str:
            parts.append(f"**Date:** {date_str}")
        parts.append("")

        body = _extract_message_body(msg)
        if body:
            parts.append(body)

        # List attachments if present
        attachments = _list_attachments(msg)
        if attachments:
            parts.append("\n**Attachments:**")
            for att in attachments:
                parts.append(f"- {att}")

        parts.append("\n---\n")

    # Remove trailing separator
    if parts and parts[-1] == "\n---\n":
        parts.pop()

    return "\n".join(parts)


def calendar_event_to_markdown(event: dict[str, Any]) -> str:
    """Convert a Google Calendar event to a markdown document.

    Args:
        event: Calendar API event object.
            Expected fields: summary, start, end, location, organizer,
            attendees, description, status, htmlLink.

    Returns:
        Markdown string representing the event.
    """
    summary = event.get("summary", "(No Title)")
    parts: list[str] = [f"# {summary}\n"]

    # Date/time
    start = _format_event_time(event.get("start", {}))
    end = _format_event_time(event.get("end", {}))
    if start and end:
        parts.append(f"**When:** {start} — {end}")
    elif start:
        parts.append(f"**When:** {start}")

    # Location
    location = event.get("location")
    hangout_link = event.get("hangoutLink")
    if location and hangout_link:
        parts.append(f"**Where:** {location} / {hangout_link}")
    elif location:
        parts.append(f"**Where:** {location}")
    elif hangout_link:
        parts.append(f"**Where:** {hangout_link}")

    # Organizer
    organizer = event.get("organizer", {})
    organizer_str = organizer.get("displayName") or organizer.get("email")
    if organizer_str:
        parts.append(f"**Organizer:** {organizer_str}")

    # Attendees
    attendees = event.get("attendees", [])
    if attendees:
        attendee_strs = []
        for att in attendees:
            name = att.get("displayName") or att.get("email", "")
            status = att.get("responseStatus", "")
            if status and status != "needsAction":
                attendee_strs.append(f"{name} ({status})")
            else:
                attendee_strs.append(name)
        parts.append(f"**Attendees:** {', '.join(attendee_strs)}")

    # Status
    status = event.get("status")
    if status:
        parts.append(f"**Status:** {status}")

    # Recurrence
    recurrence = event.get("recurrence")
    if recurrence:
        parts.append(f"**Recurrence:** {', '.join(recurrence)}")

    # Description
    description = event.get("description")
    if description:
        parts.append(f"\n## Description\n\n{description}")

    return "\n".join(parts)


def contact_to_markdown(person: dict[str, Any]) -> str:
    """Convert a Google People API person resource to a markdown document.

    Args:
        person: People API person resource object.
            Expected fields: names, emailAddresses, phoneNumbers,
            organizations, addresses, birthdays, biographies.

    Returns:
        Markdown string representing the contact.
    """
    # Display name
    names = person.get("names", [])
    display_name = names[0].get("displayName", "Unknown") if names else "Unknown"
    parts: list[str] = [f"# {display_name}\n"]

    # Emails
    emails = person.get("emailAddresses", [])
    if emails:
        email_strs = []
        for e in emails:
            value = e.get("value", "")
            label = e.get("type", "")
            if label:
                email_strs.append(f"{value} ({label})")
            else:
                email_strs.append(value)
        parts.append(f"**Email:** {', '.join(email_strs)}")

    # Phone numbers
    phones = person.get("phoneNumbers", [])
    if phones:
        phone_strs = []
        for p in phones:
            value = p.get("value", "")
            label = p.get("type", "")
            if label:
                phone_strs.append(f"{value} ({label})")
            else:
                phone_strs.append(value)
        parts.append(f"**Phone:** {', '.join(phone_strs)}")

    # Organizations
    orgs = person.get("organizations", [])
    if orgs:
        org = orgs[0]
        org_parts = []
        if org.get("name"):
            org_parts.append(org["name"])
        if org.get("title"):
            org_parts.append(org["title"])
        if org_parts:
            parts.append(f"**Organization:** {' — '.join(org_parts)}")

    # Addresses
    addresses = person.get("addresses", [])
    if addresses:
        for addr in addresses:
            formatted = addr.get("formattedValue", "")
            label = addr.get("type", "")
            if formatted:
                if label:
                    parts.append(f"**Address ({label}):** {formatted}")
                else:
                    parts.append(f"**Address:** {formatted}")

    # Birthday
    birthdays = person.get("birthdays", [])
    if birthdays:
        bday = birthdays[0].get("date", {})
        month = bday.get("month")
        day = bday.get("day")
        year = bday.get("year")
        if month and day:
            try:
                date_obj = datetime(
                    year=year or 2000, month=month, day=day, tzinfo=timezone.utc
                )
                if year:
                    parts.append(f"**Birthday:** {date_obj.strftime('%B %d, %Y')}")
                else:
                    parts.append(f"**Birthday:** {date_obj.strftime('%B %d')}")
            except ValueError:
                pass

    # Biography / Notes
    bios = person.get("biographies", [])
    if bios:
        bio_text = bios[0].get("value", "")
        if bio_text:
            parts.append(f"\n## Notes\n\n{bio_text}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_header(message: dict[str, Any], name: str) -> str | None:
    """Extract a header value from a Gmail message.

    Args:
        message: Gmail API message object.
        name: Header name (case-insensitive match).

    Returns:
        Header value string, or None if not found.
    """
    headers = message.get("payload", {}).get("headers", [])
    name_lower = name.lower()
    for header in headers:
        if header.get("name", "").lower() == name_lower:
            return header.get("value")
    return None


def _extract_message_body(message: dict[str, Any]) -> str:
    """Extract plain text body from a Gmail message.

    Walks the MIME part tree to find text/plain content.
    Falls back to stripping HTML if only text/html is available.

    Args:
        message: Gmail API message object.

    Returns:
        Plain text body string, or empty string if none found.
    """
    payload = message.get("payload", {})

    # Simple message with body directly
    body_data = payload.get("body", {}).get("data")
    mime_type = payload.get("mimeType", "")

    if body_data and mime_type == "text/plain":
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    # Multipart message - walk parts
    parts = payload.get("parts", [])
    return _find_text_in_parts(parts)


def _find_text_in_parts(parts: list[dict[str, Any]]) -> str:
    """Recursively find text/plain content in MIME parts.

    Args:
        parts: List of MIME part objects from Gmail API.

    Returns:
        Decoded plain text string, or empty string if not found.
    """
    plain_text = ""
    html_text = ""

    for part in parts:
        mime_type = part.get("mimeType", "")

        # Recurse into nested multipart
        nested_parts = part.get("parts", [])
        if nested_parts:
            result = _find_text_in_parts(nested_parts)
            if result:
                return result

        body_data = part.get("body", {}).get("data")
        if not body_data:
            continue

        decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        if mime_type == "text/plain":
            plain_text = decoded
        elif mime_type == "text/html" and not html_text:
            html_text = decoded

    if plain_text:
        return plain_text

    # Fallback: strip HTML tags for a rough plaintext
    if html_text:
        return _strip_html(html_text)

    return ""


def _strip_html(html: str) -> str:
    """Rough HTML tag stripper for fallback text extraction.

    Args:
        html: HTML string.

    Returns:
        Text with HTML tags removed.
    """
    # Remove style and script blocks
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL)
    # Replace br and p tags with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(text: str, max_length: int = 80) -> str:
    """Convert text to a URL-friendly slug for filenames.

    Args:
        text: Input text.
        max_length: Maximum slug length.

    Returns:
        Slugified string.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:max_length].strip("-")


def _list_attachments(message: dict[str, Any]) -> list[str]:
    """List attachment filenames from a Gmail message.

    Args:
        message: Gmail API message object.

    Returns:
        List of attachment filename strings.
    """
    attachments: list[str] = []
    parts = message.get("payload", {}).get("parts", [])

    for part in parts:
        filename = part.get("filename")
        if filename:
            size = part.get("body", {}).get("size", 0)
            if size > 0:
                size_kb = size / 1024
                attachments.append(f"{filename} ({size_kb:.1f} KB)")
            else:
                attachments.append(filename)

    return attachments


def _format_event_time(time_obj: dict[str, Any]) -> str:
    """Format a Calendar API dateTime or date value.

    Args:
        time_obj: Calendar API time object with either "dateTime" or "date".

    Returns:
        Formatted time string, or empty string if no time data.
    """
    if not time_obj:
        return ""

    # All-day event
    if "date" in time_obj:
        return time_obj["date"]

    # Specific time
    date_time = time_obj.get("dateTime", "")
    if date_time:
        try:
            dt = datetime.fromisoformat(date_time)
            return dt.strftime("%Y-%m-%d %H:%M %Z").strip()
        except ValueError:
            return date_time

    return ""
