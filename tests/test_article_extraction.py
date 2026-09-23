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
