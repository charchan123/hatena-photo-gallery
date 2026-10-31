"""Read-only integration gate: latest main plus exact, reviewed PR 137 bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PR137 = '1766b1693ec87a2945b98abc5456f48fc9a13026'
PR135 = '090eac16c25129695452a10a076532c752d8bd27'
REVIEWED = {'.gitignore', 'admin/comments_client.py', 'comments/worker.mjs',
            'comments/package.json', 'comments/package-lock.json'}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def assert_reviewed_source(base, path, current):
    """Never hide a main change behind the old PR's allowance."""
    original = git('show', f'{base}:{path}')
    if current == original:
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
    # New staging runtime also stays byte-for-byte equal to the reviewed PR.
    runtime = [p for p in git('ls-tree', '-rz', '--name-only', PR137, 'comments/staging').decode().split('\0') if p]
    runtime += ['comments/package.json', 'comments/package-lock.json']
    for path in runtime:
        assert (ROOT/path).read_bytes() == git('show', f'{PR137}:{path}'), path
    portal = json.loads(git('show', 'origin/gh-pages:portal-data.json'))
    read = lambda name: json.loads((ROOT/name).read_text(encoding='utf-8'))
    config = json.loads(git('show', 'origin/gh-pages:research-comments-config.json'))
    assert config == read('comments/public-config.json') and config['enabled'] is False
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
            'counts':{'photos':len(portal['observations']), 'best_shots':len(selections),
                      'notices':len(read('data/update-notices.json')['events']),
                      'research':len(cases), 'retired':snapshot['payload']['retirement']['retired_count'],
                      'master':len(read('data/mushroom-master.json')['entries']),
                      'sources':len(read('data/sources.json')['sources']), 'webp':len(artworks)},
            'published_hashes':{p:hashlib.sha256(git('show',f'origin/gh-pages:{p}')).hexdigest() for p in output_names},
            'comments_enabled':False, 'pending':state['pending'], 'remote_mutations':[]}

if __name__ == '__main__':
    result = collect(sys.argv[2] if len(sys.argv)>2 else 'origin/main')
    if len(sys.argv)>1:
        Path(sys.argv[1]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='protected_files'},ensure_ascii=False))
