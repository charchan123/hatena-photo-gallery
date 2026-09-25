import json
from pathlib import Path

import main
import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_normal_article_and_consecutive_images():
    entries = main.fetch_images([FIXTURES / "article_body.html"])

    assert entries == [
        {"alt": "ムキタケ", "src": "https://example.invalid/mukitake-1.jpg"},
        {"alt": "ムキタケ", "src": "https://example.invalid/mukitake-2.jpg"},
        {"alt": "ハラタケ", "src": "https://example.invalid/haratake.jpg"},
    ]


def test_shadow_metadata_uses_article_text_state_in_dom_order():
    metadata = main.extract_shadow_metadata(
        [FIXTURES / "article_metadata_state.html"]
    )

    assert [item["src"].rsplit("/", 1)[-1] for item in metadata] == [
        "0.jpg",
        "1.jpg",
        "2.jpg",
        "3.jpg",
        "juvenile.jpg",
        "underside.jpg",
        "4.jpg",
        "description.jpg",
        "5.jpg",
    ]
    assert metadata[0]["detected_label"] is None
    assert metadata[0]["gallery_name"] is None
    assert metadata[0]["confidence"] == "low"
    assert [item["detected_label"] for item in metadata[1:6]] == ["ムキタケ"] * 5
    assert metadata[1]["legacy_alt"] == "legacy-one"
    assert metadata[1]["confidence"] == "medium"
    assert metadata[4]["confidence"] == "high"
    assert metadata[6]["detected_label"] == "クダアカゲシメジ？"
    assert metadata[6]["gallery_name"] is None
    assert metadata[7]["detected_label"] == "クダアカゲシメジ？"
    assert metadata[7]["confidence"] == "high"
    assert metadata[8]["detected_label"] == "キハツダケ"
    assert all(item["subject_type"] == "review" for item in metadata)
    assert all(item["source"] == "standalone_text_state" for item in metadata)
    assert all(
        item["article_path"].endswith("article_metadata_state.html")
        for item in metadata
    )


def test_image_containing_subject_block_updates_state_for_nested_and_later_images(tmp_path):
    article = tmp_path / "image-subject.html"
    article.write_text(
        '<p>ヒラタケ<img src="a.jpg"><img src="b.jpg"></p>'
        '<p>説明です。</p><p><img src="c.jpg"></p>',
        encoding="utf-8",
    )

    metadata = main.extract_shadow_metadata([article], article_metadata={})

    assert [row["detected_label"] for row in metadata] == ["ヒラタケ"] * 3
    assert all(row["subject_type"] == "mushroom" for row in metadata)
    assert all(row["classification_confidence"] == "high" for row in metadata)


def test_image_containing_sentence_alt_and_category_do_not_create_subject(tmp_path):
    article = tmp_path / "no-fallback.html"
    article.write_text(
        '<p>今日は山へ行きました。<img src="x.jpg" alt="ヒラタケ"></p>',
        encoding="utf-8",
    )
    info = {str(article): {"categories": ["ヒラタケ"]}}

    [row] = main.extract_shadow_metadata([article], article_metadata=info)

    assert row["detected_label"] is None
    assert row["subject_type"] == "review"
    assert row["classification_confidence"] == "low"


def test_image_containing_unmatched_candidate_remains_review(tmp_path):
    article = tmp_path / "review.html"
    article.write_text('<p>フキノトウ<img src="x.jpg"></p>', encoding="utf-8")

    [row] = main.extract_shadow_metadata([article], article_metadata={})

    assert row["detected_label"] == "フキノトウ"
    assert row["subject_type"] == "review"
    assert row["classification_reason"] == "taxonomy_unmatched"
    assert row["classification_confidence"] == "low"
    assert row["gallery_name"] is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("コテングタケモドキ(編集中)", "コテングタケモドキ"),
        ("コテングタケモドキ（編集中）", "コテングタケモドキ"),
        ("オオワライタケ(20日撮影)", "オオワライタケ"),
        ("オオワライタケ（20日撮影）", "オオワライタケ"),
        ("オオワライタケ(25日)", "オオワライタケ"),
        ("キサケツバタケ？(26日撮影)", "キサケツバタケ？"),
        ("オオワライタケ(1日)", "オオワライタケ"),
        ("オオワライタケ(31日)", "オオワライタケ"),
        ("オオワライタケ(1日撮影)", "オオワライタケ"),
        ("オオワライタケ（31日撮影）", "オオワライタケ"),
        ("アラゲキクラゲ(アルビノ)？", "アラゲキクラゲ(アルビノ)？"),
        ("アラゲキクラゲ（アルビノ）？", "アラゲキクラゲ（アルビノ）？"),
        ("キアシヤマドリタケ(仮称)", "キアシヤマドリタケ(仮称)"),
        ("アンズタケ(広義)", "アンズタケ(広義)"),
        ("Lanmaoa angustispora(和名無し)？", "Lanmaoa angustispora？"),
        ("Lanmaoa angustispora（和名無し）", "Lanmaoa angustispora"),
    ],
)
def test_extract_subject_candidate_label_narrow_transformations(raw, expected):
    assert main.extract_subject_candidate_label(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "オオワライタケ(0日)", "オオワライタケ(32日)",
        "オオワライタケ(2025年10月20日)", "オオワライタケ(去年撮影)",
        "オオワライタケ(朝撮影)", "オオワライタケ(再撮影)",
        "オオワライタケ(確認中)", "アラゲキクラゲ(白色型)？",
        "This is a mushroom", "Butyriboletus roseogriseus？の事について",
        "ミネシメジの仲間", "Lanmaoa angustisporaの残骸",
        "オオワライタケの定点観察のため、また近所の緑地へと行ってきた。",
    ],
)
def test_extract_subject_candidate_label_rejects_unsupported_broadening(raw):
    assert main.extract_subject_candidate_label(raw) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ムキタケ", True),
        ("べにてんぐたけ", True),
        ("クダアカゲシメジ？", True),
        ("種類不明", True),
        ("コツブノオオワライタケ(仮称)", True),
        ("キアシヤマドリタケ（仮称）？", True),
        ("アンズタケ(広義)", True),
        ("Lanmaoa angustispora？", True),
        ("This is a mushroom", False),
        ("この日は林道沿いで見つけました。", False),
        ("幼菌", False),
        ("傘の裏", False),
        ("傘の裏側には細かい特徴があります。", False),
        ("https://example.invalid/name", False),
        ("2026年9月23日", False),
    ],
)
def test_subject_label_candidate_is_conservative(text, expected):
    assert main.is_subject_label_candidate(text) is expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "empty"), ("ア" * 25, "too_long"), ("幼菌", "stopword"),
        ("説明です。", "sentence_punctuation"),
        ("https://example.invalid", "url"), ("2026年9月", "date_like"),
        ("キアシヤマドリタケ(要確認)", "unsupported_annotation"),
        ("英字ABC", "unsupported_characters"), ("キノ", "too_few_kana"),
        ("不明", "accepted_unknown_label"),
        ("Lanmaoa angustispora？", "accepted_latin_label"),
        ("キアシヤマドリタケ(仮称)", "accepted_kana_label"),
    ],
)
def test_candidate_diagnostic_matches_unchanged_predicate(text, reason):
    diagnostic = main.diagnose_subject_label_candidate(text)
    assert diagnostic["candidate"] is main.is_subject_label_candidate(text)
    assert diagnostic["candidate_reason"] == reason


