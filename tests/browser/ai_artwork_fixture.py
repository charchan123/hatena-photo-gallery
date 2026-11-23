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
from lightgallery_css_guard import verify_gallery_css

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
manifest = json.loads((repo / 'audit/guide-image-refresh-20261102/artwork-manifest.json').read_text())
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
        for asset in git('ls-tree', '-r', '--name-only', base, 'assets').decode().splitlines():
            if asset.endswith('.css'):
                (out / asset).write_bytes(git('show', f'{base}:{asset}'))
        for record in manifest['assets']:
            asset = 'assets/' + record['asset']
            # Preserve artwork already tracked by the comparison baseline.
            # Only the new date-versioned asset is absent from this baseline.
            if subprocess.run(['git', 'cat-file', '-e', f'{base}:{asset}'], cwd=repo,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                (out / asset).unlink(missing_ok=True)
# Keep all non-Best-Shot HTML byte-identical. The explicitly approved
# exhibition changes Best Shot markup and paint, but not curated content.
html_files = sorted((root / 'after').glob('*.html'))
assert html_files
exhibition = (repo / 'audit/best-shot-exhibition-20261121/files.json').is_file()
def retained_best_shot_data(path):
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    cards = []
    for card in soup.select('.best-shot-card'):
        photo = card.select_one('a.best-shot-photo')
        image = photo.select_one('img')
        article = card.select_one('a.best-shot-article')
        assert photo and image and card.select_one('h3')
        cards.append({
            'id': card['data-selection-id'],
            'image': (photo['href'], image['src'], image['alt']),
            'caption': BeautifulSoup(photo.get('data-sub-html', ''), 'html.parser').get_text(),
            'name': card.select_one('h3').get_text(),
            'meta': [n.get_text() for n in card.select('.best-shot-meta')],
            'comment': card.select_one('.best-shot-comment').get_text(),
            'article': (article['href'], article.get('title'), article.get_text()) if article else None,
            'badge': bool(card.select_one('.best-shot-badge'))
        })
    return {
        'cards': cards,
        'annual': [x['data-selection-id'] for x in soup.select('.annual-best .best-shot-card')],
        'months': [(section.select_one('h2').get_text().split('月')[0] + '月',
                    [x['data-selection-id'] for x in section.select('.best-shot-card')])
                   for section in soup.select('.best-shot-month')],
        'archives': [(a.get('href'), a.get_text()) for a in soup.select('.best-shots-archive a')]
    }
# Only these exact approved reader-facing strings may differ. The generated
# source, photography, URLs, attributes and markup must otherwise be byte-equal
# to the immutable baseline after accounting for the reviewed copy edit.
approved_page_copy = [
    ('このブログで出会った写真と、確認できた図鑑情報をまとめています。',
     '撮影したキノコの写真と、資料をもとに調べた情報をまとめています。'),
    ('名前や五十音順から、ブログで出会ったキノコを探せます。',
     'ブログに登場したキノコを、名前や五十音順から探せます。'),
    ('名前が分かるときは検索、分からないときは五十音からたどれます。',
     '名前を入力して検索するか、五十音順の一覧から探せます。'),
    ('撮影時期や見た目の特徴など、別の手がかりから探せます。',
     '季節や特徴など、名前以外の方法でもキノコを探せます。調査中のキノコやベストショットも掲載しています。'),
    ('写真の撮影月から探せます', '撮影した月からキノコを探せます。'),
    ('資料に記載された見た目の特徴から探す', 'キノコを見た目の特徴から探せます。'),
    ('気になった写真を★で保存して、あとからまとめて見返せます。',
     '★をつけた写真を、撮影時期ごとにまとめています。'),
    ('気になった写真を★で保存して、あとから季節ごとに見返せます。',
     '★をつけた写真を、撮影時期ごとにまとめています。'),
    ('観察中の写真', '気になったキノコ'),
    ('まだ、ここは静かです。', '★をつけた写真はまだありません'),
    ('気になった写真に ★ をつけると、少しずつ並びはじめます。',
     '気になった写真に★をつけると、ここに表示されます。'),
    ('キノコ探索のブログ記事を、新しい順に紹介します。',
     'キノコ探索の記事を、新しい順に並べています。'),
    ('<span>図鑑を見る</span>', '<span>キノコの名前から探す</span>'),
    ('<small>名前、五十音順から探す</small>', '<small></small>'),
    ('名前がわかる場合は', '名前から探したい場合は'),
    ('図鑑から名前や五十音順で探せます。',
     '名前を検索したり、五十音順の一覧から探せます。'),
    ('<small>撮影された季節からたどる</small>', '<small></small>'),
    ('撮影した時期がわかる場合は', '季節ごとに写真を見たいときは'),
    ('季節から候補をたどれます。',
     'このブログで撮影したキノコを、季節ごとにまとめています。'),
    ('正体を調べているキノコを見る', '正体不明のキノコの写真を見る'),
    ('とっておきの一枚を集めた写真館', 'お気に入りのキノコ写真を集めました'),
    # Approved 2026-11-23 follow-up, comparing against merged PR #164.
    ('<span>キノコの名前から探す</span></strong><small></small>',
     '<span>図鑑を見る</span></strong><small>キノコの名前から探す</small>'),
    ('<span>季節から探す</span></strong><small></small>',
     '<span>季節から探す</span></strong><small>季節ごとに写真を見る</small>'),
    ('季節ごとに写真を見たいときは', '季節ごとに写真を見たい場合は'),
]
for p in html_files:
    baseline = root / 'before' / p.name
    if exhibition and (p.name == 'best-shots.html' or
                       p.name.startswith('best-shots-') and p.name.endswith('.html')):
        assert retained_best_shot_data(p) == retained_best_shot_data(baseline), p.name
        if p.name.startswith('best-shots-'):
            year = p.stem.removeprefix('best-shots-')
            assert (f'{year}年に撮影したキノコの中から、ベストショットを月ごとにまとめています。'
                    in p.read_text(encoding='utf-8')), p.name
    else:
        normalized = baseline.read_text(encoding='utf-8')
        # For the CSS-only PR #166, the base already contains all PR #164/#165
        # wording. Comparing its generated HTML byte-for-byte is stricter than
        # reapplying historical substitutions that would corrupt the baseline.
        # A link-only taxonomy update leaves the generated HTML byte-for-byte
        # unchanged when using the immutable published portal-data fixture.
        # The exact four source links are separately validated below.
        css_only_baselines = {'2af083e7ddf47eb8e374f38b2244e2f71a1729ed', '8971cbb5b9250733270853be50de48a6eec2de9c',
                              '7da1d3e27d351b18ca8c6bc0f25bb3d73f7f7cf3',
                              'f41901f452ef0046d8012355236c0dff82e587dc',
                              'a580a7dd9913645efc290cd9235ea7f994386b8b'}
        if git('rev-parse', base).decode().strip() not in css_only_baselines:
            for original, approved in approved_page_copy:
                normalized = normalized.replace(original, approved)
        # Approved 2026-11-23 shared-photo prose is the only main.py HTML
        # difference from the immutable PR #168 baseline.
        if git('rev-parse', base).decode().strip() == 'f41901f452ef0046d8012355236c0dff82e587dc':
            old_shared = ('「複数種が写る写真」は元記事の記載に基づく参照表示です。'
                          '図鑑トップ・観察記録の登録件数には加算しません。未登録の参照写真にはお気に入りの星を表示しません。')
            new_shared = ('1枚の写真に複数の種類が写っている場合は、元の記事の記載をもとに、'
                          'それぞれの図鑑ページにも写真を掲載しています。'
                          'こうした写真は図鑑トップや観察記録の登録件数には含めず、'
                          '未登録の写真にはお気に入りの星も表示していません。')
            normalized = normalized.replace(old_shared, new_shared)
        if git('rev-parse', base).decode().strip() == 'a580a7dd9913645efc290cd9235ea7f994386b8b':
            # Review only exact changes in the source-specific knowledge note.
            # Preserve the warning, source links, images and every other HTML byte.
            import re
            shiitake_previous = (
                '食用可否の自己判断には使用しない。'
                '毒性の記録がないことは安全を意味しない。 '
                '農林水産省が食用きのこと明記した利用記録。'
                '野生個体の判定には使用しない。'
            )
            shiitake_approved = (
                '農林水産省の資料では、シイタケを食用のキノコとして紹介しています。'
                'ただし、この情報だけで野生のキノコの種類や安全性を判断することはできません。'
            )

            def approved_food_note_display(match):
                note = match.group(1)
                if note == shiitake_previous:
                    note = shiitake_approved
                else:
                    note = note.replace('食用可否の自己判断には使用しない。', '')
                    note = note.replace('毒性の記録がないことは安全を意味しない。', '')
                    note = ' '.join(note.split())
                return f'<div class="knowledge-note">{note}</div>' if note else ''

            normalized = re.sub(
                r'<div class="knowledge-note">([^<]*)</div>',
                approved_food_note_display, normalized
            )
        actual = p.read_text(encoding='utf-8')
        if normalized != actual:
            from difflib import unified_diff
            report = ''.join(list(unified_diff(normalized.splitlines(True),
                                               actual.splitlines(True),
                                               fromfile='approved-copy-baseline',
                                               tofile='actual'))[:35])
            raise AssertionError(f'{p.name}: unapproved HTML difference:\\n{report}')
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
# This artwork-only audit also runs against the approved copy/UI PR.
# The comments/worker and all unrelated sources retain their original strict
# review gates. Only the seven exact reviewed Git blobs below may deviate.
approved_copy_source_blobs = {
    'best_shot_ui.py': '96b7569629bc524a055371fb096fc710065cee4a',
    'detail_ui.py': '85e630501fd622aaafd4a634944498600581f42c',
    'feature_ui.py': 'b7d14185b59a3bb1aae7d90565076726b2ae57cd',
    'records_ui.py': 'cfc82d0a8d22245bfec4cbe66a10de259e3a53c4',
    'research_ui.py': '0eae86e8d2b484b0cb0280cb883796449791cf6b',
    'season_ui.py': '2b5c6465557cb25873ef8b98360a8df2ce30098a',
    'assets/research-comments.js': 'e770b36cadf9ec4f640821d2eb6f4bbb2898a5fe',
}
assert set(approved_copy_source_blobs) <= set(protected)
hashes = {}
gallery_viewer_rules_added = False
for p in protected:
    before_bytes = git('show', f'{base}:{p}')
    after_bytes = (repo / p).read_bytes()
    if p in approved_copy_source_blobs:
        # PR #164 is now the comparison base, so these approved bytes can
        # legitimately match the previous revision. The exact Git blob stays pinned.
        expected_blob = (
            '3fe6f66947dfe1d83a99fc7fcca2179e0c606a6e'
            if p == 'detail_ui.py' and git('rev-parse', base).decode().strip() == 'a580a7dd9913645efc290cd9235ea7f994386b8b'
            else 'df4751111a023756bf05c0d59b5df748c5326fe8'
            if p == 'detail_ui.py' and git('rev-parse', base).decode().strip() == 'f41901f452ef0046d8012355236c0dff82e587dc'
            else approved_copy_source_blobs[p]
        )
        assert git('rev-parse', f'HEAD:{p}').decode().strip() == expected_blob, p
    elif p == 'assets/gallery.css':
        gallery_viewer_rules_added = verify_gallery_css(before_bytes, after_bytes)
    else:
        assert_reviewed_source(base, p, after_bytes)
    hashes[p] = hashlib.sha256(before_bytes).hexdigest()
for p in ('portal-data.json','article-sync-snapshot.json','research-comment-cases.json'):
    assert (root/'published'/p).read_bytes() == (root/'after'/p).read_bytes(), p
config = json.loads((root/'after/research-comments-config.json').read_text())
assert config == json.loads((repo/'comments/public-config.json').read_bytes())
assert json.loads((root/'published/research-comments-config.json').read_bytes()) in (
    json.loads(git('show', f'{base}:comments/public-config.json')), config)
(root/'screenshots').mkdir(exist_ok=True)
(root/'vendor').mkdir(exist_ok=True)
for p in (repo/'lightgallery').rglob('*'):
    if p.is_file(): shutil.copy2(p, root/'vendor'/p.name)
r=requests.get('https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js',timeout=30)
r.raise_for_status();assert len(r.content)>1000
(root/'vendor/imagesloaded.pkgd.min.js').write_bytes(r.content)
result = {'base_main':git('rev-parse',base).decode().strip(), 'published':git('rev-parse','origin/gh-pages').decode().strip(),
          'generated_html_count':len(html_files),'identical_html_before_after': not exhibition, 'best_shot_curated_data_identical': True, 'non_best_shot_html_identical': True,'old_display_references':remaining,
          'pages_with_new_artwork':len(coverage),'coverage':coverage,'protected_source_files':len(protected),
          'gallery_viewer_rules_added':gallery_viewer_rules_added,
          'protected_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
          'published_portal_sha256':hashlib.sha256((root/'after/portal-data.json').read_bytes()).hexdigest(),
          'counts':{'photos':len(portal['observations']),'best_shots':best['entry_count'],'research':research['case_count'],
                    'notices':len(json.loads((repo/'data/update-notices.json').read_text())['events']),
                    'master':len(portal['reference_data']['mushroom_master']['entries']),
                    'sources':len(portal['reference_data']['sources']['sources'])}}
(root/'artwork-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(root/'reference-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='coverage'},ensure_ascii=False))
