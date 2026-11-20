"""Read-only integration gate: latest main plus exact, reviewed PR 137 bytes."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PR137 = '1766b1693ec87a2945b98abc5456f48fc9a13026'
PR135 = '090eac16c25129695452a10a076532c752d8bd27'
REVIEWED = {'.gitignore', 'admin/comments_client.py', 'comments/worker.mjs',
            'comments/package.json', 'comments/package-lock.json'}
CPU_BASE = '582a6c19e136fe5f7f6b2c2448cb0f63f14d1235'
CPU_RUNTIME = {'comments/staging/worker.mjs', 'comments/staging/registry.mjs'}
RELEASE_MAIN = '249bf1845bdd5d3c7a46e7939f0cd54b6eef9792'
RELEASE_FILES = {
    'admin/comments_client.py', 'assets/research-comments.js', 'comments/worker.mjs',
    'requirements.txt', 'research_comments.py', 'research_ui.py', 'comments/tests/api.test.mjs',
}
ACTIVITY_FILES = {'assets/research-comments.js',
                  'comments/worker.mjs', 'comments/tests/api.test.mjs', 'research_ui.py'}
ACTIVITY_MAIN = 'dcd8d072bffa23495f7a1028a4636f3eb1f7ca70'
POST_RECOVERY_MAIN = '5dc43d89b2d8b05afd3985b3d6515c8b7f8de48b'
POST_RECOVERY_FILES = {'assets/research-comments.js', 'comments/worker.mjs', 'comments/tests/api.test.mjs'}
# Independent Best Shot design PR. No comment/Worker file is exempted.
EXHIBITION_BASE = '90fbdeb761abe217db7179e87d0fcf13a44b2b0b'
EXHIBITION_MODIFIED = {'best_shot_ui.py', 'assets/best-shots.css'}
EXHIBITION_NEW = {'assets/best-shot-exhibition.js', 'previews/best-shot-exhibition-20261121.html'}
TAXONOMY_LINKS = {
    'ヤマドリタケモドキ': 'yamadoritakemodoki',
    'シイタケ': 'shiitake',
    'ベニテングタケ': 'benitengutake',
    'ドクヤマドリ': 'dokuyamadori',
}
PUBLIC_CONFIG = 'comments/public-config.json'
PRODUCTION_ORIGIN = 'https://kinoko-research-comments.sasama-bb.workers.dev'
RELEASE_ID = 'research-comments-production-20261120'
DISABLED_CONFIG = {'version': 1, 'enabled': False, 'api_url': '', 'turnstile_site_key': '', 'release_approval': None}

def assert_staging_source(path, content):
    """Only the two explicitly reviewed CPU runtime files may differ in Nov 1.

    Preserve all old frozen checks; use exact SHA pins for the intended update,
    rather than exempting the entire staging directory from byte protection.
    """
    if path not in CPU_RUNTIME:
        assert content == git('show', f'{PR137}:{path}'), path
        return
    pins = json.loads((ROOT/'audit/comments-cpu-options-20261101/runtime-hashes.json').read_text(encoding='utf-8'))
    assert pins['baseline'] == CPU_BASE and set(pins['files']) == CPU_RUNTIME
    assert hashlib.sha256(content).hexdigest() == pins['files'][path], path

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def assert_reviewed_source(base, path, current):
    """Never hide a main change behind the old PR's allowance."""
    original = git('show', f'{base}:{path}')
    if current == original:
        return
    if path == 'data/subject-taxonomy.json':
        expected = json.loads(original)
        linked = set()
        for entry in expected['entries']:
            name = entry['canonical_name']
            if name in TAXONOMY_LINKS:
                assert entry['subject_type'] == 'mushroom' and 'mushroom_master_id' not in entry, name
                entry['mushroom_master_id'] = TAXONOMY_LINKS[name]
                linked.add(name)
        assert linked == TAXONOMY_LINKS.keys(), path
        assert current == (json.dumps(expected, ensure_ascii=False, indent=2) + '\n').encode('utf-8'), path
        return
    if path in EXHIBITION_MODIFIED:
        # Exception only for this Best Shot draft's exact Git blobs.
        # The baseline must be unchanged and all non-Best-Shot sources stay pinned.
        pins = json.loads((ROOT/'audit/best-shot-exhibition-20261121/files.json').read_text(encoding='utf-8'))
        assert pins['base_main'] == EXHIBITION_BASE
        assert set(pins['files']) == EXHIBITION_MODIFIED | EXHIBITION_NEW
        assert original == git('show', f'{EXHIBITION_BASE}:{path}'), f'Best Shot main advanced: {path}'
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == pins['files'][path], path
        return
    if path in POST_RECOVERY_FILES:
        pins = json.loads((ROOT/'audit/comments-post-recovery-20261120/files.json').read_text(encoding='utf-8'))
        assert pins['main'] == POST_RECOVERY_MAIN and set(pins['files']) == POST_RECOVERY_FILES
        if hashlib.sha256(current).hexdigest() == pins['files'][path]:
            assert_reviewed_source(base, path, git('show', f'{POST_RECOVERY_MAIN}:{path}'))
            return
    if path == PUBLIC_CONFIG:
        config = json.loads(current)
        assert json.loads(original) == DISABLED_CONFIG or config == DISABLED_CONFIG
        if config != DISABLED_CONFIG:
            assert config == {'version': 1, 'enabled': True, 'api_url': PRODUCTION_ORIGIN,
                              'turnstile_site_key': config['turnstile_site_key'], 'release_approval': RELEASE_ID}
            assert re.fullmatch(r'0x[A-Za-z0-9_-]{12,100}', config['turnstile_site_key'])
        return
    if path in ACTIVITY_FILES:
        pins = json.loads((ROOT/'audit/comments-activity-20261118/files.json').read_text(encoding='utf-8'))
        assert pins['main'] == ACTIVITY_MAIN and set(pins['files']) == ACTIVITY_FILES
        assert original == git('show', f'{ACTIVITY_MAIN}:{path}'), f'main advanced: {path}'
        if hashlib.sha256(current).hexdigest() == pins['files'][path]:
            return
    if path in RELEASE_FILES:
        # Keep the original reviewed PR bytes acceptable and pin the new release
        # delta. Never accept a changed version of the same file from main.
        baseline = git('show', f'{RELEASE_MAIN}:{path}')
        assert original == baseline, f'main advanced: {path}'
        if path in REVIEWED and current == git('show', f'{PR137}:{path}'):
            return
        pins = json.loads((ROOT/'audit/comments-release-prep-20261117/files.json').read_text(encoding='utf-8'))
        assert pins['main'] == RELEASE_MAIN and set(pins['files']) == RELEASE_FILES
        assert hashlib.sha256(current).hexdigest() == pins['files'][path], path
        return
    assert path in REVIEWED, path
    # package*.json are newly added in PR137, so not reached by a main file loop.
    assert original == git('show', f'{PR135}:{path}'), f'main advanced: {path}'
    assert current == git('show', f'{PR137}:{path}'), f'PR137 changed: {path}'