@pytest.mark.parametrize("boundary", [
    "ベニタケの仲間", "ベニタケの仲間(2)", "ホウキタケの仲間",
    "ヤマイグチの仲間？", "Lanmaoa angustisporaの残骸",
    "Butyriboletus roseogriseus？の事について",
    "ウラベニガサ＆タマキクラゲ", "エノキタケ&アラゲキクラゲ",
    "サザナミイグチorフリルイグチ(仮称)？",
    "不明ベニタケ(カワリハツ？)",
    "ヤマドリタケモドキ(ヨゴレキアミアシイグチの可能性有り)",
])
def test_rejected_subject_boundary_ends_previous_subject(boundary, tmp_path):
    article = tmp_path / "boundary.html"
    article.write_text(
        f'<p>ヤナギマツタケ</p><img src="before.jpg">'
        f'<p>{boundary}</p><img src="blocked.jpg">', encoding="utf-8",
    )

    rows = main.extract_shadow_metadata([article], article_metadata={})

    assert rows[0]["detected_label"] == "ヤナギマツタケ"
    assert rows[0]["subject_state_status"] == "accepted_subject"
    assert rows[1]["detected_label"] is None
    assert rows[1]["subject_state_status"] == "reset_by_rejected_boundary"
    assert rows[1]["last_rejected_boundary_text"] == boundary
    assert rows[1]["last_rejected_boundary_reason"]


def test_ordinary_text_does_not_reset_and_accepted_subject_replaces_state(tmp_path):
    article = tmp_path / "state.html"
    article.write_text(
        '<p>ノウタケ</p><img src="1.jpg"><p>普通の説明文です。</p>'
        '<img src="2.jpg"><p>ホウキタケの仲間</p><img src="3.jpg">'
        '<p>シイタケ</p><img src="4.jpg"><img src="5.jpg">',
        encoding="utf-8",
    )

    rows = main.extract_shadow_metadata([article], article_metadata={})

    assert [row["detected_label"] for row in rows] == [
        "ノウタケ", "ノウタケ", None, "シイタケ", "シイタケ",
    ]
    assert rows[2]["subject_state_status"] == "reset_by_rejected_boundary"
    assert rows[3]["subject_source_block_text"] == "シイタケ"


def test_residual_gap_audit_preserves_occurrences_and_context(tmp_path):
    article = tmp_path / "article.html"
    article.write_text(
        '<div class="entry-body"><p>説明です。</p><p>今日は山へ行きました。<img src="same.jpg" alt="キノコ"></p>'
        '<p>追加説明です。</p><img src="same.jpg" alt=""><p>シイタケ</p><img src="after.jpg" alt="legacy"></div>',
        encoding="utf-8",
    )
    path = str(article)
    info = {path: {"title": "audit", "article_id": "id", "categories": ["キノコ"]}}
    baseline = main.extract_shadow_metadata([article], article_metadata=info, taxonomy=None)
    audit = main.build_residual_gap_audit([article], baseline, info)

    assert [row["detected_label"] for row in baseline] == [None, None, "シイタケ"]
    assert [row["src"] for row in audit["undetected_images"]] == ["same.jpg", "same.jpg"]
    assert [row["article_image_index"] for row in audit["undetected_images"]] == [0, 1]
    first = audit["undetected_images"][0]
    assert first["position_relative_to_first_subject"] == "before_first_valid_subject"
    assert first["containing_block"]["text"] == "今日は山へ行きました。"
    assert first["containing_block"]["candidate"] is False
    assert first["containing_block"]["effective_candidate"] is False
    assert first["next_valid_subject"] == {"text": "シイタケ", "tag": "p", "blocks_ahead": 2, "images_ahead": 1}
    assert first["legacy_alt_category_match"]["match_type"] == "exact"
    assert baseline[0]["subject_type"] == "review"  # alt remains audit-only
    assert len(first["next_blocks"]) <= 3
    assert audit["undetected_articles"][0]["undetected_image_count"] == 2
    assert set(audit) == {"version", "summary", "undetected_images", "undetected_articles", "taxonomy_unmatched_labels"}


def test_residual_gap_audit_uses_effective_subject_rule(tmp_path):
    article = tmp_path / "effective.html"
    article.write_text(
        '<img src="before.jpg"><p>オオワライタケ(20日撮影)</p><img src="after.jpg">',
        encoding="utf-8",
    )
    metadata = main.extract_shadow_metadata([article], article_metadata={}, taxonomy=None)
    audit = main.build_residual_gap_audit([article], metadata, {})

    assert [row["detected_label"] for row in metadata] == [None, "オオワライタケ"]
    [gap] = audit["undetected_images"]
    assert gap["position_relative_to_first_subject"] == "before_first_valid_subject"
    assert gap["next_valid_subject"]["text"] == "オオワライタケ"
    assert audit["undetected_articles"][0]["first_valid_subject_label"] == "オオワライタケ"


def test_residual_gap_audit_handles_article_without_subject(tmp_path):
    article = tmp_path / "no-subject.html"
    article.write_text('<p>説明です。</p><img src="x.jpg">', encoding="utf-8")
    metadata = main.extract_shadow_metadata([article], article_metadata={}, taxonomy=None)
    audit = main.build_residual_gap_audit([article], metadata, {})
    assert audit["undetected_images"][0]["position_relative_to_first_subject"] == "article_has_no_valid_subject"
    assert audit["undetected_articles"][0]["first_valid_subject_label"] is None


def test_residual_taxonomy_aggregation_sort_flags_and_export(tmp_path, monkeypatch):
    article = tmp_path / "labels.html"
    article.write_text('<p>不明</p><img src="1"><img src="2"><p>Lanmaoa angustispora？</p><img src="3"><p>キノコ(仮称)</p><img src="4"><p>キノコ(広義)</p><img src="5">', encoding="utf-8")
    metadata = main.extract_shadow_metadata([article], article_metadata={}, taxonomy=None)
    audit = main.build_residual_gap_audit([article], metadata, {})
    rows = audit["taxonomy_unmatched_labels"]
    assert [row["image_count"] for row in rows] == [2, 1, 1, 1]
    assert rows[0]["flags"]["unknown"] is True
    assert any(row["flags"]["latin"] and row["flags"]["question"] for row in rows)
    assert any(row["flags"]["provisional"] for row in rows)
    assert any(row["flags"]["broad_sense"] for row in rows)
    assert all("category_exact_count" in row and "normalized_taxonomy_key" in row for row in rows)
    output = tmp_path / "audit.json"
    monkeypatch.setattr(main, "RESIDUAL_GAP_AUDIT_FILE", str(output))
    main.save_residual_gap_audit(audit)
    assert json.loads(output.read_text(encoding="utf-8"))["version"] == 1


def test_unknown_gallery_mapping_preserves_detected_label():
    assert main.normalize_gallery_name("シイタケ?", "mushroom", "シイタケ") == "不明"
    assert main.normalize_gallery_name("種類不明", "review") is None
    assert main.normalize_gallery_name("シイタケ", "mushroom", "シイタケ") == "シイタケ"


