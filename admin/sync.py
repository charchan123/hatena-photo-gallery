"""Local-only sync review: read public state, GET live source, persist human audit.

The safe production capability is deliberately narrow: adopt *new* photographs
already eligible under unchanged Phase3C. Renames, URL swaps and deletions remain
individual migrations. Neither a button nor a review record bypasses that rule.
"""
from collections import Counter
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlsplit

from article_sync import (SAFE_NEW, REVIEW_STATES, SyncError, SyncRun, compare_inventory,
    digest, inventory, observation_groups, payload_hash, read_json, validate_snapshot)
from sync_review import (APPROVAL_PATH, identity, occurrence_rows, photo_fingerprint,
                         load_approvals, validate_approvals)
from .core import ROOT
from .git_workflow import run

LOCK = threading.RLock()
ACTION_CACHE = {'at': 0, 'value': None}
LOCAL = ROOT / 'admin/local-state/sync'
GROUPS = ['blocker', 'new', 'legacy', 'migration', 'reviewed', 'held']
DECISIONS = {'adopt', 'hold', 'no_change', 'propose_name', 'exclude', 'confirm_url', 'delete', 'pending'}


class ReviewError(ValueError):
    pass


def now(): return datetime.now(timezone.utc).isoformat()


def safe_url(value, *, image=False):
    if not isinstance(value, str): return None
    u = urlsplit(value)
    try:
        if u.port: return None
    except ValueError: return None
    allowed = {'cdn-ak.f.st-hatena.com', 'cdn.f.st-hatena.com'} if image else {'exsudoporus-ruber.hatenablog.jp'}
    return value if u.scheme == 'https' and u.hostname in allowed and not u.username and not u.password and not u.port else None


def public_publication(*, refresh=False):
    """Use a single immutable gh-pages commit, not output/ or a mix of HTTP caches."""
    if refresh: run(['git', 'fetch', 'origin', 'gh-pages'])
    sha = run(['git', 'rev-parse', 'origin/gh-pages']).stdout.strip()
    result = {'publication_sha': sha}
    for name in ('portal-data.json','article-sync-snapshot.json','article-sync-status.json','phase3c-production-status.json'):
        try:
            result[name] = json.loads(run(['git','show',sha + ':' + name]).stdout)
        except Exception: raise ReviewError('PUBLIC_SNAPSHOT_UNAVAILABLE') from None
    portal, snapshot = result['portal-data.json'], result['article-sync-snapshot.json']
    validate_snapshot(snapshot, portal)
    phase = result['phase3c-production-status.json']
    if (phase.get('cutover_active') is not True or phase.get('validation', {}).get('valid') is not True
            or phase.get('production_image_count') != len(portal['observations'])):
        raise ReviewError('PUBLIC_SNAPSHOT_UNHEALTHY')
    return result


@contextmanager
def isolated_generator():
    """All temporary article bodies/cache/generated files confined to one directory.

    Global generator paths require serialized requests. No response bodies are
    logged, returned to the browser or persisted. Only published photos are used.
    """
    import main
    with LOCK, tempfile.TemporaryDirectory(prefix='kinoko-review-') as temporary:
        warm_cache = Path(main.CACHE_FILE)
        seed = warm_cache.read_bytes() if warm_cache.is_file() and warm_cache.stat().st_size < 25_000_000 else None
        roots = {main.OUTPUT_DIR: str(Path(temporary)/'output'),
                 main.CACHE_DIR: str(Path(temporary)/'cache'),
                 main.ARTICLES_DIR: str(Path(temporary)/'articles')}
        originals = {}
        for key, value in list(vars(main).items()):
            if not isinstance(value, str): continue
            for old, new in roots.items():
                if value == old or value.startswith(old + os.sep):
                    originals[key] = value; setattr(main, key, new + value[len(old):]); break
        for path in roots.values(): Path(path).mkdir(parents=True, exist_ok=True)
        if seed is not None: Path(main.CACHE_FILE).write_bytes(seed)
        try:
            with open(os.devnull, 'w') as silent, redirect_stdout(silent), redirect_stderr(silent):
                yield main, Path(temporary)
        finally:
            for key, value in originals.items(): setattr(main, key, value)


