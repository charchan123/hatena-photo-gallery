"""Regression tests for current-article, two-name HTML-only photo cross-links."""
import main
from multi_subject import build_multi_subject_photo_overlays


def _rows(tmp_path, heading, categories, *, article_id="article:live"):
    html = tmp_path / "mixed.html"
    html.write_text(
        f'<div class="entry-body"><p>{heading}</p><p><img src="https://cdn.test/unique.jpg" alt=""></p></div>',
        encoding="utf-8",
    )
    metadata = {str(html): {"article_id": article_id, "title": "test", "categories": categories}}
    return main.extract_shadow_metadata([html], metadata, taxonomy=main.load_subject_taxonomy())


def _links(rows, production=()):
    return build_multi_subject_photo_overlays(
        rows, main.load_subject_taxonomy(), list(production), main.match_subject_taxonomy
    )


def test_one_pair_is_two_html_pointers_but_one_source_photo(tmp_path):
    categories = ["キノコ探索日記", "ニガイグチモドキ", "ヤマドリタケモドキ"]
    rows = _rows(tmp_path, "ニガイグチモドキ&ヤマドリタケモドキ", categories)
    assert rows[0]["detected_label"] is None
    assert rows[0]["last_rejected_boundary_reason"] == "multiple_subject_separator"
    src = rows[0]["src"]
    assert _links(rows) == {"ニガイグチモドキ": [src], "ヤマドリタケモドキ": [src]}
    assert _links(rows, [{"alt": "ニガイグチモドキ", "src": src}]) == {
        "ヤマドリタケモドキ": [src],
    }
    assert _links(rows, [{"alt": "シイタケ", "src": src}]) == {}


def test_second_pair_and_uncertain_names_preserve_review_boundary(tmp_path):
    rows = _rows(tmp_path, "ムラサキヤマドリタケ&アカヤマドリ",
                 ["ムラサキヤマドリタケ", "アカヤマドリ"])
    assert set(_links(rows)) == {"ムラサキヤマドリタケ", "アカヤマドリ"}
    for label in (
        "ニガイグチの仲間", "ニガイグチモドキ&不明",
        "ニガイグチモドキ&シイタケ？",
        "ニガイグチモドキ&アカヤマドリ&シイタケ",
    ):
        assert _links(_rows(tmp_path, label, ["ニガイグチモドキ", "アカヤマドリ"])) == {}


def test_current_article_and_category_guards(tmp_path):
    names = ["ニガイグチモドキ", "ヤマドリタケモドキ"]
    text = "ニガイグチモドキ&ヤマドリタケモドキ"
    assert _links(_rows(tmp_path, text, names[:1])) == {}
    assert _links(_rows(tmp_path, text, names, article_id="")) == {}
    rows = _rows(tmp_path, text, names)
    assert _links(rows + rows) == {}
    assert _links([]) == {}


def test_html_only_addition_does_not_change_gallery_index_or_photo_identity(tmp_path, monkeypatch):
    src = "https://cdn.test/one-photo.jpg"
    entries = [{"alt": "ニガイグチモドキ", "src": src}]
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "copy_shared_assets", lambda: None)
    grouped = main.generate_gallery(entries, {}, multi_subject_overlays={
        "ヤマドリタケモドキ": [src]
    })
    assert grouped == {"ニガイグチモドキ": [src]}
    assert entries == [{"alt": "ニガイグチモドキ", "src": src}]
    left = (tmp_path / "ニガイグチモドキ.html").read_text(encoding="utf-8")
    right = (tmp_path / "ヤマドリタケモドキ.html").read_text(encoding="utf-8")
    assert src in left and src in right
    assert "複数種が写る写真" not in left
    assert "複数種が写る写真" in right


def test_unregistered_reference_cannot_offer_an_unresolvable_favorite(tmp_path, monkeypatch):
    from bs4 import BeautifulSoup
    monkeypatch.setattr(main, 'OUTPUT_DIR', str(tmp_path))
    monkeypatch.setattr(main, 'copy_shared_assets', lambda: None)
    src = 'https://cdn.test/unregistered.jpg'
    main.generate_gallery([], {}, multi_subject_overlays={'アカヤマドリ': [src]})
    soup = BeautifulSoup((tmp_path/'アカヤマドリ.html').read_text(), 'html.parser')
    assert soup.select_one('.shared-subject-note')
    assert not soup.select('.thumb-fav')
    assert '登録件数には加算しません' in soup.get_text()


def test_source_disappearance_removes_both_display_pointers_in_fresh_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'copy_shared_assets', lambda: None)
    rows = _rows(tmp_path, 'ニガイグチモドキ&ヤマドリタケモドキ', ['ニガイグチモドキ', 'ヤマドリタケモドキ'])
    before, after = tmp_path/'before', tmp_path/'after'
    monkeypatch.setattr(main, 'OUTPUT_DIR', str(before))
    main.generate_gallery([], {}, multi_subject_overlays=_links(rows))
    assert all(rows[0]['src'] in p.read_text() for p in before.glob('*.html') if p.stem in ['ニガイグチモドキ','ヤマドリタケモドキ'])
    monkeypatch.setattr(main, 'OUTPUT_DIR', str(after))
    main.generate_gallery([], {}, multi_subject_overlays=_links([]))
    assert not list(after.glob('*.html'))
    assert _links(rows, [{'alt': 'シイタケ', 'src': rows[0]['src']}]) == {}
