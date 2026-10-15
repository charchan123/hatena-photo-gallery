"""Conservative important-reference inventory, separate from rename protection.

Open PRs are enumerated on every check, not a hardcoded PR-number allowlist.
Failure to obtain any required source makes the entire inventory unavailable.
"""
import base64
from collections import defaultdict
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from article_sync import SyncError, payload_hash, read_json
from best_shot_ui import validate_best_shot_config
from research_ui import build_research_cases
from research_identifications import validate_registry

REPOSITORY = 'charchan123/hatena-photo-gallery'


def github_get(path):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'kinoko-deletion-review'}
    if token: headers['Authorization'] = 'Bearer ' + token
    # Host fixed; repository/path is not user input. Never log HTTP error bodies.
    try:
        with urlopen(Request('https://api.github.com/repos/' + REPOSITORY + '/' + path, headers=headers), timeout=30) as response:
            return json.load(response)
    except Exception:
        raise SyncError('DELETION_REFERENCES_UNAVAILABLE') from None


def open_selections(api=github_get):
    def all_prs():
        result = []
        for page in range(1, 101):
            rows = api(f'pulls?state=open&per_page=100&page={page}')
            if not isinstance(rows, list): raise SyncError('DELETION_REFERENCES_UNAVAILABLE')
            result.extend(rows)
            if len(rows) < 100: return result
        raise SyncError('DELETION_REFERENCE_PAGINATION_INCOMPLETE')
    try:
        before = all_prs(); result = []
        for pr in before:
            repo = pr['head']['repo']['full_name']
            # A fork or inaccessible pending configuration cannot be assumed safe.
            if repo != REPOSITORY: raise SyncError('DELETION_PENDING_FORK_REQUIRES_REVIEW')
            sha = pr['head']['sha']
            if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha): raise ValueError()
            tree = api('git/trees/' + sha + '?recursive=1')
            if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
                raise SyncError('DELETION_REFERENCE_TREE_INCOMPLETE')
            paths = [r for r in tree['tree'] if r['path'] == 'data/best-shots.json']
            if not paths:
                result.append({'number': pr['number'], 'head': sha, 'config': {'version':1, 'entries':[], 'annual_best':{}}, 'file_absent_verified': True})
                continue
            if len(paths) != 1 or paths[0]['type'] != 'blob' or paths[0]['mode'] not in {'100644','100755'}: raise ValueError()
            blob = api('contents/data/best-shots.json?ref=' + sha)
            if blob.get('sha') != paths[0]['sha']: raise ValueError()
            if blob['encoding'] != 'base64' or blob.get('size', 1_000_001) > 1_000_000: raise ValueError()
            config = json.loads(base64.b64decode(blob['content'], validate=False))
            result.append({'number': pr['number'], 'head': sha, 'config': config})
        signature = lambda rows: sorted((p['number'], p['head']['sha']) for p in rows)
        if signature(before) != signature(all_prs()): raise SyncError('DELETION_PENDING_REFERENCES_CHANGED')
        return result
    except SyncError: raise
    except Exception: raise SyncError('DELETION_REFERENCES_UNAVAILABLE') from None


def strings(value):
    if isinstance(value, str): yield value
    elif isinstance(value, dict):
        for v in value.values(): yield from strings(v)
    elif isinstance(value, list):
        for v in value: yield from strings(v)


def collect(portal, snapshot, root, pending, *, registry_before=None):
    """All curated JSON/HTML references + research + historical migration targets.

    Generated index pages that list *every* observation are not curated refs.
    Authenticated PR enumeration must succeed before this function is called.
    """
    root = Path(root); refs = defaultdict(list); sources = {}
    by_id = {r['observation_id']: r for r in portal['observations']}
    by_src = defaultdict(list)
    for row in by_id.values(): by_src[row['src']].append(row['observation_id'])
    def protect(oid, kind, identity):
        value = {'kind': kind, 'id': identity}
        if value not in refs[oid]: refs[oid].append(value)
    try:
        config = read_json(root / 'data/best-shots.json'); validate_best_shot_config(config, portal)
        sources['best-shots'] = payload_hash(config)
        annual = set(config['annual_best'].values())
        for row in config['entries']:
            protect(row['observation_id'], 'annual_best' if row['selection_id'] in annual else 'best_shot', row['selection_id'])
        registry = registry_before if registry_before is not None else read_json(root / 'data/research-identifications.json')
        master = read_json(root / 'data/mushroom-master.json')
        validate_registry(registry, portal, master)
        for case in build_research_cases(portal):
            for photo in case['photos']: protect(photo['observation_id'], 'research', case['case_id'])
        for row in registry['identifications']:
            case = next(c for c in build_research_cases(portal) if c['case_id'] == row['case_id'])
            for photo in case['photos']: protect(photo['observation_id'], 'identification', row['identification_id'])
        # Future curated JSON and static page links are protected by actual IDs
        # or exact photo URLs. No matching by mushroom name.
        files = list((root / 'data').rglob('*.json')) + [p for p in (root / 'sync-migrations').rglob('*.json') if 'photo-deletions' not in p.parts]
        files += [p for p in root.glob('*.html') if p.is_file()]
        for file in sorted(files):
            relative = file.relative_to(root).as_posix()
            if file.is_symlink() or file.stat().st_size > 20_000_000: raise ValueError()
            text = file.read_text(encoding='utf-8')
            if file.suffix == '.json':
                obj = registry if relative == 'data/research-identifications.json' else json.loads(text)
                sources[relative] = payload_hash(obj)
                # Best/research are already assigned precise reasons. The whole
                # registry hash still binds approvals, including empty history.
                if relative in {'data/best-shots.json', 'data/research-identifications.json'}: continue
                values = set(strings(obj))
                for oid in set(by_id) & values: protect(oid, 'curated_history', relative)
                for src in set(by_src) & values:
                    for oid in by_src[src]: protect(oid, 'curated_history', relative)
            else:
                sources[relative] = payload_hash(text)
                for oid in by_id:
                    if oid in text: protect(oid, 'curated_page', relative)
                for src, ids in by_src.items():
                    if src in text:
                        for oid in ids: protect(oid, 'curated_page', relative)
        # These immutable ledgers still require surviving targets. Deleting such
        # a photo needs an explicit migration of that contract, never this path.
        for field in ('manual_adoptions', 'name_migrations'):
            for row in snapshot['payload'].get(field, []): protect(row['observation_id'], 'receipt', field)
        for pr in pending:
            validate_best_shot_config(pr['config'], portal)
            extras = [r for r in pr['config']['entries'] if r['observation_id'] not in {e['observation_id'] for e in config['entries']}]
            # A deletion-approval PR carrying an unchanged Best Shot file must
            # not invalidate its own approval merely by being opened.
            if extras:
                sources['PR-' + str(pr['number'])] = {'config_sha256': payload_hash(pr['config'])}
            for row in extras: protect(row['observation_id'], 'pending_best_shot', 'PR #' + str(pr['number']) + ':' + row['selection_id'])
    except SyncError: raise
    except Exception: raise SyncError('DELETION_REFERENCES_UNAVAILABLE') from None
    result = {'version': 1, 'complete': True, 'sources': sources,
              'references': {oid: sorted(v, key=lambda r: (r['kind'], r['id'])) for oid, v in sorted(refs.items())}}
    return {**result, 'sha256': payload_hash(result)}
