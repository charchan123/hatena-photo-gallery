"""One pinned, explicitly approved migration. Never a generic deletion policy."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

from article_sync import SyncError, digest, payload_hash, observation_groups, read_json

MANIFEST_PATH = Path(__file__).parent / 'sync-migrations/hatena-draft-photo-retirement-2026-10-12.json'
MANIFEST_SHA256 = '4e081702d97bb62b0a05de33f02244e3af8376082e31a77fd03feda3b1d0a36c'


def load_manifest():
    try:
        raw = MANIFEST_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            raise ValueError()
        return json.loads(raw)
    except (OSError, ValueError):
        raise SyncError('RETIREMENT_MANIFEST_INVALID') from None


def baseline_commit(directory):
    """A real publication checkout, not an ancestor git repository or a marker file."""
    directory = Path(directory).resolve()
    if not (directory / '.git').exists():
        return None
    try:
        top = subprocess.check_output(['git', '-C', str(directory), 'rev-parse', '--show-toplevel'], text=True, stderr=subprocess.DEVNULL).strip()
        if Path(top).resolve() != directory:
            raise ValueError()
        return subprocess.check_output(['git', '-C', str(directory), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, ValueError, subprocess.CalledProcessError):
        raise SyncError('RETIREMENT_BASELINE_INVALID') from None


def ledger_fields(manifest):
    return {'migration_id': manifest['migration_id'], 'manifest_sha256': MANIFEST_SHA256,
            'baseline_commit': manifest['baseline_commit'],
            'baseline_portal_sha256': manifest['baseline_portal_sha256'],
            'article_sha256': manifest['target_article_sha256'],
            'retired_count': manifest['target_count'], 'result': 'APPLIED'}


def validate_ledger(ledger, portal):
    m = load_manifest()
    try:
        assert isinstance(ledger, dict)
        assert set(ledger) == set(ledger_fields(m)) | {'applied_at'}
        assert all(ledger[k] == v for k, v in ledger_fields(m).items())
        assert datetime.fromisoformat(ledger['applied_at']).tzinfo is not None
        ids = {r['observation_id'] for r in m['observations']}
        assert not ids & {r['observation_id'] for r in portal['observations']}
        assert not any(digest(r['article']['article_id']) == m['target_article_sha256'] for r in portal['observations'])
    except (AssertionError, KeyError, TypeError, ValueError):
        raise SyncError('RETIREMENT_LEDGER_INVALID') from None
    return ledger


def protected_targets(previous, target_ids, directory):
    from best_shot_ui import validate_best_shot_config
    from research_identifications import validate_registry
    from research_ui import build_research_cases
    try:
        best = read_json(Path(directory) / 'best-shots.json')
        registry = read_json(Path(directory) / 'research-identifications.json')
        validate_best_shot_config(best, previous)
        validate_registry(registry, previous, read_json(Path(directory) / 'mushroom-master.json'))
        if any(r['observation_id'] in target_ids for r in best['entries']):
            raise ValueError()
        cases = build_research_cases(previous)
        if any(target_ids & {p['observation_id'] for p in case['photos']} for case in cases):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise SyncError('RETIREMENT_PROTECTED_REFERENCE') from None


class Retirement:
    def __init__(self, previous, snapshot, directory):
        self.manifest = m = load_manifest()
        self.previous = previous
        self.effective_previous = previous
        self.ledger = snapshot.get('retirement') if snapshot else None
        self.targets = {r['observation_id']: r for r in m['observations']}
        existing = {r['observation_id']: r for r in previous['observations']}
        found = self.targets.keys() & existing.keys()
        self.applied_count = 0
        self.initial = bool(found)
        if self.ledger:
            validate_ledger(self.ledger, previous)
            if found:
                raise SyncError('RETIREMENT_LEDGER_INVALID')
        elif found:
            if found != self.targets.keys() or len(existing) != m['baseline_photo_count']:
                raise SyncError('RETIREMENT_TARGET_INVALID')
            if baseline_commit(directory) != m['baseline_commit'] or payload_hash(previous) != m['baseline_portal_sha256']:
                raise SyncError('RETIREMENT_BASELINE_INVALID')
            if snapshot is not None:
                raise SyncError('RETIREMENT_BASELINE_INVALID')
            for oid, expected in self.targets.items():
                r = existing[oid]
                if (r['gallery_name'] != expected['canonical_registered_name']
                        or digest(r['src']) != expected['image_url_sha256']
                        or digest(r['article']['article_id']) != m['target_article_sha256']
                        or digest(r['article'].get('url') or '') != m['old_article_url_sha256']):
                    raise SyncError('RETIREMENT_TARGET_INVALID')
            article_ids = {r['observation_id'] for r in previous['observations']
                           if digest(r['article']['article_id']) == m['target_article_sha256']}
            if article_ids != self.targets.keys():
                raise SyncError('RETIREMENT_TARGET_INVALID')
        elif baseline_commit(directory) is not None:
            # An unrecorded 906-photo production baseline is not a migration proof.
            raise SyncError('RETIREMENT_LEDGER_MISSING')
        self.active = self.initial or self.ledger is not None

    def prepare(self, candidate, articles, draft_hashes, data_directory):
        m = self.manifest
        if m['target_article_sha256'] in articles:
            raise SyncError('RETIRED_ARTICLE_REVIEW_REQUIRED')
        if not self.active:
            return self.previous
        if m['target_article_sha256'] not in draft_hashes:
            raise SyncError('RETIREMENT_DRAFT_NOT_CONFIRMED')
        if self.initial:
            old = observation_groups(self.previous)
            new = observation_groups(candidate)
            missing_ids = {r['observation_id'] for key in old.keys() - new.keys() for r in old[key]}
            if missing_ids != self.targets.keys():
                raise SyncError('RETIREMENT_UNAPPROVED_DISAPPEARANCE')
            protected_targets(self.previous, set(self.targets), data_directory)
            self.effective_previous = deepcopy(self.previous)
            self.effective_previous['observations'] = [r for r in self.previous['observations'] if r['observation_id'] not in self.targets]
            self.effective_previous['summary']['observation_count'] = len(self.effective_previous['observations'])
            self.ledger = {**ledger_fields(m), 'applied_at': datetime.now(timezone.utc).isoformat()}
            self.applied_count = len(self.targets)
        return self.effective_previous

    def status(self):
        return {'migration_id': self.manifest['migration_id'],
                'state': 'APPLIED' if self.applied_count else ('ALREADY_APPLIED' if self.ledger else 'NOT_APPLICABLE'),
                'retired_this_run': self.applied_count,
                'retired_total': self.manifest['target_count'] if self.ledger else 0,
                'manifest_sha256': MANIFEST_SHA256}

    def inspect_output(self, output, portal, articles=None):
        if not self.ledger:
            return {'result': 'NOT_APPLICABLE'}
        validate_ledger(self.ledger, portal)
        m = self.manifest
        legitimate = {digest(r['src']) for r in portal['observations']}
        if articles is not None:
            legitimate.update(image['url_hash'] for row in articles.values() for image in row['images'])
        blocked_images = {r['image_url_sha256'] for r in m['observations']} - legitimate
        blocked_strings = blocked_images | {m['old_article_url_sha256'], m['target_article_sha256']}
        urls = re.compile(r'https?://[^\s"\'<>\\]+')
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for x in value: yield from strings(x)
            elif isinstance(value, dict):
                for x in value.values(): yield from strings(x)
        files = 0
        for p in Path(output).rglob('*'):
            if not p.is_file() or p.suffix not in {'.html', '.json', '.js', '.css'}:
                continue
            files += 1
            text = p.read_text(encoding='utf-8')
            if any(oid in text for oid in self.targets):
                self.inspection_failure = {'file': p.relative_to(output).as_posix(), 'kind': 'retired_observation_id'}
                raise SyncError('RETIRED_CONTENT_IN_OUTPUT')
            candidates = list(urls.findall(html.unescape(text)))
            if p.suffix == '.json':
                try: candidates.extend(strings(json.loads(text)))
                except ValueError: raise SyncError('OUTPUT_JSON_INVALID') from None
            matched = next((digest(value) for value in candidates if digest(value) in blocked_strings), None)
            if matched:
                self.inspection_failure = {'file': p.relative_to(output).as_posix(), 'kind': 'retired_url_or_article', 'value_sha256': matched}
                raise SyncError('RETIRED_CONTENT_IN_OUTPUT')
        return {'result': 'PASS', 'text_files_checked': files,
                'retired_ids_absent': len(self.targets),
                'shared_image_urls_preserved': len({r['image_url_sha256'] for r in m['observations']} & legitimate)}
