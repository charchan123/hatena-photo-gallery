"""Immutable single-target human deletion transactions and internal case archives."""
from copy import deepcopy
import json
from pathlib import Path
import re

from article_sync import SyncError, payload_hash, read_json
from sync_deletions import instant
from research_ui import build_research_cases
from research_identifications import validate_registry

ACTIONS = {'hold', 'approve', 'propose_replacement', 'archive_research', 'retire_research','approve_research_photo'}
FIELDS = {'version','approval_id','candidate_id','fingerprint','baseline','protection','action',
          'approved_at','reason_sha256','case_ids','archives','registry_before','replacement_id','supersedes'}


def validate(m):
    try:
        assert isinstance(m,dict) and set(m)==FIELDS and type(m['version']) is int and m['version']==1
        assert m['action'] in ACTIONS
        for key in ('approval_id','candidate_id','fingerprint','baseline','protection','reason_sha256'):
            assert isinstance(m[key],str) and re.fullmatch('[0-9a-f]{64}',m[key])
        assert m['approval_id']==payload_hash({k:v for k,v in m.items() if k!='approval_id'})
        instant(m['approved_at'])
        assert m['supersedes'] is None or re.fullmatch('[0-9a-f]{64}',m['supersedes'])
        assert isinstance(m['case_ids'],list) and len(set(m['case_ids']))==len(m['case_ids'])
        assert all(isinstance(x,str) and re.fullmatch('research-[0-9a-f]{16}',x) for x in m['case_ids'])
        assert isinstance(m['archives'],list)
        assert m['replacement_id'] is None or re.fullmatch('obs-[a-zA-Z0-9_-]{1,100}',m['replacement_id'])
        if m['action'] in {'archive_research','retire_research','approve_research_photo'}:
            assert m['case_ids'] and len(m['archives'])==len(m['case_ids'])
            assert isinstance(m['registry_before'],dict)
        else:
            assert not m['case_ids'] and not m['archives'] and m['registry_before'] is None
    except (AssertionError,KeyError,TypeError,ValueError):
        raise SyncError('DELETION_APPROVAL_INVALID') from None
    return m


def load(root):
    directory=Path(root)/'sync-migrations/photo-deletions'
    if any(p.is_symlink() for p in (directory,*directory.parents)):raise SyncError('DELETION_APPROVAL_STORAGE_UNSAFE')
    if not directory.exists():return []
    result=[];seen=set()
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:raise SyncError('DELETION_APPROVAL_INVALID')
        m=validate(read_json(path))
        if path.name!=m['approval_id']+'.json' or m['approval_id'] in seen:raise SyncError('DELETION_APPROVAL_DUPLICATE')
        seen.add(m['approval_id']);result.append(m)
    latest(result)
    return result


def latest(manifests):
    by_id={m["approval_id"]:m for m in manifests};replaced=set()
    for m in manifests:
        prev=m["supersedes"]
        if prev is None:continue
        if prev not in by_id or prev in replaced:raise SyncError("DELETION_APPROVAL_CHAIN_INVALID")
        old=by_id[prev]
        if old["candidate_id"]!=m["candidate_id"] or instant(old["approved_at"])>=instant(m["approved_at"]):raise SyncError("DELETION_APPROVAL_CHAIN_INVALID")
        replaced.add(prev)
    tips=[m for m in manifests if m["approval_id"] not in replaced]
    if len({m["candidate_id"] for m in tips})!=len(tips):raise SyncError("DELETION_APPROVAL_CHAIN_INVALID")
    return tips


def archive_context(manifests, previous, current_registry, master, targets):
    """An archive only removes a whole, explicitly selected missing case.

    Full original observations and identification history stay inside the
    versioned manifest. The active registry is exactly the remaining history;
    the original registry validator is applied before and after the transaction.
    """
    archives=[m for m in manifests if m['action'] in {'archive_research','retire_research','approve_research_photo'}]
    if not archives:return None
    cases={c['case_id']:c for c in build_research_cases(previous)}
    old_by_id={r['observation_id']:r for r in previous['observations']}
    before=archives[0]['registry_before'];validate_registry(before,previous,master)
    target_ids={r['observation_id'] for r in targets};archived=set();seen_cases={};case_actions={}
    for m in archives:
        if m['registry_before']!=before:raise SyncError('DELETION_ARCHIVE_HISTORY_CHANGED')
        for capsule in m['archives']:
            cid=capsule['case']['case_id'];case=cases.get(cid)
            if cid not in m['case_ids'] or case!=capsule['case']:raise SyncError('DELETION_ARCHIVE_CASE_CHANGED')
            ids={p['observation_id'] for p in case['photos']}
            if m['action']=='approve_research_photo':
                if not (ids & target_ids) or not (ids-target_ids):raise SyncError('DELETION_RESEARCH_CASE_WOULD_DISAPPEAR')
            elif not ids<=target_ids:raise SyncError('DELETION_ARCHIVE_CASE_STILL_HAS_LIVE_PHOTOS')
            if cid in seen_cases and (seen_cases[cid]!=capsule or case_actions[cid]!=m['action']):raise SyncError('DELETION_ARCHIVE_ACTION_CONFLICT')
            seen_cases[cid]=capsule;case_actions[cid]=m['action']
            if capsule['observations']!=[old_by_id[p['observation_id']] for p in case['photos']]:raise SyncError('DELETION_ARCHIVE_PHOTOS_CHANGED')
            if capsule['identifications']!=[r for r in before['identifications'] if r['case_id']==cid]:raise SyncError('DELETION_ARCHIVE_HISTORY_CHANGED')
            if m['action']!='approve_research_photo':archived.add(cid)
        if set(m['case_ids'])!={c['case']['case_id'] for c in m['archives']}:raise SyncError('DELETION_ARCHIVE_CASE_CHANGED')
    expected={**before,'identifications':[r for r in before['identifications'] if r['case_id'] not in archived]}
    if current_registry!=expected:raise SyncError('DELETION_ARCHIVE_REGISTRY_NOT_EXACT')
    return before