def test_phase3b_candidate_state_preserves_annotations_and_latin_name():
    metadata = main.extract_shadow_metadata(
        [FIXTURES / "article_metadata_phase3b.html"], article_metadata={}
    )
    labels = [item["detected_label"] for item in metadata]
    assert labels == [
        "コツブノオオワライタケ(仮称)",
        "キアシヤマドリタケ（仮称）？",
        "アンズタケ(広義)",
        "Lanmaoa angustispora？",
        "Lanmaoa angustispora？",
    ]
    assert metadata[1]["gallery_name"] is None
    assert metadata[3]["gallery_name"] is None


def test_shadow_summary_counts_required_audit_states():
    metadata = main.extract_shadow_metadata(
        [FIXTURES / "article_metadata_state.html"]
    )

    summary = main.summarize_shadow_metadata(metadata)
    assert {key: summary[key] for key in (
        "total_images", "detected", "undetected", "legacy_alt_match",
        "legacy_alt_mismatch", "unknown_mapped"
    )} == {
        "total_images": 9,
        "detected": 8,
        "undetected": 1,
        "legacy_alt_match": 2,
        "legacy_alt_mismatch": 6,
        "unknown_mapped": 0,
    }
    assert summary["subject_type_review"] == 9
    assert summary["classification_low"] == 9
    assert summary["images_without_category_match"] == 9
    assert summary["images_with_category_match"] == 0


def test_shadow_report_limits_audit_output(capsys):
    metadata = main.extract_shadow_metadata(
        [FIXTURES / "article_metadata_state.html"]
    )

    main.report_shadow_metadata(metadata, audit_limit=2)
    output = capsys.readouterr().out

    assert "Phase 3B.2 metadata shadow summary:" in output
    assert "total_images=9" in output
    assert "legacy_alt_mismatch=6" in output
    assert output.count("Phase 3B.1 shadow audit:") == 3  # two rows plus omitted count
    assert "7 more omitted" in output


def test_shadow_metadata_json_is_written_under_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    shadow_file = cache_dir / "phase3-shadow-metadata.json"
    monkeypatch.setattr(main, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(main, "SHADOW_METADATA_FILE", str(shadow_file))
    metadata = main.extract_shadow_metadata(
        [FIXTURES / "article_metadata_state.html"]
    )

    main.save_shadow_metadata(metadata)

    assert shadow_file.exists()
    assert shadow_file.read_text(encoding="utf-8").startswith("[\n  {")


def test_normal_build_only_uses_files_returned_by_api(monkeypatch, tmp_path):
    articles = tmp_path / "articles"
    articles.mkdir()
    current = articles / "article_1.html"
    current.write_text((FIXTURES / "article_body.html").read_text(), encoding="utf-8")
    # These filenames deliberately match the legacy production files.
    (articles / "article1.html").write_text(
        (FIXTURES / "legacy_full_page.html").read_text(), encoding="utf-8"
    )
    (articles / "article2.html").write_text(
        (FIXTURES / "legacy_full_page.html").read_text(), encoding="utf-8"
    )
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: [str(current)])

    article_files = main.fetch_hatena_articles_api()
    entries = main.fetch_images(article_files)

    assert {entry["alt"] for entry in entries} == {"ムキタケ", "ハラタケ"}
    assert not any("hatena" in entry["src"] or "group" in entry["src"] for entry in entries)


def test_known_false_pages_are_not_generated(monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.setattr(main, "OUTPUT_DIR", str(output))
    entries = main.fetch_images([FIXTURES / "article_body.html"])

    grouped = main.generate_gallery(entries, {})
    generated = {path.name for path in output.glob("*.html")}

    assert set(grouped) == {"ムキタケ", "ハラタケ"}
    assert "ムキタケ.html" in generated
    assert "ハラタケ.html" in generated
    assert generated.isdisjoint(
        {
            "id_exsudoporus_ruber.html",
            "【公式】2025年開設ブログ.html",
            "f_id_exsudoporus_ruber_20250316193622j_image.html",
            "f_id_exsudoporus_ruber_20250316194123j_image.html",
            "f_id_exsudoporus_ruber_20250316194402j_image.html",
            "f_id_exsudoporus_ruber_20250316194450j_image.html",
        }
    )


def test_generated_page_types_use_copied_shared_assets(monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.setattr(main, "OUTPUT_DIR", str(output))
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    entries = main.fetch_images([FIXTURES / "article_body.html"])

    grouped = main.generate_gallery(entries, {})
    main.generate_index(grouped, {})
    main.generate_favorite_page(grouped)

    page_paths = {
        "index": output / "index.html",
        "favorite": output / "favorite.html",
        "detail": output / "ムキタケ.html",
        "aiuo": output / "ま行.html",
    }
    for page_type, page_path in page_paths.items():
        generated_html = page_path.read_text(encoding="utf-8")
        assert 'href="assets/gallery.css"' in generated_html, page_type
        assert 'src="assets/gallery.js"' in generated_html, page_type
        assert "<style>" not in generated_html, page_type
        assert "let lastHeight = 0" not in generated_html, page_type

    for filename in ("gallery.css", "gallery.js"):
        assert (output / "assets" / filename).read_bytes() == (
            Path(main.ASSETS_DIR) / filename
        ).read_bytes()


@pytest.mark.parametrize(
    ("name", "group", "initial"),
    [
        ("タマゴタケ", "た行", "タ"),
        ("ダイダイタケ", "た行", "タ"),
        ("ドクツルタケ", "た行", "ト"),
        ("ガンタケ", "か行", "カ"),
        ("ザラミノシメジ", "さ行", "サ"),
        ("ベニテングタケ", "は行", "ヘ"),
        ("ポルチーニ", "は行", "ホ"),
        ("ゔぇーる", "あ行", "う"),
    ],
)
def test_voiced_kana_initials_use_seion_filter(name, group, initial):
    assert main.get_aiuo_group(name) == group
    assert main.normalize_kana_initial(name) == initial


def test_gojuon_pages_merge_voiced_initial_buttons(monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.setattr(main, "OUTPUT_DIR", str(output))
    names = ["タマゴタケ", "ダイダイタケ", "ドクツルタケ"]
    entries = [
        {"alt": name, "src": f"https://example.invalid/{index}.jpg"}
        for index, name in enumerate(names)
    ]

    main.generate_gallery(entries, {})
    page = (output / "た行.html").read_text(encoding="utf-8")

    assert page.count('class="kana-btn" data-kana="タ"') == 1
    assert page.count('class="kana-btn" data-kana="ト"') == 1
    assert 'class="kana-btn" data-kana="ダ"' not in page
    assert 'class="kana-btn" data-kana="ド"' not in page
    assert page.count('data-kana="タ"') == 3
    assert page.count('data-kana="ト"') == 2


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("たまご", "タマゴ", "たまご"),
        ("べにてんぐ", "ベニテング", "べにてんぐ"),
        ("タマゴ", "ﾀﾏｺﾞ", "たまご"),
    ],
)
def test_japanese_search_normalization(left, right, expected):
    assert main.normalize_japanese_search(left) == expected
    assert main.normalize_japanese_search(right) == expected


def test_missing_secrets_only_block_api_access(monkeypatch):
    monkeypatch.setattr(main, "HATENA_USER", None)
    monkeypatch.setattr(main, "HATENA_BLOG_ID", None)
    monkeypatch.setattr(main, "HATENA_API_KEY", None)

    try:
        main.fetch_hatena_articles_api()
    except EnvironmentError as error:
        assert "HATENA_USER" in str(error)
    else:
        raise AssertionError("API access must fail without credentials")

    assert main.fetch_images([FIXTURES / "article_body.html"])


def test_fetch_hatena_articles_api_returns_saved_article_files(monkeypatch, tmp_path):
    atom_response = """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>tag:example,1</id><title>First title</title>
    <category term="キノコ"/><category term="観察記録"/>
    <content type="text/html">&lt;p&gt;first&lt;/p&gt;</content></entry>
  <entry><content type="text/html">&lt;p&gt;second&lt;/p&gt;</content></entry>
</feed>
"""

    class FakeResponse:
        status_code = 200
        text = atom_response

    monkeypatch.setattr(main, "HATENA_USER", "test-user")
    monkeypatch.setattr(main, "HATENA_BLOG_ID", "test-blog")
    monkeypatch.setattr(main, "HATENA_API_KEY", "test-key")
    monkeypatch.setattr(main, "ARTICLES_DIR", str(tmp_path / "articles"))
    sidecar = tmp_path / "cache" / "phase3-article-metadata.json"
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(main, "ARTICLE_METADATA_FILE", str(sidecar))
    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: FakeResponse())

    article_files = main.fetch_hatena_articles_api()

    assert article_files == [
        str(tmp_path / "articles" / "article_1.html"),
        str(tmp_path / "articles" / "article_2.html"),
    ]
    assert [Path(path).read_text(encoding="utf-8") for path in article_files] == [
        "<p>first</p>",
        "<p>second</p>",
    ]
    captured = __import__("json").loads(sidecar.read_text(encoding="utf-8"))
    assert captured[article_files[0]]["article_id"] == "tag:example,1"
    assert captured[article_files[0]]["title"] == "First title"
    assert captured[article_files[0]]["categories"] == ["キノコ", "観察記録"]


