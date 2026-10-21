"""Separate, explicit comment identity bindings; never change research identities."""
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def fingerprint(article_identity, observation_ids):
    return hashlib.sha256(canonical([article_identity, sorted(observation_ids)]).encode()).hexdigest()

def validate_bindings(registry):
    import re
    if not isinstance(registry, dict) or set(registry) != {'version', 'cases'} or registry['version'] != 1:
        raise ValueError('comment binding schema invalid')
    ids, aliases, photos = set(), set(), set()
    for row in registry['cases']:
        if set(row) != {'id','label','article_identity','observation_ids','render_ids'}:
            raise ValueError('comment binding fields invalid')
        if not re.fullmatch(r'research-[0-9a-f]{16}', row['id']) or row['id'] in ids:
            raise ValueError('duplicate/invalid permanent comment ID')
        ids.add(row['id'])
        if not isinstance(row['label'], str) or not row['label'].strip():
            raise ValueError('comment case label required')
        identity = row['article_identity']
        if not isinstance(identity, list) or len(identity) != 2 or identity[0] not in {'article_id','article_path','url'} or not isinstance(identity[1], str) or not identity[1]:
            raise ValueError('stable article identity required')
        members = row['observation_ids']
        if not isinstance(members, list) or not members or any(not isinstance(x,str) or not x for x in members) or len(set(members)) != len(members) or photos.intersection(members):
            raise ValueError('ambiguous/split/merged comment photo membership')
        photos.update(members)
        if not isinstance(row['render_ids'], list) or not row['render_ids'] or row['id'] not in row['render_ids']:
            raise ValueError('original comment alias must be retained')
        for alias in row['render_ids']:
            if not isinstance(alias,str) or not re.fullmatch(r'research-[0-9a-f]{16}',alias) or alias in aliases:
                raise ValueError('comment alias collision')
            aliases.add(alias)
    # A permanent ID cannot be used as another case's alias.
    return registry

def registry_digest(registry):
    return hashlib.sha256(canonical(validate_bindings(registry)).encode()).hexdigest()

def bind_cases(cases, registry):
    from research_ui import _article_identity
    validate_bindings(registry)
    aliases = {a:row for row in registry['cases'] for a in row['render_ids']}
    from collections import Counter
    render_counts = Counter(c['case_id'] for c in cases)
    thread_counts = Counter(aliases[c['case_id']]['id'] for c in cases if c['case_id'] in aliases)
    bound, pending = {}, []
    seen = set()
    for case in cases:
        row = aliases.get(case['case_id'])
        members = [p.get('observation_id') for p in case['photos']]
        identity = _article_identity(case['article'])
        if (row and render_counts[case['case_id']] == 1 and thread_counts[row['id']] == 1 and identity and list(identity) == row['article_identity']
                and len(members)==len(set(members)) and set(members)==set(row['observation_ids'])
                and row['id'] not in seen):
            bound[case['case_id']] = row['id']; seen.add(row['id'])
        else:
            pending.append(case['case_id'])
    return bound, pending

def prepare(cases, registry=None):
    if registry is None:
        registry = json.loads((ROOT/'comments/cases.json').read_text(encoding='utf-8'))
    bindings, pending = bind_cases(cases, registry)
    active = sorted(set(bindings.values()))
    return {'registry_sha256':registry_digest(registry), 'bindings':bindings, 'pending':pending,
            'active_ids':active, 'archived':[r for r in registry['cases'] if r['id'] not in active]}

def mount(case_id, prepared):
    thread = prepared['bindings'].get(case_id)
    if not thread:
        return '<p class="research-comments-pending">コメントの紐付けは管理人の確認待ちです。以前の履歴は下の保管欄から確認できます。</p>'
    return thread_mount(thread)

def thread_mount(thread, archived=False):
    note = '過去のコメントを読む（新規投稿は停止）' if archived else '同定のヒント・コメント'
    return f'<details class="research-comments" data-research-thread="{html.escape(thread,quote=True)}" data-archived="{str(archived).lower()}"><summary>{note}</summary><div class="research-comments-content"><p role="status">コメント機能は準備中です。</p></div></details>'

def public_config():
    from urllib.parse import urlsplit
    config = json.loads((ROOT/'comments/public-config.json').read_text(encoding='utf-8'))
    if set(config) != {'version','enabled','api_url','turnstile_site_key','release_approval'} or config['version'] != 1 or type(config['enabled']) is not bool:
        raise ValueError('invalid comments public configuration')
    if config['enabled']:
        url=urlsplit(config['api_url'])
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in {'','/'} or url.query or url.fragment or not config['turnstile_site_key'] or not config['release_approval']:
            raise ValueError('comment publication requires explicit approval and HTTPS configuration')
    return config