def authenticated():
    import main
    return all((main.HATENA_USER, main.HATENA_BLOG_ID, main.HATENA_API_KEY))


def latest_actions():
    """Best-effort GET/read-only metadata and sanitized failed-run report.

    Public success data remain available even if gh/credentials/artifacts fail.
    Never echo subprocess stderr, raw artifact bodies or authentication details.
    """
    if time.monotonic() - ACTION_CACHE['at'] < 60: return ACTION_CACHE['value']
    value = {'available':False, 'error_code':None, 'report_available':False}
    try:
        result = run(['gh','run','list','--workflow','generate.yml','--limit','1',
                      '--json','databaseId,status,conclusion,url,headSha'],check=False)
        rows=json.loads(result.stdout) if result.returncode==0 else []
        if rows:
            row=rows[0]
            if type(row.get('databaseId')) is not int: raise ValueError()
            value={**value,'available':True,**row}
            if row.get('conclusion') not in (None,'success'):
                attempt=run(['gh','api',f"repos/charchan123/hatena-photo-gallery/actions/runs/{row['databaseId']}",
                             '--method','GET','--jq','.run_attempt'],check=False).stdout.strip()
                if not attempt.isdigit(): raise ValueError()
                with tempfile.TemporaryDirectory(prefix='kinoko-sync-report-') as temporary:
                    result=run(['gh','run','download',str(row['databaseId']),
                        '--name',f"article-sync-report-{row['databaseId']}-{attempt}",'--dir',temporary],check=False)
                    report=Path(temporary)/'article-sync-report.json'
                    if result.returncode==0 and report.is_file() and not report.is_symlink() and report.stat().st_size < 2_000_000:
                        raw=json.loads(report.read_text(encoding='utf-8'))
                        code=raw.get('error_code')
                        import re
                        if isinstance(code,str) and re.fullmatch(r'[A-Z0-9_]{1,90}',code):
                            value.update(error_code=code,report_available=True)
    except Exception: pass
    ACTION_CACHE.update(at=time.monotonic(),value=value)
    return value


class Captured(Exception): pass


class Capture:
    def __init__(self):
        self.status = {'fetch_audit': {}}; self.excluded_draft_hashes = set()
    def capture(self, files, metadata): self.files, self.metadata = files, metadata
    def reconcile(self, portal, shadows):
        self.portal = portal; self.shadows = shadows
        self.articles = inventory(self.files, self.metadata, shadows)
        raise Captured()


def live_capture():
    if not authenticated(): raise ReviewError('LOCAL_HATENA_CREDENTIALS_UNAVAILABLE')
    try:
        with isolated_generator() as (main, _):
            captured = Capture()
            original_exif_builder = main.build_exif_cache
            # Classification/Phase3C are real. A review listing does not need to
            # download hundreds of photographs merely to fill absent EXIF dates.
            # Known cache dates survive; absent metadata remain explicitly absent.
            main.build_exif_cache = lambda entries, cache: cache
            try:
                try: main.build_gallery(sync_run=captured)
                except Captured: pass
            finally: main.build_exif_cache = original_exif_builder
            if not hasattr(captured, 'portal'): raise ReviewError('LIVE_PHASE3C_CAPTURE_FAILED')
            phase = read_json(main.PHASE3C_PRODUCTION_STATUS_FILE)
            if phase.get('cutover_active') is not True or phase.get('validation', {}).get('valid') is not True:
                raise ReviewError('LIVE_PHASE3C_VALIDATION_FAILED')
            # Build photo details from public-only Atom metadata + original DOM.
            from bs4 import BeautifulSoup
            photos = {}
            shadow_queues = {}
            for s in captured.shadows:
                shadow_queues.setdefault((os.path.normpath(s['article_path']), s['src']), []).append(s)
            for file in captured.files:
                meta = captured.metadata[os.path.normpath(str(file))]
                ah = digest(meta['article_id']); counts = Counter()
                for image in BeautifulSoup(Path(file).read_text(encoding='utf-8'),'html.parser').find_all('img'):
                    src = image.get('src')
                    if not src: continue
                    ordinal = counts[src]; counts[src] += 1
                    queue = shadow_queues.get((os.path.normpath(str(file)), src), [])
                    shadow = queue[ordinal] if ordinal < len(queue) else {}
                    photos[(ah, digest(src), ordinal)] = {
                        'thumbnail': safe_url(src, image=True), 'article_title': meta.get('title'),
                        'article_url': safe_url(meta.get('url')), 'published': meta.get('published'),
                        'updated': meta.get('updated'), 'detected_name': shadow.get('detected_label')}
            return {'articles': captured.articles, 'portal': captured.portal, 'photos': photos,
                    'excluded_draft_hashes': sorted(captured.excluded_draft_hashes),
                    'fetch_audit': captured.status['fetch_audit']}
    except (ReviewError, SyncError): raise
    except Exception: raise ReviewError('LIVE_FETCH_OR_GENERATION_FAILED') from None