def test_article_metadata_sidecar_failure_does_not_discard_articles(monkeypatch, tmp_path, capsys):
    atom_response = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><content>x</content></entry></feed>'
    response = type("Response", (), {"status_code": 200, "text": atom_response})()
    monkeypatch.setattr(main, "HATENA_USER", "user")
    monkeypatch.setattr(main, "HATENA_BLOG_ID", "blog")
    monkeypatch.setattr(main, "HATENA_API_KEY", "key")
    monkeypatch.setattr(main, "ARTICLES_DIR", str(tmp_path / "articles"))
    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(
        main,
        "save_article_metadata",
        lambda data: (_ for _ in ()).throw(OSError("read-only")),
    )

    assert main.fetch_hatena_articles_api() == [
        str(tmp_path / "articles" / "article_1.html")
    ]
    assert (
        "Phase 3B article metadata capture failed: read-only"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("ムキタケ", ("review", "taxonomy_unmatched", "low")),
        ("コブハクチョウ", ("non_mushroom", "taxonomy_non_mushroom", "high")),
        ("シイタケ", ("mushroom", "taxonomy_mushroom", "high")),
        (None, ("review", "no_detected_label", "low")),
    ],
)
def test_taxonomy_aware_classification(label, expected):
    assert main.classify_subject_type(label, main.load_subject_taxonomy()) == expected


def test_shadow_metadata_uses_metadata_for_classification_without_changing_confidence():
    path = FIXTURES / "article_metadata_state.html"
    article_metadata = {
        str(path): {"article_id": "entry-1", "title": "Birds", "categories": ["野鳥"]}
    }
    metadata = main.extract_shadow_metadata([path], article_metadata)
    assert metadata[1]["subject_type"] == "review"
    assert metadata[1]["classification_confidence"] == "low"
    assert metadata[1]["confidence"] == "medium"
    assert metadata[1]["article_id"] == "entry-1"
    assert metadata[1]["article_title"] == "Birds"


def test_category_corroboration_is_audit_evidence_not_mushroom_taxonomy(tmp_path):
    article = tmp_path / "article.html"
    article.write_text('<p>ミツバアケ</p><img src="x.jpg" alt="">', encoding="utf-8")
    records = main.extract_shadow_metadata([article], {
        str(article): {"categories": ["ミツバアケ", "キノコ探索日記"]}
    })
    assert records[0]["matched_categories"] == ["ミツバアケ"]
    assert records[0]["category_match_type"] == "exact"
    assert records[0]["subject_type"] == "review"
    assert records[0]["classification_confidence"] == "low"


def test_category_match_normalization_and_no_match():
    assert main.match_label_to_categories("キアシヤマドリタケ(仮称)？", ["キアシヤマドリタケ(仮称)"]) == (["キアシヤマドリタケ(仮称)"], "normalized")
    assert main.match_label_to_categories("ムキタケ", ["観察記録"]) == ([], "none")


def test_category_evidence_uses_exact_terms_and_separates_context():
    assert main.get_category_evidence(["キノコ探索日記"]) == {
        "has_mushroom_context": True,
        "has_explicit_mushroom_signal": False,
        "has_explicit_non_mushroom_signal": False,
    }
    assert not main.get_category_evidence(["野鳥観察日記"])[
        "has_explicit_non_mushroom_signal"
    ]


def test_legacy_alt_does_not_change_classification_or_category_match(tmp_path):
    article = tmp_path / "article.html"
    metadata = {str(article): {"categories": ["ミツバアケ", "キノコ探索日記"]}}
    results = []
    for alt in ("", "completely different"):
        article.write_text(f'<p>ミツバアケ</p><img src="x.jpg" alt="{alt}">', encoding="utf-8")
        results.append(main.extract_shadow_metadata([article], metadata)[0])
    assert {(row["subject_type"], row["category_match_type"]) for row in results} == {("review", "exact")}


def test_empty_alt_audit_and_distinct_label_summary(tmp_path, capsys):
    article = tmp_path / "article.html"
    article.write_text('<p>コブハクチョウ</p><img src="1.jpg" alt=""><img src="2.jpg" alt="">', encoding="utf-8")
    records = main.extract_shadow_metadata([article], {str(article): {"title": "Bird", "categories": ["キノコ探索日記"]}})
    main.report_shadow_metadata(records)
    output = capsys.readouterr().out
    assert "Phase 3B.1 empty-alt detected audit" in output
    assert "detected=コブハクチョウ" in output
    assert main.summarize_detected_labels(records)[0]["image_count"] == 2
    summary = main.summarize_shadow_metadata(records)
    assert summary["detected_empty_alt"] == 2
    assert summary["unique_detected_labels"] == 1


def test_category_inventory_counts_articles_once_per_category(capsys):
    files = ["a.html", "b.html", "c.html"]
    result = main.report_category_inventory(files, {
        "a.html": {"categories": ["キノコ", "観察記録"]},
        "b.html": {"categories": ["キノコ"]},
        "c.html": {"categories": []},
    })
    assert result == {
        "categories": {"キノコ": 2, "観察記録": 1},
        "total_unique_categories": 2,
        "articles_with_categories": 2,
        "articles_without_categories": 1,
        "articles_with_mushroom_context": 0,
        "articles_with_explicit_non_mushroom_signal": 0,
        "articles_with_conflicting_signals": 0,
    }
    assert "キノコ=2 articles" in capsys.readouterr().out


