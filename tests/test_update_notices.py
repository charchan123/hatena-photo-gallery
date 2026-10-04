from datetime import datetime, timedelta
import json

from bs4 import BeautifulSoup
import pytest

import main
from records_ui import render_record_preview_rows
from update_notices import load_notice_events, render_record_notice, render_section_notice


NOW = datetime.fromisoformat("2026-10-04T17:00:00+09:00")


def visible_badges(markup):
    return [node.get_text() for node in BeautifulSoup(markup, "html.parser").select(".update-badge")
            if not node.has_attr("hidden")]


@pytest.mark.parametrize("age, expected", [(0, ["NEW!"]), (7 * 86400 - 1, ["NEW!"]), (7 * 86400, []), (-1, [])])
def test_new_window_is_publication_based_and_excludes_future(age, expected):
    record = {"published": (NOW - timedelta(seconds=age)).isoformat(), "title": "1900年1月1日観察"}
    assert visible_badges(render_record_notice(record, now=NOW)) == expected


@pytest.mark.parametrize("value", [None, "bad", "2026-10-04", "2026-10-04T17:00:00", "2026-02-30T00:00:00Z"])
def test_missing_or_ambiguous_dates_do_not_get_badges(value):
    assert render_record_notice({"published": value, "updated": NOW.isoformat()}, now=NOW) == ""


def test_update_and_new_priority_with_cached_page_transition():
    published = NOW - timedelta(days=6)
    record = {"published": published.isoformat(), "updated": NOW.isoformat()}
    markup = render_record_notice(record, now=NOW)
    assert visible_badges(markup) == ["NEW!"]
    update = BeautifulSoup(markup, "html.parser").select_one(".update-badge--update")
    assert update.has_attr("hidden")
    assert int(update["data-notice-start"]) == int((published + timedelta(days=7)).timestamp() * 1000)
    assert visible_badges(render_record_notice(record, now=NOW + timedelta(days=1))) == ["UPDATE!"]
    assert render_record_notice(record, now=NOW + timedelta(days=7)) == ""


@pytest.mark.parametrize("updated", ["2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z", "bad"])
def test_old_future_invalid_update_cannot_revive_old_record(updated):
    assert not render_record_notice({"published": "2026-02-01T00:00:00Z", "updated": updated}, now=NOW)


def event(**kwargs):
    return {"section": "research", "kind": "identified", "occurred_at": NOW.isoformat(),
            "summary": "1種の正体が判明<&", **kwargs}


def test_identified_fourteen_days_specific_summary_and_latest_event():
    events = [event(occurred_at=(NOW-timedelta(days=13)).isoformat()), event(summary="さらに1種の正体が判明")]
    assert "さらに1種の正体が判明" in render_section_notice("research", events, now=NOW)
    markup = render_section_notice("research", events[:1], now=NOW)
    assert "正体が判明&lt;&amp;" in markup and "IDENTIFIED!" in markup
    assert not render_section_notice("research", events[:1], now=NOW + timedelta(days=1))
    assert not render_section_notice("guide", events, now=NOW)
    assert not render_section_notice("research", [event(occurred_at=(NOW+timedelta(seconds=1)).isoformat())], now=NOW)


@pytest.mark.parametrize("kind", ["new", "update"])
def test_editorial_new_and_update_expire_at_seven_days(kind):
    events = [event(section="guide", kind=kind)]
    assert render_section_notice("guide", events, now=NOW + timedelta(days=6))
    assert not render_section_notice("guide", events, now=NOW + timedelta(days=7))


def test_config_validation_and_failure_isolation(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"version": 1, "events": [event()]}))
    assert len(load_notice_events(path)) == 1
    path.write_text(json.dumps({"version": 1, "events": [event(section="guide")]}))
    with pytest.warns(UserWarning):
        assert load_notice_events(path) == []
    path.write_text("broken")
    with pytest.warns(UserWarning):
        assert load_notice_events(path) == []


def test_all_recent_rows_badged_without_changing_order_or_links():
    rows = [{"published": NOW.isoformat(), "title": title, "url": f"https://example.test/{i}"}
            for i, title in enumerate(["長いタイトル" * 10, "2026年9月19日静岡県浜松市"])]
    soup = BeautifulSoup(render_record_preview_rows(rows, now=NOW), "html.parser")
    assert [node.get_text() for node in soup.select(".record-preview-title")] == [r["title"] for r in rows]
    assert len(soup.select(".record-preview-heading .update-badge--new")) == 2
    assert [a["href"] for a in soup.select("a")] == [r["url"] for r in rows]


def test_portal_events_require_editorial_history_not_counts(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "load_notice_events", lambda: [])
    main.generate_new_top({}, {}, research_summary={"case_count": 12}, best_shot_summary={"entry_count": 10})
    assert "IDENTIFIED!" not in (tmp_path / "new-top.html").read_text()
    # Use a current explicit event; the actual production config stays empty.
    current = datetime.now().astimezone().isoformat()
    monkeypatch.setattr(main, "load_notice_events", lambda: [event(occurred_at=current)])
    main.generate_new_top({}, {}, research_summary={"case_count": 12})
    soup = BeautifulSoup((tmp_path / "new-top.html").read_text(), "html.parser")
    assert soup.select_one(".portal-card--research .portal-update-summary").get_text() == "1種の正体が判明<&"
    assert not soup.select("a a")
