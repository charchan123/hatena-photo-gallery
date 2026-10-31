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
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git', 'archive', 'origin/gh-pages']))) as archive:
    archive.extractall(root / 'before', filter='data')
shutil.copytree(root / 'before', root / 'after', dirs_exist_ok=True)
for name in ['gallery.js', 'record-stars.js', 'record-stars.css']:
    shutil.copy2(repo / 'assets' / name, root / 'after/assets' / name)
portal = json.loads((root / 'before/portal-data.json').read_text())
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
(root / 'parent-template.html').write_text('''<!doctype html><meta charset=utf-8><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0}header{height:300px}#kinoko-home-portal{margin:0}iframe{width:100%;border:0}html{overflow-y:scroll}</style><header>Isolated parent replay</header><section id="kinoko-home-portal"><iframe id="photoGallery" title="child" src="CHILD_URL" sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-top-navigation-by-user-activation" scrolling="no"></iframe></section>''' + handler)
(root / 'manifest.json').write_text(json.dumps({
    'main': subprocess.check_output(['git', 'rev-parse', 'origin/main'], text=True).strip(),
    'published': subprocess.check_output(['git', 'rev-parse', 'origin/gh-pages'], text=True).strip(),
    'best_shots': len(json.loads((repo / 'data/best-shots.json').read_text())['entries']),
}, indent=2))
print(root)