def test_build_stops_when_api_returns_no_article_files(monkeypatch):
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: [])
    monkeypatch.setattr(
        main,
        "fetch_images",
        lambda _files: pytest.fail("image extraction must not run without articles"),
    )

    with pytest.raises(RuntimeError, match="記事ファイル"):
        main.build_gallery()


def test_build_stops_when_articles_contain_no_images(monkeypatch):
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda _files: [])
    monkeypatch.setattr(
        main,
        "load_exif_cache",
        lambda: pytest.fail("generation must not run without image entries"),
    )

    with pytest.raises(RuntimeError, match="画像を1件も抽出"):
        main.build_gallery()


def test_build_processes_non_empty_data_as_before(monkeypatch):
    entries = [{"alt": "ムキタケ", "src": "https://example.invalid/mukitake.jpg"}]
    calls = []

    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries if files else [])
    monkeypatch.setattr(
        main,
        "extract_shadow_metadata",
        lambda files, **kwargs: [{"shadow": True}] if files else [],
    )
    monkeypatch.setattr(
        main, "report_shadow_metadata", lambda metadata, **kwargs: calls.append("shadow-report")
    )
    monkeypatch.setattr(
        main, "save_shadow_metadata", lambda metadata: calls.append("shadow-save")
    )
    monkeypatch.setattr(main, "build_phase3c_readiness", lambda legacy, shadow: {"summary": {}, "blocked_review_labels": []})
    monkeypatch.setattr(main, "report_phase3c_readiness", lambda audit: calls.append("readiness-report"))
    monkeypatch.setattr(main, "save_phase3c_readiness", lambda audit: calls.append("readiness-save"))
    monkeypatch.setattr(main, "load_article_metadata", lambda: {})
    monkeypatch.setattr(main, "build_phase3c_hybrid_preview",
                        lambda legacy, shadow, metadata: ([], {"summary": {}, "rename_groups": [], "added_groups": []}))
    monkeypatch.setattr(main, "report_phase3c_hybrid_preview",
                        lambda report: calls.append("hybrid-report"))
    monkeypatch.setattr(main, "save_phase3c_hybrid_preview",
                        lambda report: calls.append("hybrid-save"))
    monkeypatch.setattr(main, "build_residual_gap_audit", lambda files, metadata: {"summary": {}, "undetected_images": []})
    monkeypatch.setattr(main, "report_residual_gap_audit", lambda audit: calls.append("residual-report"))
    monkeypatch.setattr(main, "save_residual_gap_audit", lambda audit: calls.append("residual-save"))
    monkeypatch.setattr(main, "save_taxonomy_candidates", lambda metadata: None)
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: calls.append("save"))
    def generate_gallery(actual, cache):
        assert actual is entries
        assert actual == [
            {"alt": "ムキタケ", "src": "https://example.invalid/mukitake.jpg"}
        ]
        return {"ムキタケ": [actual[0]["src"]]}

    monkeypatch.setattr(main, "generate_gallery", generate_gallery)
    monkeypatch.setattr(
        main, "generate_index", lambda grouped, cache: calls.append("index")
    )
    monkeypatch.setattr(
        main, "generate_favorite_page", lambda grouped: calls.append("favorite")
    )

    main.build_gallery()

    assert calls == [
        "shadow-report",
        "shadow-save",
        "readiness-report",
        "readiness-save",
        "hybrid-report",
        "hybrid-save",
        "residual-report",
        "residual-save",
        "save",
        "index",
        "favorite",
    ]


@pytest.mark.parametrize("failing_step", ["report", "export"])
def test_residual_audit_failures_preserve_production_entries(monkeypatch, failing_step, capsys):
    entries = [{"alt": "legacy", "src": "x.jpg"}]
    generated = []
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries)
    monkeypatch.setattr(main, "extract_shadow_metadata", lambda files, **kwargs: [])
    monkeypatch.setattr(main, "report_category_inventory", lambda files: None)
    monkeypatch.setattr(main, "report_shadow_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "save_taxonomy_candidates", lambda data: None)
    monkeypatch.setattr(main, "save_shadow_metadata", lambda data: None)
    monkeypatch.setattr(main, "build_residual_gap_audit", lambda files, data: {"summary": {}, "undetected_images": []})
    monkeypatch.setattr(main, "report_residual_gap_audit", lambda audit: (_ for _ in ()).throw(RuntimeError("report")) if failing_step == "report" else None)
    monkeypatch.setattr(main, "save_residual_gap_audit", lambda audit: (_ for _ in ()).throw(OSError("export")) if failing_step == "export" else None)
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: None)
    monkeypatch.setattr(main, "generate_gallery", lambda actual, cache: generated.append(actual) or {})
    monkeypatch.setattr(main, "generate_index", lambda grouped, cache: None)
    monkeypatch.setattr(main, "generate_favorite_page", lambda grouped: None)

    main.build_gallery()

    assert generated == [entries]
    assert generated[0] is entries
    expected = "audit failed: report" if failing_step == "report" else "audit export failed: export"
    assert expected in capsys.readouterr().out


def test_shadow_failure_is_logged_without_blocking_production(monkeypatch, capsys):
    entries = [{"alt": "ムキタケ", "src": "https://example.invalid/image.jpg"}]
    generated = []
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries)
    monkeypatch.setattr(
        main,
        "extract_shadow_metadata",
        lambda files, **kwargs: (_ for _ in ()).throw(ValueError("broken shadow")),
    )
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: None)
    monkeypatch.setattr(
        main,
        "generate_gallery",
        lambda actual, cache: generated.append(actual) or {"ムキタケ": []},
    )
    monkeypatch.setattr(main, "generate_index", lambda grouped, cache: None)
    monkeypatch.setattr(main, "generate_favorite_page", lambda grouped: None)

    main.build_gallery()

    assert generated == [entries]
    assert (
            "Phase 3B.2 shadow audit failed: broken shadow"
        in capsys.readouterr().out
    )


def _readiness_row(src, label, subject_type, gallery_name, *, alt="legacy", reason=None,
                   path="articles/a.html"):
    return {
        "src": src, "detected_label": label, "subject_type": subject_type,
        "gallery_name": gallery_name, "legacy_alt": alt,
        "classification_reason": reason or f"taxonomy_{subject_type}",
        "taxonomy_match_type": "canonical_exact" if subject_type != "review" else "none",
        "article_title": "Article", "article_path": path,
        "subject_state_status": "accepted_subject" if label is not None else "no_subject",
        "subject_source_block_text": label,
    }


