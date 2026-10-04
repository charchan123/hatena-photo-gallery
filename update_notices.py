"""Presentation-only update notices; never infer additions or identifications."""

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import warnings


NOTICE_DAYS = {"new": 7, "update": 7, "identified": 14}
NOTICE_LABELS = {"new": "NEW!", "update": "UPDATE!", "identified": "IDENTIFIED!"}
NOTICE_DESCRIPTIONS = {"new": "新しく公開", "update": "内容を更新", "identified": "正体が判明"}
SECTIONS = {"guide", "season", "features", "research", "best-shots", "about", "daily", "links"}
CONFIG_PATH = Path(__file__).parent / "data" / "update-notices.json"


def validate_notice_config(data):
    """Validate the shared editorial event contract and return its event list."""
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("events"), list):
        raise ValueError("expected version 1 and an events list")
    events = data["events"]
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        if set(event) != {"section", "kind", "summary", "occurred_at"}:
            raise ValueError("event has invalid fields")
        if event.get("section") not in SECTIONS or event.get("kind") not in NOTICE_DAYS:
            raise ValueError("unknown notice section or kind")
        if timestamp(event.get("occurred_at")) is None:
            raise ValueError("occurred_at requires an ISO datetime with timezone")
        if not isinstance(event.get("summary"), str) or not event["summary"].strip() or len(event["summary"]) > 80:
            raise ValueError("summary must contain 1–80 characters")
        if event["kind"] == "identified" and event["section"] != "research":
            raise ValueError("identified notices belong to research")
    return events


def timestamp(value):
    """Require an explicit timezone; do not guess from observation dates/titles."""
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def current_timestamp(now=None):
    return (now or datetime.now(timezone.utc)).timestamp()


def _window_attributes(start, end, now):
    hidden = "" if start <= now < end else " hidden"
    return f' data-notice-start="{int(start * 1000)}" data-notice-end="{int(end * 1000)}"{hidden}'


def _badge(kind, attributes=""):
    return (f'<span class="update-badge update-badge--{kind}"{attributes} '
            f'title="{NOTICE_DESCRIPTIONS[kind]}" '
            f'aria-label="{NOTICE_DESCRIPTIONS[kind]}">{NOTICE_LABELS[kind]}</span>')


def render_record_notice(record, now=None):
    """NEW takes priority, followed by a still-recent, later article update."""
    current = current_timestamp(now)
    published = timestamp(record.get("published"))
    if published is None or published > current:
        return ""
    new_end = published + NOTICE_DAYS["new"] * 86400
    badges = []
    if current < new_end:
        badges.append(_badge("new", _window_attributes(published, new_end, current)))
    updated = timestamp(record.get("updated"))
    if updated is not None and published < updated <= current:
        update_end = updated + NOTICE_DAYS["update"] * 86400
        update_start = max(updated, new_end)
        if current < update_end and update_start < update_end:
            badges.append(_badge("update", _window_attributes(update_start, update_end, current)))
    return "".join(badges)


def load_notice_events(path=None):
    """An invalid optional config must not take down the gallery build."""
    try:
        data = json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))
        return validate_notice_config(data)
    except (OSError, ValueError, TypeError) as error:
        warnings.warn(f"Update notices unavailable: {error}", stacklevel=2)
        return []


def render_section_notice(section, events, now=None, *, href=None):
    """Display the latest active editorial event, including its specific change."""
    current = current_timestamp(now)
    active = []
    for event in events:
        if event["section"] != section:
            continue
        start = timestamp(event["occurred_at"])
        end = start + NOTICE_DAYS[event["kind"]] * 86400
        if start <= current < end:
            active.append((start, end, event))
    if not active:
        return ""
    start, end, event = max(active, key=lambda item: item[0])
    tag = "a" if href else "span"
    link = f' href="{html.escape(href, quote=True)}"' if href else ""
    classes = "portal-update-note portal-update-link" if href else "portal-update-note"
    return (f'<{tag} class="{classes}"{link}{_window_attributes(start, end, current)}>'
            f'<span class="portal-update-summary">{html.escape(event["summary"])}</span>'
            f'{_badge(event["kind"])}</{tag}>')
