"""Conservative important-reference inventory, separate from rename protection.

Open PRs are enumerated on every check, not a hardcoded PR-number allowlist.
Failure to obtain any required source makes the entire inventory unavailable.
"""
import base64
from collections import defaultdict
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

from article_sync import SyncError, payload_hash, read_json, digest
from best_shot_ui import validate_best_shot_config
from research_ui import build_research_cases
from research_identifications import validate_registry

REPOSITORY = 'charchan123/hatena-photo-gallery'


def curated_path(path):
    p=Path(path)
    if path == 'comments/cases.json': return True
    return ((path.startswith('data/') or path.startswith('sync-migrations/')) and
            p.suffix=='.json' and not path.startswith('sync-migrations/photo-deletions/')) or (
            len(p.parts)==1 and p.suffix in {'.html','.js','.py'}) or (
            len(p.parts)==2 and p.parts[0]=='assets' and p.suffix in {'.js','.html'})


def github_get(path):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        import shutil, subprocess
        if shutil.which('gh'):
            result=subprocess.run(['gh','auth','token'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
            if result.returncode==0:token=result.stdout.strip()
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
        before = all_prs(); result = []; blobs = {}
        for pr in before:
            repo = pr['head']['repo']['full_name']
            # A fork or inaccessible pending configuration cannot be assumed safe.
            if repo != REPOSITORY: raise SyncError('DELETION_PENDING_FORK_REQUIRES_REVIEW')
            sha = pr['head']['sha']
            if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha): raise ValueError()
            tree = api('git/trees/' + sha + '?recursive=1')
            if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
                raise SyncError('DELETION_REFERENCE_TREE_INCOMPLETE')
            def text_content(node):
                if node['type']!='blob' or node['mode'] not in {'100644','100755'}:raise ValueError()
                if node['sha'] in blobs:return blobs[node['sha']]
                blob=api('contents/'+quote(node['path'],safe='/')+'?ref='+sha)
                if blob.get('sha')!=node['sha'] or blob.get('encoding')!='base64' or blob.get('size',1_000_001)>1_000_000:raise ValueError()
                text=base64.b64decode(blob['content'],validate=False).decode('utf-8')
                blobs[node['sha']]=text
                return text
            def content(node):return json.loads(text_content(node))
            paths=[r for r in tree['tree'] if r['path']=='data/best-shots.json']
            if len(paths)>1:raise ValueError()
            config=content(paths[0]) if paths else {'version':1,'entries':[],'annual_best':{}}
            from deletion_approvals import validate as validate_approval, latest
            manifests=[]
            for node in tree['tree']:
                if not node['path'].startswith('sync-migrations/photo-deletions/'):continue
                if node['type']=='tree':continue
                m=validate_approval(content(node))
                if node['path']!='sync-migrations/photo-deletions/'+m['approval_id']+'.json':raise ValueError()
                manifests.append(m)
            holds=[m for m in latest(manifests) if m['action'] in {'hold','propose_replacement'}]
            # Read every changed curated file at its immutable PR head. Patch
            # excerpts are incomplete and cannot prove absence of references.
            changed=[]
            for page in range(1,31):
                rows=api(f"pulls/{pr['number']}/files?per_page=100&page={page}")
                if not isinstance(rows,list):raise ValueError()
                changed.extend(rows)
                if len(rows)<100:break
            else:raise SyncError('DELETION_REFERENCE_PAGINATION_INCOMPLETE')
            nodes={n['path']:n for n in tree['tree']};curated=[]
            for row in changed:
                path=row['filename']
                if not curated_path(path) or path=='data/best-shots.json' or row['status']=='removed':continue
                if path not in nodes:raise ValueError()
                curated.append({'path':path,'text':text_content(nodes[path])})
            result.append({'number':pr['number'],'head':sha,'config':config,
                'file_absent_verified':not paths,'deletion_holds':holds,'curated':curated})
        signature = lambda rows: sorted((p['number'], p['head']['sha']) for p in rows)
        if signature(before) != signature(all_prs()): raise SyncError('DELETION_PENDING_REFERENCES_CHANGED')
        return result
    except SyncError: raise
    except Exception: raise SyncError('DELETION_REFERENCES_UNAVAILABLE') from None


def strings(value):
    if isinstance(value, str): yield value
    elif isinstance(value, dict):
        for k,v in value.items():
            if isinstance(k,str):yield k
            yield from strings(v)
    elif isinstance(value, list):
        for v in value: yield from strings(v)


def collect(portal, snapshot, root, pending, *, registry_before=None):
    """All curated JSON/HTML references + research + historical migration targets.

    Generated index pages that list *every* observation are not curated refs.
    Authenticated PR enumeration must succeed before this function is called.
    """
    root = Path(root); refs = defaultdict(list); sources = {}; source_refs=defaultdict(list); image_refs=defaultdict(list)
    known_urls={im['url_hash'] for article in snapshot['payload']['articles'].values() for im in article['images']}
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
        comment_bindings = root / 'comments/cases.json'
        if comment_bindings.exists():
            from research_comments import validate_bindings
            validate_bindings(read_json(comment_bindings))
            files.append(comment_bindings)
        files += [p for pattern in ('*.html','*.js','*.py','assets/*.js','assets/*.html') for p in root.glob(pattern) if p.is_file()]
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
                for value in values:
                    key=value if value in known_urls else digest(value)
                    if key in known_urls and {'kind':'curated_history','id':relative} not in image_refs[key]:
                        image_refs[key].append({'kind':'curated_history','id':relative})
                for oid in set(by_id) & values: protect(oid, 'curated_history', relative)
                for src in set(by_src) & values:
                    for oid in by_src[src]: protect(oid, 'curated_history', relative)
            else:
                for value in re.findall(r'''https?://[^\s"'<>\\]+''',text):
                    key=digest(value)
                    if key in known_urls:image_refs[key].append({'kind':'curated_page','id':relative})
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
            for file in pr.get('curated',[]):
                identity='PR #'+str(pr['number'])+':'+file['path']
                text=file['text']
                if file['path'].endswith('.json'):
                    values=set(strings(json.loads(text)))
                    for oid in set(by_id)&values:protect(oid,'pending_curated_reference',identity)
                    urls=values
                else:
                    for oid in by_id:
                        if oid in text:protect(oid,'pending_curated_reference',identity)
                    urls=re.findall(r'''https?://[^\s"'<>\\]+''',text)
                for value in urls:
                    key=value if value in known_urls else digest(value)
                    ref={'kind':'pending_curated_reference','id':identity}
                    if key in known_urls and ref not in image_refs[key]:image_refs[key].append(ref)
            for hold in pr.get('deletion_holds',[]):
                if hold['baseline']==snapshot['sha256']:
                    source_refs[hold['candidate_id']].append({'kind':'pending_deletion_hold','id':'PR #'+str(pr['number'])})
            validate_best_shot_config(pr['config'], portal)
            extras = [r for r in pr['config']['entries'] if r['observation_id'] not in {e['observation_id'] for e in config['entries']}]
            # A deletion-approval PR carrying an unchanged Best Shot file must
            # not invalidate its own approval merely by being opened.
            if extras:
                sources['PR-' + str(pr['number'])] = {'config_sha256': payload_hash(pr['config'])}
            for row in extras: protect(row['observation_id'], 'pending_best_shot', 'PR #' + str(pr['number']) + ':' + row['selection_id'])
    except SyncError: raise
    except Exception: raise SyncError('DELETION_REFERENCES_UNAVAILABLE') from None
    result = {'version': 1, 'complete': True, 'sources': sources, 'source_references': dict(sorted(source_refs.items())), 'image_references':dict(sorted(image_refs.items())),
              'references': {oid: sorted(v, key=lambda r: (r['kind'], r['id'])) for oid, v in sorted(refs.items())}}
    return {**result, 'sha256': payload_hash(result)}