def test_phase3c_hybrid_preview_policy_occurrences_groups_and_metadata():
    legacy = [
        {"src": "same.jpg", "alt": "Same"},
        {"src": "rename.jpg", "alt": "Old"},
        {"src": "review.jpg", "alt": "Review legacy"},
        {"src": "none.jpg", "alt": "Undetected legacy"},
        {"src": "missing.jpg", "alt": "Missing legacy"},
        {"src": "remove.jpg", "alt": "Bird legacy"},
        {"src": "duplicate.jpg", "alt": "First legacy"},
        {"src": "duplicate.jpg", "alt": "Second legacy"},
    ]
    shadow = [
        _readiness_row("same.jpg", "Same", "mushroom", "Same"),
        _readiness_row("rename.jpg", "Old", "mushroom", "New"),
        _readiness_row("review.jpg", "Unknown", "review", None,
                       reason="taxonomy_unmatched"),
        _readiness_row("none.jpg", None, "review", None,
                       reason="no_detected_label"),
        _readiness_row("remove.jpg", "Bird", "non_mushroom", None),
        _readiness_row("duplicate.jpg", "First legacy", "mushroom", "Duplicate new"),
        _readiness_row("duplicate.jpg", "Insect", "non_mushroom", None),
        _readiness_row("new.jpg", "Added", "mushroom", "Added"),
        _readiness_row("new-review.jpg", "Maybe", "review", None),
        _readiness_row("new-none.jpg", None, "review", None,
                       reason="no_detected_label"),
        _readiness_row("new-bird.jpg", "Bird", "non_mushroom", None),
        _readiness_row("new2.jpg", "Added", "mushroom", "Added",
                       path="articles/b.html"),
    ]
    shadow[1]["taxonomy_canonical_name"] = "New"
    metadata = {
        "articles/a.html": {"title": "Title", "url": "https://example/a",
                            "article_id": "a", "published": "2026-01-01"},
        "articles/b.html": {"title": "Other", "url": "https://example/b",
                            "article_id": "b", "published": "2026-01-02"},
    }

    hybrid, report = main.build_phase3c_hybrid_preview(legacy, shadow, metadata)

    assert hybrid == [
        {"src": "same.jpg", "alt": "Same"},
        {"src": "rename.jpg", "alt": "New"},
        {"src": "review.jpg", "alt": "Review legacy"},
        {"src": "none.jpg", "alt": "Undetected legacy"},
        {"src": "missing.jpg", "alt": "Missing legacy"},
        {"src": "duplicate.jpg", "alt": "Duplicate new"},
        {"src": "new.jpg", "alt": "Added"},
        {"src": "new2.jpg", "alt": "Added"},
    ]
    assert report["renamed_occurrences"][0]["article_url"] == "https://example/a"
    assert report["renamed_occurrences"][0]["article_id"] == "a"
    assert report["legacy_fallback_review"][0]["classification_reason"] == "taxonomy_unmatched"
    assert report["legacy_fallback_shadow_missing"][0]["decision"] == "legacy_fallback_shadow_missing"
    assert [row["src"] for row in report["removed_non_mushroom"]] == [
        "remove.jpg", "duplicate.jpg"
    ]
    assert len(report["new_review_excluded"]) == 1
    assert len(report["new_undetected_excluded"]) == 1
    assert len(report["new_non_mushroom_excluded"]) == 1
    assert report["rename_groups"][0]["image_count"] == 1
    assert report["added_groups"] == [{
        "gallery_name": "Added", "image_count": 2, "article_count": 2,
        "sample_srcs": ["new.jpg", "new2.jpg"],
        "sample_article_urls": ["https://example/a", "https://example/b"],
    }]
    assert report["summary"] == {
        "legacy_image_count": 8, "hybrid_image_count": 8, "net_image_delta": 0,
        "legacy_preserved_exact_count": 4,
        "confirmed_mushroom_same_name_count": 1,
        "confirmed_mushroom_renamed_count": 2,
        "review_legacy_fallback_count": 1,
        "undetected_legacy_fallback_count": 1,
        "shadow_missing_legacy_fallback_count": 1,
        "confirmed_non_mushroom_removed_count": 2,
        "confirmed_new_mushroom_added_count": 2,
        "new_review_excluded_count": 1,
        "new_undetected_excluded_count": 1,
        "new_non_mushroom_excluded_count": 1,
        "hybrid_unique_names": 7, "rename_group_count": 2,
        "added_gallery_name_count": 1,
        "compatible_rename_count": 2,
        "rename_conflict_count": 0,
        "rename_conflict_group_count": 0,
        "rejected_subject_boundary_count": 0,
        "images_blocked_by_rejected_boundary_count": 0,
        "new_boundary_blocked_excluded_count": 0,
    }


def test_phase3c_hybrid_preview_schema_and_group_sort(tmp_path, monkeypatch):
    target = tmp_path / "output" / "phase3c-hybrid-preview.json"
    monkeypatch.setattr(main, "PHASE3C_HYBRID_PREVIEW_FILE", str(target))
    monkeypatch.setattr(main, "OUTPUT_DIR", str(target.parent))
    legacy = [
        {"src": "a.jpg", "alt": "Old"}, {"src": "b.jpg", "alt": "Old"},
        {"src": "c.jpg", "alt": "Other"},
    ]
    shadow = [
        _readiness_row("a.jpg", "Old", "mushroom", "New"),
        _readiness_row("b.jpg", "Old", "mushroom", "New"),
        _readiness_row("c.jpg", "Other", "mushroom", "Third"),
    ]
    _, report = main.build_phase3c_hybrid_preview(legacy, shadow)
    main.save_phase3c_hybrid_preview(report)
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert set(saved) == {
        "version", "summary", "rename_groups", "renamed_occurrences",
        "added_groups", "added_occurrences", "removed_non_mushroom",
        "legacy_fallback_review", "legacy_fallback_undetected",
        "legacy_fallback_shadow_missing", "new_review_excluded",
        "new_undetected_excluded", "new_non_mushroom_excluded",
        "new_boundary_blocked_excluded", "rename_conflicts",
        "rename_conflict_groups", "rejected_subject_boundaries",
        "readiness_notes",
    }
    assert [row["image_count"] for row in saved["rename_groups"]] == [2, 1]


def test_phase3c_hybrid_rename_guard_and_new_boundary_safety():
    legacy = [
        {"src": "unknown.jpg", "alt": "チャアミガサタケ？"},
        {"src": "broad.jpg", "alt": "ヤマドリタケモドキ(広義)"},
        {"src": "conflict.jpg", "alt": "アシボソアミガサタケ？"},
    ]
    shadow = [
        _readiness_row("unknown.jpg", "チャアミガサタケ？", "mushroom", "不明"),
        _readiness_row("broad.jpg", "ヤマドリタケモドキ(広義)", "mushroom",
                       "ヤマドリタケモドキ"),
        _readiness_row("conflict.jpg", "トガリアミガサタケ", "mushroom",
                       "トガリアミガサタケ"),
        _readiness_row("new.jpg", "シイタケ", "mushroom", "シイタケ", alt=""),
        _readiness_row("blocked.jpg", None, "review", None, alt=""),
        _readiness_row("resumed.jpg", "ムキタケ", "mushroom", "ムキタケ", alt=""),
    ]
    shadow[2]["taxonomy_canonical_name"] = "トガリアミガサタケ"
    shadow[2]["dom_context"] = {"containing_block": None, "previous_blocks": [],
                                 "next_blocks": []}
    shadow[4].update({
        "subject_state_status": "reset_by_rejected_boundary",
        "last_rejected_boundary_text": "ベニタケの仲間",
        "last_rejected_boundary_reason": "family_or_group_heading",
    })

    hybrid, report = main.build_phase3c_hybrid_preview(legacy, shadow)

    assert hybrid == [
        {"src": "unknown.jpg", "alt": "不明"},
        {"src": "broad.jpg", "alt": "ヤマドリタケモドキ"},
        {"src": "conflict.jpg", "alt": "アシボソアミガサタケ？"},
        {"src": "new.jpg", "alt": "シイタケ"},
        {"src": "resumed.jpg", "alt": "ムキタケ"},
    ]
    assert report["summary"]["compatible_rename_count"] == 2
    assert report["summary"]["rename_conflict_count"] == 1
    assert report["rename_conflicts"][0]["decision"] == "rename_conflict_manual_review"
    assert report["rename_conflicts"][0]["proposed_hybrid_alt"] == "トガリアミガサタケ"
    assert [row["src"] for row in report["new_boundary_blocked_excluded"]] == [
        "blocked.jpg"
    ]


