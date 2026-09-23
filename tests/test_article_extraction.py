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
    assert metadata[6]["gallery_name"] == "不明"
    assert metadata[7]["detected_label"] == "クダアカゲシメジ？"
    assert metadata[7]["confidence"] == "high"
    assert metadata[8]["detected_label"] == "キハツダケ"
    assert all(item["subject_type"] == "review" for item in metadata)
    assert all(item["source"] == "standalone_text_state" for item in metadata)
    assert all(
        item["article_path"].endswith("article_metadata_state.html")
        for item in metadata
    )


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


def test_unknown_gallery_mapping_preserves_detected_label():
    assert main.normalize_gallery_name("クダアカゲシメジ?") == "不明"
    assert main.normalize_gallery_name("クダアカゲシメジ？") == "不明"
    assert main.normalize_gallery_name("種類不明") == "不明"
    assert main.normalize_gallery_name("ムキタケ") == "ムキタケ"


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
    assert metadata[1]["gallery_name"] == "不明"
    assert metadata[3]["gallery_name"] == "不明"


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
        "unknown_mapped": 2,
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

    assert "Phase 3B.1 metadata shadow summary:" in output
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
    ("label", "categories", "expected"),
    [
        ("ムキタケ", ["キノコ"], ("review", "explicit_mushroom_category_review", "low")),
        ("ムキタケ", ["キノコ探索日記"], ("review", "mushroom_context_only", "low")),
        ("コブハクチョウ", ["キノコ探索日記"], ("review", "mushroom_context_only", "low")),
        ("コブハクチョウ", ["野鳥"], ("non_mushroom", "explicit_non_mushroom_category", "high")),
        ("コブハクチョウ", [], ("review", "no_category_signal", "low")),
        ("ムキタケ", ["キノコ", "野鳥"], ("review", "conflicting_category_signals", "low")),
        (None, ["キノコ"], ("review", "no_detected_label", "low")),
    ],
)
def test_category_aware_classification(label, categories, expected):
    assert main.classify_subject_type(label, categories) == expected


def test_shadow_metadata_uses_metadata_for_classification_without_changing_confidence():
    path = FIXTURES / "article_metadata_state.html"
    article_metadata = {
        str(path): {"article_id": "entry-1", "title": "Birds", "categories": ["野鳥"]}
    }
    metadata = main.extract_shadow_metadata([path], article_metadata)
    assert metadata[1]["subject_type"] == "non_mushroom"
    assert metadata[1]["classification_confidence"] == "high"
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
        lambda files: [{"shadow": True}] if files else [],
    )
    monkeypatch.setattr(
        main, "report_shadow_metadata", lambda metadata, **kwargs: calls.append("shadow-report")
    )
    monkeypatch.setattr(
        main, "save_shadow_metadata", lambda metadata: calls.append("shadow-save")
    )
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
        "save",
        "index",
        "favorite",
    ]


def test_shadow_failure_is_logged_without_blocking_production(monkeypatch, capsys):
    entries = [{"alt": "ムキタケ", "src": "https://example.invalid/image.jpg"}]
    generated = []
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries)
    monkeypatch.setattr(
        main,
        "extract_shadow_metadata",
        lambda files: (_ for _ in ()).throw(ValueError("broken shadow")),
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
        "Phase 3B.1 shadow audit failed: broken shadow"
        in capsys.readouterr().out
    )


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
