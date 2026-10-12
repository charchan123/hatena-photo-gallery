"""Narrow human name migrations, AFTER the unmodified Phase3C validation.

No addition, deletion, URL replacement, taxonomy edit or blanket permission.
Every migration is bound to one already published, globally unique photo.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
import re

from article_sync import SyncError, digest, payload_hash, observation_groups

ROOT = Path(__file__).resolve().parent
DIRECTORY = ROOT / 'sync-migrations/photo-names'
HASH = re.compile(r'^[0-9a-f]{64}$')
FIELDS = {'version','migration_id','operation','baseline_snapshot_sha256',
          'article_hash','url_hash','observation_id','old_name','proposed_name',
          'raw_fingerprint','approved_at','reason_sha256','approval'}


def fail(code):
    raise SyncError(code)


def name_valid(name):
    return (isinstance(name,str) and 0 < len(name) <= 120 and name == name.strip()
            and not any(ord(c) < 32 or ord(c) == 127 for c in name))


def validate_manifest(m):
    try:
        if not isinstance(m,dict) or set(m) != FIELDS: raise ValueError()
        if type(m['version']) is not int or m['version'] != 1: raise ValueError()
        if m['operation'] != 'rename_existing_unique_photo' or m['approval'] != 'explicit_human_name_confirmation': raise ValueError()
        for k in ('baseline_snapshot_sha256','article_hash','url_hash','raw_fingerprint','reason_sha256'):
            if not isinstance(m[k],str) or not HASH.fullmatch(m[k]): raise ValueError()
        if not isinstance(m['observation_id'],str) or not re.fullmatch(r'obs-[A-Za-z0-9_-]{1,100}',m['observation_id']): raise ValueError()
        if not all(name_valid(m[k]) and m[k] != '不明' for k in ('old_name','proposed_name')) or m['old_name']==m['proposed_name']: raise ValueError()
        if not isinstance(m['approved_at'],str) or datetime.fromisoformat(m['approved_at']).tzinfo is None: raise ValueError()
        if m['migration_id'] != payload_hash({k:v for k,v in m.items() if k != 'migration_id'}): raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError): fail('NAME_MIGRATION_INVALID')
    return m


def load_manifests(directory=None):
    directory=Path(DIRECTORY if directory is None else directory)
    if any(p.is_symlink() for p in (directory,*directory.parents)): fail('NAME_MIGRATION_STORAGE_UNSAFE')
    if not directory.exists(): return []
    if not directory.is_dir(): fail('NAME_MIGRATION_INVALID')
    result=[]; ids=set(); targets=set()
    for file in sorted(directory.iterdir()):
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 12000: fail('NAME_MIGRATION_INVALID')
        try: m=validate_manifest(json.loads(file.read_text(encoding='utf-8')))
        except (OSError,ValueError): fail('NAME_MIGRATION_INVALID')
        if file.name != m['migration_id']+'.json' or m['migration_id'] in ids or m['observation_id'] in targets: fail('NAME_MIGRATION_DUPLICATE_OR_PATH_INVALID')
        ids.add(m['migration_id']); targets.add(m['observation_id']); result.append(m)
    return result


def raw_fingerprint(row, image):
    # Stable article ID / exact URL are checked separately. No article_N or global
    # DOM index. Unrelated text updates may proceed; target evidence changes cannot.
    return payload_hash({'image':image,'name':row['gallery_name'],'classification':row['classification']})


def protected_ids(portal, data=ROOT/'data'):
    from research_ui import build_research_cases
    from article_sync import read_json
    best=read_json(Path(data)/'best-shots.json')
    registry=read_json(Path(data)/'research-identifications.json')
    result={r['observation_id'] for r in best['entries']}
    cases=build_research_cases(portal)
    result.update(p['observation_id'] for c in cases for p in c['photos'])
    # Protect registry cases as well, including reopened/identified histories.
    known={c['case_id'] for c in cases}
    if any(r.get('case_id') not in known for r in registry['identifications']): fail('PROTECTED_REFERENCE_ERROR')
    return result


def validate_ledger(ledger,portal):
    try:
        if not isinstance(ledger,list): raise ValueError()
        rows={r['observation_id']:r for r in portal['observations']}; seen=set(); targets=set()
        for r in ledger:
            if not isinstance(r,dict) or set(r) != {'migration_id','manifest_sha256','observation_id','name_sha256','applied_at'}: raise ValueError()
            if any(not isinstance(r[k],str) or not HASH.fullmatch(r[k]) for k in ('migration_id','manifest_sha256','name_sha256')): raise ValueError()
            if r['migration_id'] in seen or r['observation_id'] in targets or r['observation_id'] not in rows: raise ValueError()
            seen.add(r['migration_id']); targets.add(r['observation_id'])
            if digest(rows[r['observation_id']]['gallery_name']) != r['name_sha256']: raise ValueError()
            if datetime.fromisoformat(r['applied_at']).tzinfo is None: raise ValueError()
    except (ValueError,KeyError,TypeError): fail('NAME_MIGRATION_LEDGER_INVALID')
    return ledger


def check_target(m, raw, previous, articles, *, data=ROOT/'data'):
    validate_manifest(m); observation_groups(raw); observation_groups(previous)
    old=[r for r in previous['observations'] if r['observation_id']==m['observation_id']]
    matches=[r for r in raw['observations'] if digest(r['article']['article_id'])==m['article_hash'] and digest(r['src'])==m['url_hash']]
    if len(old)!=1 or len(matches)!=1: fail('NAME_MIGRATION_TARGET_MISSING_OR_AMBIGUOUS')
    before,row=old[0],matches[0]
    if digest(before['article']['article_id'])!=m['article_hash'] or digest(before['src'])!=m['url_hash']: fail('NAME_MIGRATION_IDENTITY_CHANGED')
    # Global exact-URL uniqueness: portal shadow fallback cannot select another
    # article/duplicate occurrence. Duplicate URLs are intentionally unsupported.
    images=[im for article in articles.values() for im in article['images'] if im['url_hash']==m['url_hash']]
    if len(images)!=1 or images[0]['ordinal']!=0 or sum(r['src']==row['src'] for r in raw['observations'])!=1: fail('NAME_MIGRATION_DUPLICATE_URL')
    if images[0] not in articles.get(m['article_hash'],{}).get('images',[]): fail('NAME_MIGRATION_IDENTITY_CHANGED')
    if row.get('shadow_match_status') not in {'exact_gallery_name','exact_legacy_alt'}: fail('NAME_MIGRATION_SHADOW_AMBIGUOUS')
    if raw_fingerprint(row,images[0]) != m['raw_fingerprint']: fail('NAME_MIGRATION_SOURCE_CHANGED')
    if before['gallery_name'] not in {m['old_name'],m['proposed_name']}: fail('NAME_MIGRATION_OLD_NAME_CHANGED')
    if m['observation_id'] in protected_ids(previous,data): fail('NAME_MIGRATION_PROTECTED_REFERENCE')
    names={r['canonical_name'] for r in raw['reference_data']['subject_taxonomy']['entries'] if r.get('subject_type')=='mushroom'}
    if m['proposed_name'] not in names: fail('NAME_MIGRATION_NAME_NOT_IN_EXISTING_TAXONOMY')
    return row


class NameMigrations:
    def __init__(self,previous,snapshot,*,directory=None,data=ROOT/'data'):
        self.previous=previous; self.snapshot=snapshot; self.data=data
        self.manifests=load_manifests(directory); self.events=[]
        self.ledger=deepcopy(validate_ledger((snapshot or {}).get('name_migrations',[]),previous))
        by_id={m['migration_id']:m for m in self.manifests}
        for r in self.ledger:
            if r['migration_id'] not in by_id or r['manifest_sha256']!=payload_hash(by_id[r['migration_id']]): fail('NAME_MIGRATION_MANIFEST_MISSING_OR_CHANGED')

    def project(self,raw,entries,articles):
        if not self.manifests: return entries
        if not self.snapshot: fail('NAME_MIGRATION_SNAPSHOT_REQUIRED')
        result=deepcopy(entries); applied={r['migration_id'] for r in self.ledger}
        effective=deepcopy(self.previous)
        for m in self.manifests:
            row=check_target(m,raw,self.previous,articles,data=self.data)
            if m['migration_id'] not in applied:
                if m['baseline_snapshot_sha256']!=payload_hash(self.snapshot): fail('NAME_MIGRATION_STALE_SNAPSHOT')
                before=next(r for r in self.previous['observations'] if r['observation_id']==m['observation_id'])
                if before['gallery_name']!=m['old_name']: fail('NAME_MIGRATION_OLD_NAME_CHANGED')
                self.events.append(m['migration_id'])
            else:
                before=next(r for r in self.previous['observations'] if r['observation_id']==m['observation_id'])
                if before['gallery_name']!=m['proposed_name']: fail('NAME_MIGRATION_LEDGER_INVALID')
            index=row['production_index']
            if result[index]['src']!=row['src'] or result[index]['alt']!=row['gallery_name']: fail('NAME_MIGRATION_PROJECTION_INVALID')
            result[index]['alt']=m['proposed_name']
            next(r for r in effective['observations'] if r['observation_id']==m['observation_id'])['gallery_name']=m['proposed_name']
        if Counter(r['src'] for r in result)!=Counter(r['src'] for r in entries) or len(result)!=len(entries): fail('NAME_MIGRATION_PROJECTION_INVALID')
        self.effective_previous=effective
        return result

    def finish(self,portal,timestamp):
        for mid in self.events:
            m=next(m for m in self.manifests if m['migration_id']==mid)
            self.ledger.append({'migration_id':mid,'manifest_sha256':payload_hash(m),
                'observation_id':m['observation_id'],'name_sha256':digest(m['proposed_name']),'applied_at':timestamp})
        validate_ledger(self.ledger,portal)
        return self.ledger