def test_phase3c_readiness_candidate_multisets_and_classifications():
    legacy = [
        {"src": "same.jpg", "alt": "疑問符名？"},
        {"src": "duplicate.jpg", "alt": "旧名"},
        {"src": "duplicate.jpg", "alt": "旧名"},
        {"src": "legacy-only.jpg", "alt": "旧"},
    ]
    shadow = [
        _readiness_row("same.jpg", "疑問符名？", "mushroom", "不明", alt="疑問符名？"),
        _readiness_row("duplicate.jpg", "新名", "mushroom", "新名", alt="旧名"),
        _readiness_row("duplicate.jpg", "新名", "mushroom", "新名", alt="旧名"),
        _readiness_row("new.jpg", "ムキタケ", "mushroom", "ムキタケ", alt=""),
        _readiness_row("bird.jpg", "鳥", "non_mushroom", None),
        _readiness_row("review-z.jpg", "未登録Z", "review", None,
                       reason="taxonomy_unmatched", path="articles/z.html"),
        _readiness_row("review-a1.jpg", "未登録A", "review", None,
                       reason="taxonomy_unmatched", path="articles/a.html"),
        _readiness_row("review-a2.jpg", "未登録A", "review", None,
                       reason="taxonomy_unmatched", path="articles/b.html"),
        _readiness_row("none.jpg", None, "review", None,
                       reason="no_detected_label"),
    ]

    audit = main.build_phase3c_readiness(legacy, shadow)

    assert audit["version"] == 1
    assert [(row["src"], row["gallery_name"]) for row in audit["candidate_only"]] == [
        ("same.jpg", "不明"), ("duplicate.jpg", "新名"),
        ("duplicate.jpg", "新名"), ("new.jpg", "ムキタケ"),
    ]
    assert not {"bird.jpg", "review-z.jpg", "none.jpg"} & {
        row["src"] for row in audit["candidate_only"]
    }
    assert [row["detected_label"] for row in audit["blocked_review_labels"]] == [
        "未登録A", "未登録Z"
    ]
    assert audit["blocked_review_labels"][0]["article_count"] == 2
    assert len(audit["legacy_only"]) == 4
    assert sum(row["src"] == "duplicate.jpg" for row in audit["legacy_only"]) == 2
    assert {row["src"] for row in audit["name_changes"]} == {"same.jpg", "duplicate.jpg"}
    assert audit["summary"]["legacy_src_only_count"] == 1
    assert audit["summary"]["candidate_src_only_count"] == 1
    assert audit["summary"]["same_src_name_change_count"] == 2
    assert audit["non_mushroom_exclusions"][0]["detected_label"] == "鳥"
    assert audit["undetected"] == [{
        "src": "none.jpg", "legacy_alt": "legacy", "article_title": "Article",
        "article_path": "articles/a.html", "classification_reason": "no_detected_label",
    }]


def test_phase3c_readiness_json_schema(tmp_path, monkeypatch):
    target = tmp_path / "output" / "phase3c-readiness.json"
    monkeypatch.setattr(main, "PHASE3C_READINESS_FILE", str(target))
    monkeypatch.setattr(main, "OUTPUT_DIR", str(target.parent))
    audit = main.build_phase3c_readiness([], [])

    main.save_phase3c_readiness(audit)

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert set(saved) == {"version", "summary", "blocked_review_labels", "legacy_only",
                          "candidate_only", "name_changes", "non_mushroom_exclusions",
                          "undetected", "readiness_notes"}
    assert saved["summary"]["candidate_vs_legacy_ratio"] is None
    assert saved["summary"]["taxonomy_mushroom_share_of_shadow"] is None


def test_phase3c_audit_failure_preserves_exact_production_entries(monkeypatch, capsys):
    entries = [{"alt": "legacy", "src": "x.jpg"}]
    generated = []
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries)
    monkeypatch.setattr(main, "extract_shadow_metadata", lambda files, **kwargs: [])
    monkeypatch.setattr(main, "report_category_inventory", lambda files: None)
    monkeypatch.setattr(main, "report_shadow_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "save_taxonomy_candidates", lambda data: None)
    monkeypatch.setattr(main, "save_shadow_metadata", lambda data: None)
    monkeypatch.setattr(main, "build_phase3c_readiness",
                        lambda legacy, shadow: (_ for _ in ()).throw(RuntimeError("broken readiness")))
    monkeypatch.setattr(main, "build_residual_gap_audit",
                        lambda files, data: {"summary": {}, "undetected_images": []})
    monkeypatch.setattr(main, "report_residual_gap_audit", lambda audit: None)
    monkeypatch.setattr(main, "save_residual_gap_audit", lambda audit: None)
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: None)
    monkeypatch.setattr(main, "generate_gallery", lambda actual, cache: generated.append(actual) or {})
    monkeypatch.setattr(main, "generate_index", lambda grouped, cache: None)
    monkeypatch.setattr(main, "generate_favorite_page", lambda grouped: None)

    main.build_gallery()

    assert generated == [entries]
    assert generated[0] is entries
    assert "Phase 3C.0 readiness audit failed: broken readiness" in capsys.readouterr().out


