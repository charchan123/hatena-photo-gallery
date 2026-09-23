import importlib
import sys

import pytest


@pytest.fixture
def gallery(monkeypatch):
    monkeypatch.setenv("HATENA_USER", "test-user")
    monkeypatch.setenv("HATENA_BLOG_ID", "test-blog")
    monkeypatch.setenv("HATENA_API_KEY", "test-key")
    sys.modules.pop("main", None)
    return importlib.import_module("main")


def test_empty_article_files_stop_build(gallery):
    with pytest.raises(RuntimeError, match="0 件"):
        gallery.require_nonempty([], "記事が 0 件です")


def test_empty_entries_stop_build(gallery):
    with pytest.raises(RuntimeError, match="0 件"):
        gallery.require_nonempty([], "画像が 0 件です")


def test_nonempty_build_data_is_returned_unchanged(gallery):
    values = [{"alt": "タマゴタケ", "src": "https://example.test/image.jpg"}]

    assert gallery.require_nonempty(values, "unused") is values


def test_fetch_images_uses_only_given_article_files(gallery, tmp_path):
    article = tmp_path / "article.html"
    article.write_text(
        '<div class="entry-body"><img alt="タマゴタケ" src="image.jpg"></div>',
        encoding="utf-8",
    )

    assert gallery.fetch_images([str(article)]) == [
        {"alt": "タマゴタケ", "src": "image.jpg"}
    ]


def test_fetch_hatena_articles_returns_saved_files(gallery, monkeypatch, tmp_path):
    atom_feed = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><content type="html">&lt;p&gt;first&lt;/p&gt;</content></entry>
      <entry><content type="html">&lt;p&gt;second&lt;/p&gt;</content></entry>
    </feed>"""

    class Response:
        status_code = 200
        text = atom_feed

    monkeypatch.setattr(gallery, "ARTICLES_DIR", str(tmp_path))
    monkeypatch.setattr(gallery.requests, "get", lambda *args, **kwargs: Response())

    article_files = gallery.fetch_hatena_articles_api()

    assert article_files == [
        str(tmp_path / "article_1.html"),
        str(tmp_path / "article_2.html"),
    ]
    assert [tmp_path.joinpath(f"article_{i}.html").read_text(encoding="utf-8") for i in (1, 2)] == [
        "<p>first</p>",
        "<p>second</p>",
    ]
