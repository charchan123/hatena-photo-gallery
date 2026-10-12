"""Independently validated human adoptions of unique public DOM occurrences.

Never changes the detector, Phase3C validator, or automatic addition eligibility.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import requests
from PIL import Image
from article_sync import SyncError, digest, payload_hash
from sync_exceptions import name_valid

DIRECTORY=Path(__file__).resolve().parent/'sync-migrations/photo-adoptions'
HASH=re.compile(r'^[0-9a-f]{64}$')
FIELDS={'version','migration_id','operation','baseline_snapshot_sha256','article_hash',
        'url_hash','ordinal','observation_id','decision','gallery_name','raw_fingerprint',
        'image_content_sha256','approved_at','reason_sha256','approval'}
RAW_FIELDS=('detected_label','subject_type','gallery_name','legacy_alt','classification_reason',
            'classification_confidence','subject_state_status','taxonomy_canonical_name','taxonomy_match_type')
STATUS='human_reviewed_mushroom'


def fail(code): raise SyncError(code)


def stable_id(ah,uh,ordinal):
    # Disjoint, deterministic namespace. Never article_N / global DOM position.
    return 'obs-'+digest('human-adoption-v1\0'+ah+'\0'+uh+'\0'+str(ordinal))


def validate_manifest(m):
    try:
        if not isinstance(m,dict) or set(m)!=FIELDS: raise ValueError()
        if type(m['version']) is not int or m['version']!=1 or m['operation']!='adopt_unique_public_mushroom_photo': raise ValueError()
        if m['approval']!='explicit_human_photo_adoption' or m['decision'] not in {'named_mushroom','unknown_mushroom'}: raise ValueError()
        for k in ('baseline_snapshot_sha256','article_hash','url_hash','raw_fingerprint','image_content_sha256','reason_sha256'):
            if not isinstance(m[k],str) or not HASH.fullmatch(m[k]): raise ValueError()
        if type(m['ordinal']) is not int or m['ordinal']!=0: raise ValueError()
        if m['observation_id']!=stable_id(m['article_hash'],m['url_hash'],m['ordinal']): raise ValueError()
        if not name_valid(m['gallery_name']): raise ValueError()
        if (m['decision']=='unknown_mushroom')!=(m['gallery_name']=='不明'): raise ValueError()
        if not isinstance(m['approved_at'],str) or datetime.fromisoformat(m['approved_at']).tzinfo is None: raise ValueError()
        if m['migration_id']!=payload_hash({k:v for k,v in m.items() if k!='migration_id'}): raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError): fail('ADOPTION_MANIFEST_INVALID')
    return m


def load_manifests(directory=None):
    directory=Path(DIRECTORY if directory is None else directory)
    if any(p.is_symlink() for p in (directory,*directory.parents)): fail('ADOPTION_STORAGE_UNSAFE')
    if not directory.exists(): return []
    if not directory.is_dir(): fail('ADOPTION_MANIFEST_INVALID')
    result=[];targets=set()
    for file in sorted(directory.iterdir()):
        if file.is_symlink() or not file.is_file() or file.stat().st_size>12000: fail('ADOPTION_MANIFEST_INVALID')
        try:m=validate_manifest(json.loads(file.read_text(encoding='utf-8')))
        except (OSError,ValueError):fail('ADOPTION_MANIFEST_INVALID')
        if file.name!=m['migration_id']+'.json' or m['observation_id'] in targets: fail('ADOPTION_DUPLICATE_OR_PATH_INVALID')
        targets.add(m['observation_id']);result.append(m)
    return result


def public_image_url(src):
    try:
        u=urlsplit(src)
        return (u.scheme=='https' and u.hostname in {'cdn-ak.f.st-hatena.com','cdn.f.st-hatena.com'}
                and not u.username and not u.password and not u.port and not u.fragment
                and u.path.startswith('/images/'))
    except (ValueError,TypeError):return False


class _AnonymousImageAuth(requests.auth.AuthBase):
    def __call__(self, request):
        # Explicit auth object disables ambient .netrc default credentials.
        request.headers.pop('Authorization', None)
        return request


def image_hash(src):
    """Bounded unauthenticated GET to the exact public Hatena CDN URL. No redirects."""
    if not public_image_url(src):fail('ADOPTION_IMAGE_HOST_UNSUPPORTED')
    response=None
    try:
        response=requests.get(src,timeout=(10,30),allow_redirects=False,stream=True,auth=_AnonymousImageAuth())
        if response.status_code!=200 or not response.headers.get('Content-Type','').lower().startswith('image/'):
            fail('ADOPTION_IMAGE_FETCH_FAILED')
        data=bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data)>25_000_000:fail('ADOPTION_IMAGE_TOO_LARGE')
        if not data:fail('ADOPTION_IMAGE_FETCH_FAILED')
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'JPEG','PNG','WEBP'} or image.width*image.height>60_000_000:
                fail('ADOPTION_IMAGE_FORMAT_UNSUPPORTED')
            image.verify()
        return hashlib.sha256(data).hexdigest()
    except SyncError:raise
    except Exception:fail('ADOPTION_IMAGE_FETCH_OR_DECODE_FAILED')
    finally:
        if response is not None:response.close()


def fingerprint(image,shadow):
    return payload_hash({'image':image,'raw_classification':{k:shadow.get(k) for k in RAW_FIELDS}})


def source_occurrences(files,metadata,shadows,articles):
    """Read ORIGINAL public DOM and original detector rows; no synthetic rows."""
    import os
    from bs4 import BeautifulSoup
    by_key={};counts=Counter()
    for shadow in shadows:
        by_key.setdefault((os.path.normpath(shadow['article_path']),shadow['src']),[]).append(shadow)
    result={}
    for file in files:
        meta=metadata[os.path.normpath(str(file))];ah=digest(meta['article_id']);local=Counter()
        for node in BeautifulSoup(Path(file).read_text(encoding='utf-8'),'html.parser').find_all('img'):
            src=node.get('src')
            if not src:continue
            ordinal=local[src];local[src]+=1;counts[digest(src)]+=1
            image=next(i for i in articles[ah]['images'] if i['url_hash']==digest(src) and i['ordinal']==ordinal)
            queue=by_key.get((os.path.normpath(str(file)),src),[])
            shadow=queue[ordinal] if ordinal<len(queue) else {}
            result[(ah,digest(src),ordinal)]={'src':src,'article':{**meta,'article_path':str(file)},
                'image':image,'shadow':deepcopy(shadow),'fingerprint':fingerprint(image,shadow)}
    for r in result.values():r['global_url_count']=counts[digest(r['src'])]
    return result


def check_target(m,raw,previous,sources,*,applied=False,verify_image=True):
    from sync_retirement import load_manifest as retirement_manifest
    validate_manifest(m)
    if m['article_hash']==retirement_manifest()['target_article_sha256']:fail('ADOPTION_RETIRED_ARTICLE_FORBIDDEN')
    source=sources.get((m['article_hash'],m['url_hash'],m['ordinal']))
    if not source:fail('ADOPTION_PUBLIC_SOURCE_MISSING')
    if source['global_url_count']!=1:fail('ADOPTION_DUPLICATE_URL')
    if not public_image_url(source['src']):fail('ADOPTION_IMAGE_HOST_UNSUPPORTED')
    if source['fingerprint']!=m['raw_fingerprint']:fail('ADOPTION_SOURCE_CHANGED')
    # No gate-bypass for a raw gallery candidate, regardless of its confidence.
    if any(r['src']==source['src'] for r in raw['observations']):fail('ADOPTION_ALREADY_IN_RAW_GALLERY')
    existing=[r for r in previous['observations'] if r['src']==source['src'] or r['observation_id']==m['observation_id']]
    if applied:
        if len(existing)!=1 or existing[0]['observation_id']!=m['observation_id']:fail('ADOPTION_EXISTING_IDENTITY_CHANGED')
        row=existing[0]
        if digest(row['article']['article_id'])!=m['article_hash'] or digest(row['src'])!=m['url_hash'] or row['gallery_name']!=m['gallery_name']:
            fail('ADOPTION_EXISTING_IDENTITY_CHANGED')
    elif existing:fail('ADOPTION_TARGET_ALREADY_PUBLISHED')
    if m['decision']=='named_mushroom':
        names={r['canonical_name'] for r in raw['reference_data']['subject_taxonomy']['entries'] if r.get('subject_type')=='mushroom'}
        if m['gallery_name'] not in names:fail('ADOPTION_NAME_NOT_IN_EXISTING_TAXONOMY')
    if verify_image and image_hash(source['src'])!=m['image_content_sha256']:fail('ADOPTION_IMAGE_CONTENT_CHANGED')
    return source


def validate_ledger(ledger,portal):
    try:
        if not isinstance(ledger,list):raise ValueError()
        rows={r['observation_id']:r for r in portal['observations']};seen=set();targets=set()
        for record in ledger:
            fields={'migration_id','manifest_sha256','observation_id','article_hash','url_hash','ordinal','name_sha256','image_content_sha256','applied_at'}
            if not isinstance(record,dict) or set(record)!=fields:raise ValueError()
            if any(not isinstance(record[k],str) or not HASH.fullmatch(record[k]) for k in ('migration_id','manifest_sha256','article_hash','url_hash','name_sha256','image_content_sha256')):raise ValueError()
            if type(record['ordinal']) is not int or record['ordinal']!=0:raise ValueError()
            oid=record['observation_id']
            if oid!=stable_id(record['article_hash'],record['url_hash'],0) or oid in targets or record['migration_id'] in seen or oid not in rows:raise ValueError()
            seen.add(record['migration_id']);targets.add(oid);r=rows[oid]
            if digest(r['article']['article_id'])!=record['article_hash'] or digest(r['src'])!=record['url_hash'] or digest(r['gallery_name'])!=record['name_sha256']:raise ValueError()
            h=r['human_review']
            if set(h)!={'kind','migration_id','decision','approved_at','reason_sha256','raw_fingerprint','image_content_sha256'}:raise ValueError()
            if r['classification']['status']!=STATUS or h['kind']!='manual_adoption' or h['migration_id']!=record['migration_id']:raise ValueError()
            if h['decision'] not in {'named_mushroom','unknown_mushroom'} or (h['decision']=='unknown_mushroom')!=(r['gallery_name']=='不明'):raise ValueError()
            if h['image_content_sha256']!=record['image_content_sha256'] or any(not HASH.fullmatch(h[k]) for k in ('reason_sha256','raw_fingerprint')):raise ValueError()
            if datetime.fromisoformat(h['approved_at']).tzinfo is None:raise ValueError()
            if datetime.fromisoformat(record['applied_at']).tzinfo is None:raise ValueError()
        if {r['observation_id'] for r in rows.values() if r.get('human_review',{}).get('kind')=='manual_adoption' or r.get('classification',{}).get('status')==STATUS}!=targets:raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):fail('ADOPTION_LEDGER_INVALID')
    return ledger


class Adoptions:
    def __init__(self,previous,snapshot):
        self.previous=previous;self.snapshot=snapshot;self.manifests=load_manifests();self.events=[];self.targets=[]
        self.ledger=deepcopy(validate_ledger((snapshot or {}).get('manual_adoptions',[]),previous))
        by_id={m['migration_id']:m for m in self.manifests}
        for r in self.ledger:
            m=by_id.get(r['migration_id'])
            if not m or payload_hash(m)!=r['manifest_sha256'] or m['observation_id']!=r['observation_id']:fail('ADOPTION_MANIFEST_MISSING_OR_CHANGED')

    def project(self,raw,entries,shadows,sources):
        if not self.manifests:return entries,shadows
        if not self.snapshot:fail('ADOPTION_SNAPSHOT_REQUIRED')
        result=deepcopy(entries);view_shadows=deepcopy(shadows);applied={r['migration_id'] for r in self.ledger}
        for m in self.manifests:
            old=m['migration_id'] in applied
            if not old and m['baseline_snapshot_sha256']!=payload_hash(self.snapshot):fail('ADOPTION_STALE_SNAPSHOT')
            source=check_target(m,raw,self.previous,sources,applied=old)
            if not old:self.events.append(m['migration_id'])
            # A synthetic projection row has no detector authority. Original
            # shadows/inventory/audit remain untouched. annotate() restores raw
            # fields and labels the independent HUMAN decision explicitly.
            synthetic={'src':source['src'],'article_path':source['article']['article_path'],
                       'gallery_name':m['gallery_name'],'subject_type':None,'detected_label':None}
            view_shadows.append(synthetic);result.append({'src':source['src'],'alt':m['gallery_name']})
            self.targets.append((m,source,len(result)-1))
        return result,view_shadows

    def annotate(self,portal):
        result=deepcopy(portal)
        for m,source,index in self.targets:
            row=result['observations'][index]
            if row['src']!=source['src'] or row['gallery_name']!=m['gallery_name'] or digest(row['article']['article_id'])!=m['article_hash']:
                fail('ADOPTION_PROJECTION_INVALID')
            row['observation_id']=m['observation_id'];row['classification']={
                'status':STATUS,'subject_type':source['shadow'].get('subject_type'),
                'detected_label':source['shadow'].get('detected_label'),
                'shadow_gallery_name':source['shadow'].get('gallery_name'),
                **{k:source['shadow'].get(k) for k in RAW_FIELDS if k not in {'subject_type','detected_label','gallery_name','legacy_alt'}}}
            row['human_review']={'kind':'manual_adoption','migration_id':m['migration_id'],
                'decision':m['decision'],'approved_at':m['approved_at'],'reason_sha256':m['reason_sha256'],
                'raw_fingerprint':m['raw_fingerprint'],'image_content_sha256':m['image_content_sha256']}
        # Recompute only classification tallies; all standard grouping is already
        # built from the complete projected entries by the ordinary portal builder.
        from portal_data import CLASSIFICATION_STATUSES
        counts=Counter(r['classification']['status'] for r in result['observations'])
        for status in (*CLASSIFICATION_STATUSES,STATUS):result['summary'][status+'_count']=counts[status]
        for subject in result['subjects']:
            subject['classification_counts']=dict(sorted(Counter(r['classification']['status'] for r in result['observations'] if r['gallery_name']==subject['gallery_name']).items()))
        return result

    def without_manual(self,portal):
        result=deepcopy(portal);ids={m['observation_id'] for m in self.manifests}
        result['observations']=[r for r in result['observations'] if r['observation_id'] not in ids]
        result['summary']['observation_count']=len(result['observations'])
        return result

    def finish(self,portal,timestamp):
        # Recheck bytes at the final publication gate, not just at projection.
        for m,source,_ in self.targets:
            if image_hash(source['src'])!=m['image_content_sha256']:fail('ADOPTION_IMAGE_CONTENT_CHANGED')
        for mid in self.events:
            m=next(m for m in self.manifests if m['migration_id']==mid)
            self.ledger.append({'migration_id':mid,'manifest_sha256':payload_hash(m),'observation_id':m['observation_id'],
                'article_hash':m['article_hash'],'url_hash':m['url_hash'],'ordinal':0,'name_sha256':digest(m['gallery_name']),
                'image_content_sha256':m['image_content_sha256'],'applied_at':timestamp})
        validate_ledger(self.ledger,portal)
        return self.ledger