@pytest.mark.parametrize("failing_step", ["build", "report", "save"])
def test_phase3c_hybrid_failure_preserves_exact_production_entries(
    monkeypatch, capsys, failing_step
):
    entries = [{"alt": "legacy", "src": "x.jpg"}]
    generated = []
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries)
    monkeypatch.setattr(main, "extract_shadow_metadata", lambda files, **kwargs: [])
    monkeypatch.setattr(main, "report_category_inventory", lambda files: None)
    monkeypatch.setattr(main, "report_shadow_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "save_taxonomy_candidates", lambda data: None)
    monkeypatch.setattr(main, "save_shadow_metadata", lambda data: None)
    monkeypatch.setattr(main, "build_phase3c_readiness",
                        lambda legacy, shadow: {"summary": {}, "blocked_review_labels": []})
    monkeypatch.setattr(main, "report_phase3c_readiness", lambda audit: None)
    monkeypatch.setattr(main, "save_phase3c_readiness", lambda audit: None)
    monkeypatch.setattr(main, "load_article_metadata", lambda: {})
    report = {"summary": {}, "rename_groups": [], "added_groups": []}
    monkeypatch.setattr(
        main, "build_phase3c_hybrid_preview",
        lambda *args: (_ for _ in ()).throw(RuntimeError("build"))
        if failing_step == "build" else ([], report),
    )
    monkeypatch.setattr(
        main, "report_phase3c_hybrid_preview",
        lambda audit: (_ for _ in ()).throw(RuntimeError("report"))
        if failing_step == "report" else None,
    )
    monkeypatch.setattr(
        main, "save_phase3c_hybrid_preview",
        lambda audit: (_ for _ in ()).throw(RuntimeError("save"))
        if failing_step == "save" else None,
    )
    monkeypatch.setattr(main, "build_residual_gap_audit",
                        lambda files, data: {"summary": {}, "undetected_images": []})
    monkeypatch.setattr(main, "report_residual_gap_audit", lambda audit: None)
    monkeypatch.setattr(main, "save_residual_gap_audit", lambda audit: None)
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: None)
    monkeypatch.setattr(main, "generate_gallery",
                        lambda actual, cache: generated.append(actual) or {})
    monkeypatch.setattr(main, "generate_index", lambda grouped, cache: None)
    monkeypatch.setattr(main, "generate_favorite_page", lambda grouped: None)

    main.build_gallery()

    assert generated == [entries]
    assert generated[0] is entries
    assert f"Phase 3C.2 guarded hybrid preview failed: {failing_step}" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("iso_values", "expected"),
    [
        (
            {
                "ISOSpeedRatings": 100,
                "ISOSpeed": 200,
                "StandardOutputSensitivity": 400,
                "RecommendedExposureIndex": 800,
            },
            "100",
        ),
        ({"ISOSpeed": 200}, "200"),
        ({"StandardOutputSensitivity": 400}, "400"),
        ({"RecommendedExposureIndex": 800}, "800"),
    ],
)
def test_extract_exif_uses_supported_iso_tags_in_priority_order(
    monkeypatch, iso_values, expected
):
    exif = {
        getattr(main.piexif.ExifIFD, name): value
        for name, value in iso_values.items()
    }
    monkeypatch.setattr(
        main.piexif, "load", lambda content: {"0th": {}, "Exif": exif}
    )

    assert main.extract_exif_from_bytes(b"jpeg")["iso"] == expected


def test_extract_exif_without_iso_preserves_other_fields(monkeypatch):
    monkeypatch.setattr(
        main.piexif,
        "load",
        lambda content: {
            "0th": {main.piexif.ImageIFD.Model: b"Test Camera"},
            "Exif": {
                main.piexif.ExifIFD.LensModel: b"Test Lens",
                main.piexif.ExifIFD.FNumber: (28, 10),
                main.piexif.ExifIFD.ExposureTime: (1, 125),
                main.piexif.ExifIFD.FocalLength: (50, 1),
                main.piexif.ExifIFD.DateTimeOriginal: b"2026:09:23 12:34:56",
            },
        },
    )

    assert main.extract_exif_from_bytes(b"jpeg") == {
        "model": "Test Camera",
        "lens": "Test Lens",
        "iso": "",
        "f": "f/2.8",
        "exposure": "1/125",
        "focal": "50mm",
        "date": "2026/09/23",
    }


@pytest.mark.parametrize("empty_value", [[], ()])
def test_extract_exif_skips_empty_iso_sequences(monkeypatch, empty_value):
    monkeypatch.setattr(
        main.piexif,
        "load",
        lambda content: {
            "0th": {},
            "Exif": {
                main.piexif.ExifIFD.ISOSpeedRatings: empty_value,
                main.piexif.ExifIFD.ISOSpeed: (640,),
            },
        },
    )

    assert main.extract_exif_from_bytes(b"jpeg")["iso"] == "640"


def test_extract_exif_skips_iso_tag_constants_missing_from_piexif(monkeypatch):
    monkeypatch.delattr(main.piexif.ExifIFD, "ISOSpeedRatings")
    monkeypatch.setattr(
        main.piexif,
        "load",
        lambda content: {
            "0th": {},
            "Exif": {main.piexif.ExifIFD.ISOSpeed: 320},
        },
    )

    assert main.extract_exif_from_bytes(b"jpeg")["iso"] == "320"


def test_exif_cache_hit_does_not_download(monkeypatch, tmp_path, capsys):
    src = "https://example.invalid/cached.jpg"
    cache = {src: {"model": "cached camera"}}
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(
        main.requests,
        "get",
        lambda *args, **kwargs: pytest.fail("cached URL must not be downloaded"),
    )

    result = main.build_exif_cache([{"src": src}, {"src": src}], cache)

    assert result is cache
    assert result[src] == {"model": "cached camera"}
    assert "total=1\nhits=1\nfetched=0\nfailed=0" in capsys.readouterr().out


def test_http_200_with_exif_is_cached(monkeypatch, tmp_path):
    src = "https://example.invalid/with-exif.jpg"
    response = type("Response", (), {"status_code": 200, "content": b"jpeg"})()
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(
        main, "extract_exif_from_bytes", lambda content: {"model": "test camera"}
    )

    result = main.build_exif_cache([{"src": src}], {})

    assert result[src] == {"model": "test camera"}


def test_http_200_without_exif_is_cached_and_not_downloaded_again(
    monkeypatch, tmp_path
):
    src = "https://example.invalid/no-exif.jpg"
    response = type("Response", (), {"status_code": 200, "content": b"jpeg"})()
    calls = []
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(
        main.requests, "get", lambda *args, **kwargs: calls.append(src) or response
    )
    monkeypatch.setattr(main, "extract_exif_from_bytes", lambda content: {})

    cache = main.build_exif_cache([{"src": src}], {})
    main.build_exif_cache([{"src": src}], cache)

    assert cache[src] == {}
    assert calls == [src]


@pytest.mark.parametrize("status_code", [404, 500])
def test_http_error_is_not_cached(monkeypatch, tmp_path, status_code):
    src = f"https://example.invalid/{status_code}.jpg"
    response = type("Response", (), {"status_code": status_code, "content": b""})()
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: response)

    result = main.build_exif_cache([{"src": src}], {})

    assert src not in result


def test_request_exception_is_not_cached(monkeypatch, tmp_path):
    src = "https://example.invalid/network-error.jpg"
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))

    def raise_network_error(*args, **kwargs):
        raise main.requests.RequestException("temporary failure")

    monkeypatch.setattr(main.requests, "get", raise_network_error)

    result = main.build_exif_cache([{"src": src}], {})

    assert src not in result


def test_exif_cache_summary_counts_unique_urls(monkeypatch, tmp_path, capsys):
    cached = "https://example.invalid/cached.jpg"
    fetched = "https://example.invalid/fetched.jpg"
    failed = "https://example.invalid/failed.jpg"
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))

    def get(url, timeout):
        if url == fetched:
            return type("Response", (), {"status_code": 200, "content": b"jpeg"})()
        return type("Response", (), {"status_code": 503, "content": b""})()

    monkeypatch.setattr(main.requests, "get", get)
    monkeypatch.setattr(main, "extract_exif_from_bytes", lambda content: {})
    entries = [{"src": cached}, {"src": fetched}, {"src": failed}, {"src": cached}]

    main.build_exif_cache(entries, {cached: {}})

    assert "total=3\nhits=1\nfetched=1\nfailed=1" in capsys.readouterr().out