def candidates(publication, live=None):
    old_portal = publication['portal-data.json']; snap = publication['article-sync-snapshot.json']
    before = snap['payload']['articles']; articles = live['articles'] if live else before
    current = live['portal'] if live else old_portal
    old_rows = occurrence_rows(old_portal); rows = occurrence_rows(current)
    old_images = {(ah, x['url_hash'], x['ordinal']): x for ah, a in before.items() for x in a['images']}
    images = {(ah, x['url_hash'], x['ordinal']): x for ah, a in articles.items() for x in a['images']}
    from sync_retirement import load_manifest
    retired_article = load_manifest()['target_article_sha256']
    result = []
    image_counts = Counter(k[:2] for k in images)
    row_counts = Counter(k[:2] for k in rows)
    for key in sorted(images.keys() | old_images.keys()):
        ah, uh, ordinal = key; image = images.get(key); row = rows.get(key); old = old_rows.get(key)
        old_image = old_images.get(key)
        removed = image is None
        new = old_image is None
        changed = old_image is not None and image is not None and image != old_image
        old_change = old is not None and (row is None or row.get('gallery_name') != old.get('gallery_name'))
        state = image['state'] if image else old_image['state']
        uncertain = state in REVIEW_STATES or (row and row.get('classification', {}).get('status') not in SAFE_NEW)
        if not (new or changed or removed or old_change or uncertain): continue
        classification = row.get('classification', {}) if row else {}
        adoptable = bool(ah != retired_article and live and new and row and not old and image_counts[key[:2]] == row_counts[key[:2]] and
            classification.get('status') in SAFE_NEW and classification.get('subject_state_status') == 'accepted_subject'
            and classification.get('classification_confidence') == 'high')
        if ah == retired_article: group = 'migration'; kind = 'retired_article_requires_individual_review'
        elif removed or old_change: group = 'migration'; kind = 'removed_or_changed_existing_photo'
        elif new: group = 'new' if adoptable or row is None else 'blocker'; kind = 'new_gallery_photo' if row else 'new_non_gallery_image'
        elif changed: group = 'blocker' if old_change else 'legacy'; kind = 'classification_change'
        else: group = 'legacy'; kind = 'legacy_classification_review'
        detail = (live.get('photos', {}).get(key, {}) if live else {})
        source = row or old
        if source:
            article = source['article']
            detail = {**{'thumbnail': safe_url(source['src'], image=True), 'article_title': article.get('title'),
                'article_url': safe_url(article.get('url')), 'published': article.get('published'),
                'updated': article.get('updated'), 'detected_name': source.get('classification',{}).get('detected_label')}, **detail}
        adoptable = adoptable and bool(detail.get('thumbnail') and detail.get('article_url'))
        if new and row and not adoptable and ah != retired_article: group = 'blocker'
        protected = False
        if old:
            # All existing identities are protected by the normal gate. Explicit
            # curated reference protection is also checked in preview/finalize.
            protected = True
        result.append({'candidate_id': identity(*key), 'article_hash': ah, 'url_hash': uh, 'ordinal': ordinal,
            'change_type': kind, 'group': group, 'state': state, 'reason': image['reason'] if image else 'missing',
            'current_name': old.get('gallery_name') if old else None,
            'candidate_name': row.get('gallery_name') if row else None,
            'observation_id': old.get('observation_id') if old else None,
            'capture_date': (source.get('capture') or {}).get('date') if source else None,
            'previous_state': old_image['state'] if old_image else None,
            'classification': classification, 'protected_existing': protected,
            'fingerprint': photo_fingerprint(articles.get(ah, {}), image, row),
            'adoptable': adoptable, 'individual_migration_required': not adoptable and kind != 'legacy_classification_review',
            **detail})
    rank = {v:i for i,v in enumerate(GROUPS)}
    return sorted(result, key=lambda r:(rank[r['group']], r['candidate_id']))


