"""Hatena archive stylesheet: the daily and mushroom indexes share styling only."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hatena"
SOURCE = ROOT / "hatena-design-css-daily-archive-2026-10-11.css"
CANDIDATE = ROOT / "hatena-design-css-shared-daily-field-archives-2026-10-17.css"
BASE = ROOT / "hatena-design-css-mobile-optimized-2026-10-09.css"
OLD = "body.page-archive-category.category-日常の記録"
SHARED = "body.page-archive-category:is(.category-日常の記録, .category-キノコ探索日記)"
EYEBROW = ('\n/* Mushroom observation archive shares Daily Notes layout; only its label differs. */\n'
           'body.page-archive-category.category-キノコ探索日記 .archive-heading::before {\n'
           '  content: "FIELD NOTES";\n}\n')


def test_shared_archive_css_exactly_preserves_baseline_and_existing_declarations():
    original = SOURCE.read_text(encoding="utf-8")
    proposed = CANDIDATE.read_text(encoding="utf-8")
    baseline = BASE.read_bytes()
    assert original.encode("utf-8").startswith(baseline)
    assert proposed.encode("utf-8").startswith(baseline)
    assert original.count(OLD) == 73
    assert proposed == original.replace(OLD, SHARED) + EYEBROW
    assert len(proposed.encode("utf-8")) < 65536


def test_scope_keeps_daily_and_observation_categories_only():
    s = CANDIDATE.read_text(encoding="utf-8")
    assert s.count(SHARED) == 73
    assert "body.page-archive-category.category-日常の記録" not in s
    assert 'content: "DAILY NOTES";' in s
    assert 'body.page-archive-category.category-キノコ探索日記 .archive-heading::before {\n  content: "FIELD NOTES";' in s
    for token in (".archive-entry", ".archive-entries-sort", ".entry-thumb", "#box2", "#menu"):
        assert any(token in line and SHARED in line for line in s.splitlines())
