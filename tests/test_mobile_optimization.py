import hashlib
from pathlib import Path
from bs4 import BeautifulSoup
import main
from best_shot_ui import _best_shots_hero

ROOT = Path(__file__).resolve().parents[1]


def test_hatena_baseline_and_article_rules_preserved():
    original = (ROOT / 'hatena/hatena-design-css-slimmed-2026-10-07.css').read_bytes()
    candidate = (ROOT / 'hatena/hatena-design-css-mobile-optimized-2026-10-09.css').read_bytes()
    assert hashlib.sha256(original).hexdigest() == '0158ad4f6b192abc8315903a7149be7ac5ed950253938f80b88329c1ae1f15c2'
    assert original.split(b'/* Shared')[0] == candidate.split(b'/* Shared')[0]
    article = b'body.page-entry:not(.static-page-new-top) {'
    assert original[original.index(article):] == candidate[candidate.index(article):]


def test_generated_kana_and_detail_navigation(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'OUTPUT_DIR', str(tmp_path))
    names = ['カエンタケ', 'キクラゲ', 'クリタケ', 'ケショウハツ', 'コウタケ']
    main.generate_gallery([{'alt': name, 'src': name + '.jpg'} for name in names], {}, detail_views={})
    page = BeautifulSoup((tmp_path / 'か行.html').read_text(), 'html.parser')
    assert [b.get_text(strip=True) for b in page.select('.kana-btn')] == ['すべて', 'カ', 'キ', 'ク', 'ケ', 'コ']
    detail = BeautifulSoup((tmp_path / 'カエンタケ.html').read_text(), 'html.parser')
    assert len(detail.select('.detail-aiuo-links a')) == 10
    assert detail.select_one('a[href="index.html"]')
    assert detail.select_one('script[src="assets/gallery.js"]')


def test_year_heading_preserves_words():
    for year in [2025, 2026, 2030]:
        page = BeautifulSoup(_best_shots_hero(f'{year}年のベストショット', '説明', year=year), 'html.parser')
        heading = page.select_one('h1')
        assert heading.get_text() == f'{year}年のベストショット'
        assert [s.get_text() for s in heading.select('span')] == [f'{year}年の', 'ベストショット']
        assert heading.select_one('wbr')


def test_camera_artwork_copied_for_guide(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'OUTPUT_DIR', str(tmp_path))
    main.generate_index({}, {})
    name = 'new-top-best-shots-camera-mushrooms.webp'
    assert (tmp_path / 'assets' / name).read_bytes() == (ROOT / 'assets' / name).read_bytes()
    assert name in (ROOT / 'assets/guide.css').read_text()
