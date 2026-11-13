"""Read-only published snapshot plus candidate render; never runs daily sync."""
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import best_shot_ui
import requests

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
repo = Path(__file__).resolve().parents[2]
# Replay the old dialog/star layout and the pre-toolbar LightGallery separately.
# The current published snapshot already contains the accepted toolbar CSS.
baseline = sys.argv[2] if len(sys.argv) > 2 else '3de2dc74d1d48813d9ed411e88e4ce74f3d9784c'
pre_toolbar = sys.argv[3] if len(sys.argv) > 3 else 'ae08f456729e7d89619af9569b7daecdd85080cd'
for variant, ref in [('historical', baseline), ('before', pre_toolbar), ('after', 'origin/gh-pages')]:
    with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git', 'archive', ref]))) as archive:
        archive.extractall(root / variant, filter='data')
for name in ['gallery.js', 'gallery.css', 'record-stars.js', 'record-stars.css']:
    shutil.copy2(repo / 'assets' / name, root / 'after/assets' / name)
portal = json.loads((root / 'after/portal-data.json').read_text())
best_shot_ui.generate_best_shot_pages(portal, repo / 'data/best-shots.json', root / 'after', repo / 'assets')
(root / 'vendor').mkdir(exist_ok=True)
for name in ['lightgallery.min.js', 'lightgallery-bundle.min.css', 'lg-zoom.min.js', 'lg-thumbnail.min.js', 'lg-share.min.js', 'lg-autoplay.min.js']:
    shutil.copy2(repo / 'lightgallery' / name, root / 'vendor' / name)
for file in (repo / 'lightgallery/fonts').glob('lg.*'):
    shutil.copy2(file, root / 'vendor' / file.name)
r = requests.get('https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js', timeout=30)
r.raise_for_status()
assert len(r.content) > 1000
(root / 'vendor/imagesloaded.pkgd.min.js').write_bytes(r.content)
(root / 'screenshots').mkdir(exist_ok=True)
parent = (repo / 'hatena/release-2026-10-24/footer-managed.html').read_text()
handler = parent[parent.rfind('<script>'):]
scroll_lock = (repo / 'hatena/patches/lightgallery-overlay-scroll-lock-20261108.html').read_text()
parent_template = '''<!doctype html><meta charset=utf-8><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0}header{height:300px}iframe{width:100%;border:0}html{overflow-y:scroll}::-webkit-scrollbar{width:15px}</style><!-- HOST_SCROLL_STYLE --><header>Isolated parent replay</header><section id="kinoko-home-portal"><iframe id="photoGallery" title="child" src="CHILD_URL" sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-top-navigation-by-user-activation" scrolling="no"></iframe></section>''' + handler
(root / 'parent-before-template.html').write_text(parent_template)
(root / 'parent-template.html').write_text(parent_template + scroll_lock)
(root / 'manifest.json').write_text(json.dumps({
    'pre_toolbar_comparison': subprocess.check_output(['git', 'rev-parse', pre_toolbar], text=True).strip(),
    'historical_comparison': subprocess.check_output(['git', 'rev-parse', baseline], text=True).strip(),
    'main': subprocess.check_output(['git', 'rev-parse', 'origin/main'], text=True).strip(),
    'published': subprocess.check_output(['git', 'rev-parse', 'origin/gh-pages'], text=True).strip(),
    'best_shots': len(json.loads((repo / 'data/best-shots.json').read_text())['entries']),
    'published_star_styles_match_candidate': (
        (root / 'historical/assets/record-stars.css').read_bytes() ==
        (repo / 'assets/record-stars.css').read_bytes() and
        (root / 'historical/assets/record-stars.js').read_bytes() ==
        (repo / 'assets/record-stars.js').read_bytes()
    ),
}, indent=2))
print(root)
