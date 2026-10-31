"""Regenerate both revisions from immutable published inputs, without daily sync."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import types
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import requests
from bs4 import BeautifulSoup
import main
from comments_integration_protection import assert_reviewed_source
from best_shot_ui import generate_best_shot_pages
from detail_ui import build_detail_views
from records_ui import build_observation_records, generate_records_page
from research_ui import generate_research_page
from season_ui import generate_season_page

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
base = sys.argv[2] if len(sys.argv) > 2 else 'origin/main'
repo = Path(__file__).resolve().parents[2]
git = lambda *args: subprocess.check_output(['git', *args], cwd=repo)
with tarfile.open(fileobj=io.BytesIO(git('archive', 'origin/gh-pages'))) as archive:
    archive.extractall(root / 'published', filter='data')
portal = json.loads((root / 'published/portal-data.json').read_text())
records = build_observation_records(portal)
entries = [{'alt': o['gallery_name'], 'src': o['src']} for o in portal['observations']]
exif = {o['src']: dict((o.get('capture') or {}).get('camera') or {},
                       date=((o.get('capture') or {}).get('date') or '').replace('-', '/'))
        for o in portal['observations']}
# Preserve HTML-only cross-subject references from the published pages as well.
base_grouped = defaultdict(set)
for e in entries: base_grouped[e['alt']].add(e['src'])
overlays = {}
for p in (root / 'published').glob('*.html'):
    soup = BeautifulSoup(p.read_text(), 'html.parser')
    title = soup.select_one('.detail-hero h2')
    if title:
        extra = [a['href'] for a in soup.select('.gallery a.gallery-item[href]')
                 if a['href'] not in base_grouped[title.text]]
        if extra: overlays[title.text] = extra
views = build_detail_views(portal)
feature = main.validate_feature_production_state()
assert feature['mushroom_master'] == portal['reference_data']['mushroom_master']
manifest = json.loads((repo / 'audit/ai-image-refresh-20261031/artwork-manifest.json').read_text())
before = types.ModuleType('artwork_baseline_main')
before.__file__ = main.__file__
sys.modules[before.__name__] = before
exec(compile(git('show', f'{base}:main.py'), main.__file__, 'exec'), before.__dict__)
for variant, module in [('before', before), ('after', main)]:
    out = root / variant
    shutil.copytree(root / 'published', out, dirs_exist_ok=True)
    module.OUTPUT_DIR = str(out)
    with contextlib.redirect_stdout(io.StringIO()):
        grouped = module.generate_gallery(entries, exif, detail_views=views, multi_subject_overlays=overlays)
        generate_season_page(portal, out, repo / 'assets', module.safe_filename)
        generate_records_page(portal, out, repo / 'assets')
        module._write_feature_page(portal, feature['feature_facets'], out, repo / 'assets', module.safe_filename)
        research = generate_research_page(portal, out, repo / 'assets')
        best = generate_best_shot_pages(portal, repo / 'data/best-shots.json', out, repo / 'assets')
        module.generate_index(grouped, exif, observation_records=records, feature_search_available=True,
                              research_summary=research, best_shot_summary=best, detail_views=views)
        module.generate_new_top(grouped, exif, observation_records=records, feature_search_available=True,
                                research_summary=research, best_shot_summary=best)
        module.generate_favorite_page(grouped)
    if variant == 'before':
        for p in (repo / 'assets').glob('*.css'):
            (out / 'assets' / p.name).write_bytes(git('show', f'{base}:assets/{p.name}'))
        for record in manifest['assets']:
            asset = 'assets/' + record['asset']
            # A later integration baseline already contains the approved artwork.
            # Keep it when tracked there; original replacement baselines lack it.
            if subprocess.run(['git','cat-file','-e',f'{base}:{asset}'],cwd=repo,
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
                (out / asset).unlink(missing_ok=True)
# All generated content, links, photos and captions must be identical: only paint changes.
html_files = sorted((root / 'after').glob('*.html'))
assert html_files
for p in html_files:
    assert p.read_bytes() == (root / 'before' / p.name).read_bytes(), p.name
old = set(manifest['replacements'])
new = {a['asset'] for a in manifest['assets']}
remaining = []
for p in (root / 'after').rglob('*'):
    if p.suffix in ('.html', '.css', '.js', '.json'):
        content = p.read_text()
        remaining.extend((str(p.relative_to(root / 'after')), name) for name in old if name in content)
assert not remaining, remaining
coverage = {}
for p in html_files:
    soup = BeautifulSoup(p.read_text(), 'html.parser')
    names = set()
    for link in soup.select('link[rel=stylesheet][href]'):
        css = root / 'after' / link['href']
        if css.is_file(): names.update(name for name in new if name in css.read_text())
    if names: coverage[p.name] = sorted(names)
assert len(coverage) > 300
for asset in new:
    assert any(asset in names for names in coverage.values()), asset
changed_styles = set(manifest['css_non_artwork_sha256'])
protected = [p for p in git('ls-tree','-rz','--name-only',base).decode().split('\0') if p and
             p != 'main.py' and p not in changed_styles and
             not p.startswith(('.github/','audit/','tests/','docs/','tools/'))]
hashes = {}
for p in protected:
    before_bytes = git('show', f'{base}:{p}')
    assert_reviewed_source(base, p, (repo / p).read_bytes())
    hashes[p] = hashlib.sha256(before_bytes).hexdigest()
for p in ('portal-data.json','article-sync-snapshot.json','research-comment-cases.json','research-comments-config.json'):
    assert (root/'published'/p).read_bytes() == (root/'after'/p).read_bytes(), p
config = json.loads((root/'after/research-comments-config.json').read_text())
assert config['enabled'] is False
(root/'screenshots').mkdir(exist_ok=True)
(root/'vendor').mkdir(exist_ok=True)
for p in (repo/'lightgallery').rglob('*'):
    if p.is_file(): shutil.copy2(p, root/'vendor'/p.name)
r=requests.get('https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js',timeout=30)
r.raise_for_status();assert len(r.content)>1000
(root/'vendor/imagesloaded.pkgd.min.js').write_bytes(r.content)
result = {'base_main':git('rev-parse',base).decode().strip(), 'published':git('rev-parse','origin/gh-pages').decode().strip(),
          'generated_html_count':len(html_files),'identical_html_before_after':True,'old_display_references':remaining,
          'pages_with_new_artwork':len(coverage),'coverage':coverage,'protected_source_files':len(protected),
          'protected_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
          'published_portal_sha256':hashlib.sha256((root/'after/portal-data.json').read_bytes()).hexdigest(),
          'counts':{'photos':len(portal['observations']),'best_shots':best['entry_count'],'research':research['case_count'],
                    'notices':len(json.loads((repo/'data/update-notices.json').read_text())['events']),
                    'master':len(portal['reference_data']['mushroom_master']['entries']),
                    'sources':len(portal['reference_data']['sources']['sources'])}}
(root/'artwork-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(root/'reference-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='coverage'},ensure_ascii=False))