def collect(base='origin/main'):
    git('merge-base', '--is-ancestor', base, 'HEAD')
    protected = [p for p in git('ls-tree', '-rz', '--name-only', base).decode().split('\0')
                 if p and not p.startswith(('.github/', 'audit/', 'tests/', 'docs/', 'tools/'))]
    hashes = {}
    for path in protected:
        content = (ROOT / path).read_bytes()
        assert_reviewed_source(base, path, content)
        hashes[path] = hashlib.sha256(content).hexdigest()
    # Newly added exhibit assets are not in the baseline tree: pin explicitly.
    pins = json.loads((ROOT/'audit/best-shot-exhibition-20261121/files.json').read_text(encoding='utf-8'))
    assert pins['base_main'] == EXHIBITION_BASE
    assert set(pins['files']) == EXHIBITION_MODIFIED | EXHIBITION_NEW
    for path in EXHIBITION_NEW:
        current = (ROOT / path).read_bytes()
        blob = b'blob ' + str(len(current)).encode('ascii') + b'\0' + current
        assert hashlib.sha1(blob).hexdigest() == pins['files'][path], path
    # Original runtime stays byte-for-byte equal except exact reviewed CPU pins.
    runtime = [p for p in git('ls-tree', '-rz', '--name-only', PR137, 'comments/staging').decode().split('\0') if p]
    runtime += ['comments/package.json', 'comments/package-lock.json']
    runtime += ['comments/staging/registry.mjs']
    for path in runtime:
        assert_staging_source(path, (ROOT/path).read_bytes())
    portal = json.loads(git('show', 'origin/gh-pages:portal-data.json'))
    read = lambda name: json.loads((ROOT/name).read_text(encoding='utf-8'))
    config = json.loads(git('show', 'origin/gh-pages:research-comments-config.json'))
    source_config = read(PUBLIC_CONFIG)
    base_config = json.loads(git('show', f'{base}:{PUBLIC_CONFIG}'))
    assert config in (base_config, source_config)
    registry = read('comments/cases.json')
    sys.path.insert(0, str(ROOT))
    from research_comments import registry_digest, prepare
    from research_ui import build_research_cases
    cases = build_research_cases(portal)
    state = prepare(cases, registry)
    assert not state['pending'], state['pending']
    manifest = read('comments/staging/manifest.json')
    published = json.loads(git('show', 'origin/gh-pages:research-comment-cases.json'))
    assert manifest == published
    assert manifest['registry_sha256'] == registry_digest(registry)
    assert sorted(manifest['active_ids']) == sorted(r['id'] for r in registry['cases'])
    snapshot = json.loads(git('show', 'origin/gh-pages:article-sync-snapshot.json'))
    from bs4 import BeautifulSoup
    selections = set()
    for p in git('ls-tree','-rz','--name-only','origin/gh-pages').decode().split('\0'):
        if p.startswith('best-shots') and p.endswith('.html'):
            selections.update(c['data-selection-id'] for c in BeautifulSoup(git('show',f'origin/gh-pages:{p}'),'html.parser').select('[data-selection-id]'))
    assert selections == {e['selection_id'] for e in read('data/best-shots.json')['entries']}
    for name in ('mushroom-master', 'sources'):
        key = 'mushroom_master' if name == 'mushroom-master' else name
        assert portal['reference_data'][key] == read(f'data/{name}.json')
    artworks = read('audit/ai-image-refresh-20261031/artwork-manifest.json')['assets']
    for row in artworks:
        name = 'assets/'+row['asset']
        assert (ROOT/name).read_bytes() == git('show', f'origin/gh-pages:{name}'), name
    output_names = ['portal-data.json','article-sync-snapshot.json','research-comment-cases.json','research-comments-config.json']
    return {'main':git('rev-parse',base).decode().strip(),
            'published':git('rev-parse','origin/gh-pages').decode().strip(),
            'reviewed_pr137':PR137, 'protected_files':hashes,
            'exact_reviewed_staging_files':runtime, 'registry_sha256':registry_digest(registry),
            'cpu_runtime_review':CPU_BASE,
            'counts':{'photos':len(portal['observations']), 'best_shots':len(selections),
                      'notices':len(read('data/update-notices.json')['events']),
                      'research':len(cases), 'retired':snapshot['payload']['retirement']['retired_count'],
                      'master':len(read('data/mushroom-master.json')['entries']),
                      'sources':len(read('data/sources.json')['sources']), 'webp':len(artworks)},
            'published_hashes':{p:hashlib.sha256(git('show',f'origin/gh-pages:{p}')).hexdigest() for p in output_names},
            'comments_enabled':config['enabled'], 'pending':state['pending'], 'remote_mutations':[]}

if __name__ == '__main__':
    result = collect(sys.argv[2] if len(sys.argv)>2 else 'origin/main')
    if len(sys.argv)>1:
        Path(sys.argv[1]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='protected_files'},ensure_ascii=False))
