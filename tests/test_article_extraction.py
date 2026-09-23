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
  <entry><content type="text/html">&lt;p&gt;first&lt;/p&gt;</content></entry>
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
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: calls.append("save"))
    monkeypatch.setattr(
        main, "generate_gallery", lambda actual, cache: {"ムキタケ": [actual[0]["src"]]}
    )
    monkeypatch.setattr(
        main, "generate_index", lambda grouped, cache: calls.append("index")
    )
    monkeypatch.setattr(
        main, "generate_favorite_page", lambda grouped: calls.append("favorite")
    )

    main.build_gallery()

    assert calls == ["save", "index", "favorite"]
