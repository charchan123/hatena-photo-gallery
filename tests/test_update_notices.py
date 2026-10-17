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


def test_best_shot_notice_may_lead_with_badge_without_changing_expiry():
    events = [{"section": "best-shots", "kind": "new",
               "summary": "ベストショットを追加", "occurred_at": NOW.isoformat()}]
    default = BeautifulSoup(render_section_notice("best-shots", events, now=NOW), "html.parser")
    badge_first = BeautifulSoup(render_section_notice("best-shots", events, now=NOW,
                                                       badge_first=True), "html.parser")
    notice = badge_first.select_one(".portal-update-note")
    assert [node.get_text(strip=True) for node in notice.find_all(recursive=False)] == [
        "NEW!", "ベストショットを追加",
    ]
    assert [node.get_text(strip=True) for node in default.select_one(
        ".portal-update-note").find_all(recursive=False)] == ["ベストショットを追加", "NEW!"]
    assert notice["data-notice-start"] == default.select_one(".portal-update-note")["data-notice-start"]
    assert notice["data-notice-end"] == default.select_one(".portal-update-note")["data-notice-end"]
    assert int(notice["data-notice-end"]) - int(notice["data-notice-start"]) == 7 * 86400 * 1000
    assert not render_section_notice("best-shots", events, now=NOW + timedelta(days=7),
                                     badge_first=True)


def test_best_shot_notice_shares_description_row_with_research_card(monkeypatch, tmp_path):
    now = datetime.now().astimezone()
    events = [{"section": "best-shots", "kind": "new",
               "summary": "ベストショットを追加", "occurred_at": now.isoformat()}]
    monkeypatch.setattr(main, "load_notice_events", lambda: events)
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_new_top({}, {}, research_summary={"case_count": 66},
                          best_shot_summary={"entry_count": 12})
    soup = BeautifulSoup((tmp_path / "new-top.html").read_text(encoding="utf-8"), "html.parser")
    research = soup.select_one(".portal-card--research")
    best = soup.select_one(".portal-card--best-shots")
    assert research.select_one("strong + .portal-card__details > small").get_text() == "正体を調べているキノコを見る"
    assert best.select_one("strong + .portal-card__details > small").get_text() == "とっておきの一枚を集めた写真館"
    assert not research.select_one(".portal-update-note")
    note = best.select_one(".portal-card__details > .portal-update-note")
    assert note is not None
    assert [child.get_text(strip=True) for child in note.find_all(recursive=False)] == [
        "NEW!", "ベストショットを追加",
    ]
    assert not best.select_one(".portal-card__copy > .portal-update-note")
    assert not soup.select("a a")
    # No NEW! changes a card's eyebrow, title, destination or image asset.
    assert research.select_one(".portal-eyebrow").get_text() == "RESEARCH LAB"
    assert best.select_one(".portal-eyebrow").get_text() == "BEST SHOTS"
    assert best.select_one("strong").get_text(" ", strip=True).startswith("ベストショット")
    assert best["href"] == "best-shots.html"


def test_guide_section_notices_stay_in_same_description_area(monkeypatch, tmp_path):
    current = datetime.now().astimezone()
    sections = ("guide", "season", "features")
    active_events = [{"section": name, "kind": "new", "summary": f"{name}の候補を追加",
                      "occurred_at": current.isoformat()} for name in sections]
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    for events in ([], active_events):
        monkeypatch.setattr(main, "load_notice_events", lambda events=events: events)
        main.generate_new_top({}, {}, feature_search_available=True)
        soup = BeautifulSoup((tmp_path / "new-top.html").read_text(encoding="utf-8"),
                             "html.parser")
        for name in sections:
            card = soup.select_one(f".portal-guide-row .portal-card--{name}")
            row = card.find_parent(class_="portal-guide-row")
            note = row.select_one(".portal-guide-note")
            details = note.select_one(".portal-guide-note__details")
            assert len(note.find_all("strong", recursive=False)) == 1
            assert details is not None
            assert note.select_one("strong").get_text(strip=True)
            assert details.find("small", recursive=False).get_text(strip=True)
            assert not note.find("small", recursive=False)
            linked = details.select_one(".portal-update-note")
            if events:
                assert linked is not None
                assert linked.name == "a" and linked["href"] == card["href"]
                assert [child.get_text(strip=True)
                        for child in linked.find_all(recursive=False)] == [
                            "NEW!", f"{name}の候補を追加",
                        ]
                assert int(linked["data-notice-end"]) - int(
                    linked["data-notice-start"]) == 7 * 86400 * 1000
            else:
                assert linked is None
        assert not soup.select("a a")


def test_research_identified_notice_uses_best_shot_details_without_shifting_title(
        monkeypatch, tmp_path):
    now = datetime.now().astimezone()
    events = [{"section": "research", "kind": "identified",
               "summary": "長い研究結果の報告" * 8, "occurred_at": now.isoformat()}]
    monkeypatch.setattr(main, "load_notice_events", lambda: events)
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    main.generate_new_top({}, {}, research_summary={"case_count": 66},
                          best_shot_summary={"entry_count": 12})
    soup = BeautifulSoup((tmp_path / "new-top.html").read_text(encoding="utf-8"),
                         "html.parser")
    card = soup.select_one(".portal-card--research")
    details = card.select_one("strong + .portal-card__details")
    assert details.find("small", recursive=False).get_text(strip=True) == "正体を調べているキノコを見る"
    note = details.select_one(".portal-update-note")
    assert [item.get_text(strip=True) for item in note.find_all(recursive=False)] == [
        "IDENTIFIED!", "長い研究結果の報告" * 8,
    ]
    assert int(note["data-notice-end"]) - int(
        note["data-notice-start"]) == 14 * 86400 * 1000
    assert not soup.select("a a")
    best = soup.select_one(".portal-card--best-shots")
    assert best.select_one(".portal-card__details > small")
    assert not best.select_one(".portal-update-note")