class SyncReview:
    def __init__(self, root=LOCAL):
        self.root = Path(root); self.publication = None; self.live = None
        self.rows = []; self.bundle_id = None; self.error = None; self.last_preview = None
        self.decisions = {}; self.audit = []
        self._load()

    def _check_storage(self):
        if any(p.is_symlink() for p in (self.root, *self.root.parents)):
            raise ReviewError('LOCAL_STATE_UNSAFE')

    def _load(self):
        self._check_storage()
        file = self.root / 'review.json'
        if file.exists():
            if self.root.is_symlink() or file.is_symlink(): raise ReviewError('LOCAL_STATE_UNSAFE')
            try:
                value = json.loads(file.read_text(encoding='utf-8'))
                if value.get('version') != 1 or not isinstance(value.get('decisions'), dict) or not isinstance(value.get('audit'),list):
                    raise ValueError()
                self.decisions, self.audit = value['decisions'], value['audit']
            except (OSError, ValueError): raise ReviewError('LOCAL_STATE_CORRUPT') from None

    def _save(self):
        self._check_storage()
        if self.root.is_symlink(): raise ReviewError('LOCAL_STATE_UNSAFE')
        self.root.mkdir(parents=True,exist_ok=True)
        file = self.root/'review.json'
        if file.is_symlink(): raise ReviewError('LOCAL_STATE_UNSAFE')
        raw = json.dumps({'version':1,'decisions':self.decisions,'audit':self.audit},ensure_ascii=False,indent=2)
        fd, temporary = tempfile.mkstemp(dir=self.root, prefix='review-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as out: out.write(raw+'\n')
            os.replace(temporary,file)
        finally:
            if Path(temporary).exists(): Path(temporary).unlink()

    def refresh(self, *, fetch=False, with_live=False):
        with LOCK:
            self.last_preview = None
            ACTION_CACHE['at'] = 0
            try:
                publication = public_publication(refresh=fetch)
                live = live_capture() if with_live else None
                self.install(publication, live)
                self.error = None
            except Exception as error:
                self.error = str(error) if isinstance(error,(ReviewError,SyncError)) else 'SYNC_REVIEW_UNAVAILABLE'
                # Failed retrieval must not leave an older live batch actionable.
                self.live = None; self.last_preview = None
                if self.publication: self.install(self.publication, None)
        return self.dashboard()

    def install(self, publication, live=None):
        validate_snapshot(publication['article-sync-snapshot.json'],publication['portal-data.json'])
        self.publication, self.live = publication, live
        self.rows = candidates(publication, live)
        self.inventory_hash = payload_hash(live['articles'] if live else publication['article-sync-snapshot.json']['payload']['articles'])
        self.bundle_id = payload_hash({'base':publication['article-sync-snapshot.json']['sha256'],
            'inventory':self.inventory_hash,'candidates':self.rows, 'live':live is not None})

    def dashboard(self):
        if not self.publication: return {'available':False,'error':self.error or 'PUBLIC_STATE_NOT_LOADED'}
        status = self.publication['article-sync-status.json']
        time = self.publication['article-sync-snapshot.json']['payload']['last_success_at']
        from datetime import timedelta
        jst = datetime.fromisoformat(time).astimezone(timezone(timedelta(hours=9))).isoformat()
        comparison = compare_inventory(self.publication['article-sync-snapshot.json']['payload']['articles'],self.live['articles']) if self.live else {
            k:status.get(k) for k in ('comparison','new_articles','new_images','deleted_images','possible_url_changes')}
        summary = {**comparison, 'last_success_jst':jst, 'published_articles':len(self.publication['article-sync-snapshot.json']['payload']['articles']),
            'gallery_photos':len(self.publication['portal-data.json']['observations']),
            'classification_review_count':status.get('classification_review_count'),
            'retirement':status.get('retirement'), 'error':self.error,
            'publication_sha':self.publication['publication_sha'], 'snapshot_sha256':self.publication['article-sync-snapshot.json']['sha256']}
        return {'available':True,'summary':summary,'bundle_id':self.bundle_id,'live_review_available':self.live is not None,
            'credentials_available':authenticated(),'notice':'公開済みデータのみ。新しい写真の承認にはローカル認証GET取得が必要です。' if not self.live else '公開記事のみGET取得済み。既存名変更・削除・URL置換は要個別移行です。',
            'groups':dict(Counter(self.view(r)['group'] for r in self.rows)),
            'stale_decisions':sum(d.get('bundle_id') != self.bundle_id for d in self.decisions.values()),
            'history':[{k:record[k] for k in ('event','candidate_id','decision','decided_at','at','application') if k in record}
                       for record in self.audit[-30:]]}

    def view(self, row):
        result = deepcopy(row); d = self.decisions.get(row['candidate_id'])
        fresh = d and d.get('bundle_id') == self.bundle_id
        result['review'] = d if fresh else None; result['stale_review'] = bool(d and not fresh)
        if fresh:
            if d['decision'] == 'hold' or d['decision'] in {'propose_name','exclude','confirm_url','delete'}: result['group']='held'
            elif d['decision'] in {'adopt','no_change'}: result['group']='reviewed'
        return result

    def page(self, query='', group='', page=1):
        if group and group not in GROUPS: raise ReviewError('INVALID_FILTER')
        if not isinstance(query,str) or len(query)>120 or type(page) is not int or not 1<=page<=10000:
            raise ReviewError('INVALID_FILTER')
        rows = [self.view(r) for r in self.rows]
        rows = [r for r in rows if (not group or r['group']==group) and query.casefold() in ' '.join(str(r.get(k) or '') for k in ('current_name','candidate_name','detected_name','article_title','published','updated','state')).casefold()]
        return {'rows':rows[(page-1)*30:page*30],'total':len(rows),'page':page,'page_size':30,'bundle_id':self.bundle_id}

    def decide(self, body):
        with LOCK:
            allowed = {'candidate_id','bundle_id','decision','comment','proposed_name'}
            if not isinstance(body,dict) or set(body)-allowed: raise ReviewError('INVALID_DECISION_INPUT')
            if body.get('bundle_id') != self.bundle_id or not self.bundle_id: raise ReviewError('STALE_REVIEW')
            row = next((r for r in self.rows if r['candidate_id']==body.get('candidate_id')),None)
            choice = body.get('decision'); comment=body.get('comment',''); name=body.get('proposed_name','')
            if not row or choice not in DECISIONS: raise ReviewError('INVALID_CANDIDATE_OR_DECISION')
            if not isinstance(comment,str) or len(comment)>2000 or not isinstance(name,str) or len(name)>120: raise ReviewError('INVALID_DECISION_INPUT')
            if choice == 'adopt' and not row['adoptable']: raise ReviewError('INDIVIDUAL_MIGRATION_REQUIRED')
            if choice in {'delete','confirm_url','exclude'} and row['protected_existing']:
                raise ReviewError('EXISTING_PHOTO_PROTECTED_USE_INDIVIDUAL_MIGRATION')
            if choice == 'propose_name' and not name.strip(): raise ReviewError('NAME_REQUIRED')
            self.last_preview = None
            d = {'candidate_id':row['candidate_id'],'bundle_id':self.bundle_id,'decision':choice,
                'decided_at':now(),'comment':comment,'proposed_name':name.strip(),
                'base_snapshot_sha256':self.publication['article-sync-snapshot.json']['sha256'],
                'inventory_sha256':self.inventory_hash,'article_hash':row['article_hash'],'url_hash':row['url_hash'],
                'ordinal':row['ordinal'],'change_type':row['change_type'],'fingerprint':row['fingerprint'],
                'application':'requires_individual_migration' if choice in {'propose_name','exclude','confirm_url','delete'} else 'local_review_only' if choice != 'adopt' else 'pending_draft_pr'}
            self.audit.append(d); self.decisions[row['candidate_id']]=d
            self._save()
            return {'saved':True,'application':d['application']}

    def package(self, root=ROOT):
        if not self.live: raise ReviewError('LIVE_REVIEW_REQUIRED')
        if any(a.get('event')=='draft_pr_created' and a.get('bundle_id')==self.bundle_id for a in self.audit):
            raise ReviewError('REVIEW_ALREADY_HAS_DRAFT_PR')
        manifest = deepcopy(load_approvals(root)); additions = []
        for row in self.rows:
            d = self.decisions.get(row['candidate_id'], {})
            if d.get('decision') != 'adopt': continue
            if d.get('bundle_id') != self.bundle_id: raise ReviewError('STALE_REVIEW')
            if not row['adoptable']: raise ReviewError('INDIVIDUAL_MIGRATION_REQUIRED')
            additions.append({k:d[k] for k in ('candidate_id','article_hash','url_hash','ordinal','base_snapshot_sha256','inventory_sha256','fingerprint','decided_at','change_type')}
                | {'name_hash':digest(row['candidate_name']), 'comment_sha256':digest(d['comment']),
                   'decision':'adopt','reviewer':'explicit-local-human-review'})
        if not additions: raise ReviewError('NO_APPROVED_NEW_PHOTOS')
        for row in additions:
            if row not in manifest['approvals']: manifest['approvals'].append(row)
        validate_approvals(manifest)
        return manifest

    def assert_fresh(self, publication, live):
        if not self.publication or publication['article-sync-snapshot.json']['sha256'] != self.publication['article-sync-snapshot.json']['sha256']:
            raise ReviewError('STALE_PUBLIC_SNAPSHOT')
        original = self.bundle_id
        probe = SyncReview.__new__(SyncReview); probe.install(publication, live)
        if probe.bundle_id != original: raise ReviewError('STALE_LIVE_REVIEW')

    def plan(self):
        reviewed = [self.view(row) for row in self.rows]
        return {'additions':[{'candidate_id':r['candidate_id'],'name':r['candidate_name'],
                            'article_title':r.get('article_title')} for r in reviewed
                            if r.get('review',{} ) and r['review']['decision']=='adopt'],
                'existing_names_changed':[], 'deletions':[], 'url_replacements':[],
                'held':[{'candidate_id':r['candidate_id'],'operation':r['review']['decision'],
                         'application':'NOT_APPLIED'} for r in reviewed if r['group']=='held'],
                'unapproved_count':sum(not r.get('review') or r['review']['decision']=='pending' for r in reviewed),
                'existing_references':'unchanged; validated by production preview'}

    def preview(self):
        with LOCK:
            fresh = public_publication(refresh=True); live = live_capture(); self.assert_fresh(fresh,live)
            plan = self.plan()
            try:
                manifest = self.package()
                result = validate_package(fresh, manifest)
            except (ReviewError, SyncError) as error:
                self.last_preview = None
                return {'ready':False, 'error_code':str(error), 'plan':plan}
            result['plan'] = plan
            self.last_preview = {'bundle_id':self.bundle_id,'manifest_sha256':payload_hash(manifest),**result}
            return self.last_preview


def validate_package(publication, manifest):
    """Full, fail-closed real generator in a temporary directory, never publish."""
    from article_sync import run as generate
    with isolated_generator() as (_, temporary):
        previous = temporary/'previous'; previous.mkdir()
        for name in ('portal-data.json','article-sync-snapshot.json','phase3c-production-status.json'):
            (previous/name).write_text(json.dumps(publication[name]),encoding='utf-8')
        output=temporary/'candidate'; report=temporary/'report.json'
        code = generate(previous, output, report, review_manifest=manifest)
        status = read_json(report)
        if code: raise ReviewError(status.get('error_code','PREVIEW_BLOCKED'))
        if (output/'admin').exists() or (output/'sync-reviews').exists(): raise ReviewError('PUBLIC_ISOLATION_FAILED')
        return {'ready':True, 'result':status['result'], 'added_photos':status['human_review']['approved_new_photos'],
                'preserved_photo_ids':status['preserved_photo_ids'], 'gallery_photos':status['gallery_photo_count'],
                'best_shot_references_preserved':status['best_shot_references_preserved'],
                'research_cases_preserved':status['research_cases_preserved'], 'retirement':status['retirement'],
                'generated_html_pages':status['generated_html_pages']}
