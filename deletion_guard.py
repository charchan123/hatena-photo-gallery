"""Opt-in adapter: narrowly remove proven targets, then run original sync gates."""
from copy import deepcopy
from datetime import datetime, timezone
import html
from pathlib import Path
import re

from article_sync import SyncError, payload_hash, read_json, digest
from sync_deletions import (plan, event_for, append_event, select, validate_history,
                            without_targets, occurrences, instant, photo_keys)
from deletion_history import GitHistory
from deletion_protection import collect, open_selections
from deletion_approvals import load as load_approvals, archive_context, latest


def validate_ledger(records, portal, articles=None):
    try:
        assert isinstance(records,list)
        ids={r['observation_id'] for r in portal['observations']};seen=set()
        for r in records:
            assert set(r)=={'candidate_id','observation_id','article_hash','url_hash','ordinal','kind','mode',
                'article_url_hash','baseline','baseline_commit','detected_at','applied_at','fingerprint','approval_id','history_head','sha256','automatic_addition_receipt'}
            assert r['sha256']==payload_hash({k:v for k,v in r.items() if k!='sha256'})
            assert r['candidate_id'] not in seen;seen.add(r['candidate_id'])
            for k in ('candidate_id','article_hash','article_url_hash','url_hash','baseline','fingerprint','history_head'):
                assert re.fullmatch('[0-9a-f]{64}',r[k])
            assert re.fullmatch('[0-9a-f]{40}',r['baseline_commit'])
            assert type(r['ordinal']) is int and r['ordinal']==0
            assert r['candidate_id']==payload_hash({'baseline':r['baseline'],'key':[r['article_hash'],r['url_hash'],r['ordinal']]})
            assert r['kind'] in {'article_deleted','photo_deleted'} and r['mode'] in {'automatic','manual'}
            assert r['observation_id'] is None or (r['observation_id'] not in ids and re.fullmatch('obs-[A-Za-z0-9_-]{1,100}',r['observation_id']))
            assert r['approval_id'] is None if r['mode']=='automatic' else re.fullmatch('[0-9a-f]{64}',r['approval_id'])
            assert instant(r['applied_at'])>=instant(r['detected_at'])
            prior=r['automatic_addition_receipt']
            if prior:
                assert prior['observation_id']==r['observation_id'] and prior['article_hash']==r['article_hash'] and prior['url_hash']==r['url_hash'] and prior['ordinal']==r['ordinal']
                assert instant(prior['added_at'])<=instant(r['applied_at'])
            if articles is not None:
                # Any reappearance, including an article with different images,
                # or the same photo URL in a different article, needs review.
                assert not any(im['url_hash']==r['url_hash'] for a in articles.values() for im in a['images'])
                if r['kind']=='article_deleted':
                    assert r['article_hash'] not in articles
                    assert all(a.get('article_url_hash')!=r['article_url_hash'] for a in articles.values())
    except (AssertionError,KeyError,TypeError,ValueError):raise SyncError('DELETION_RECEIPT_INVALID_OR_REAPPEARED') from None
    return records


class DeletionGuard:
    def __init__(self, previous, snapshot, baseline_commit, root, run_id, *, store=None, pending=None, preview=False):
        self.preview=preview
        self.previous=previous;self.snapshot=snapshot;self.baseline_commit=baseline_commit
        self.root=Path(root);self.run_id=run_id;self.store=store or GitHistory(root)
        if not re.fullmatch('[0-9a-f]{40}',baseline_commit):raise SyncError('DELETION_BASELINE_COMMIT_INVALID')
        self.history=self.store.load(snapshot['payload'].get('deletion_history_head'))
        self.ledger=deepcopy(snapshot['payload'].get('deletions',[]));validate_ledger(self.ledger,previous,snapshot['payload']['articles'])
        anchors={row['sha256']:i for i,row in enumerate(self.history)}
        for receipt in self.ledger:
            index=anchors.get(receipt['history_head'])
            if index is None:raise SyncError('DELETION_RECEIPT_HISTORY_MISMATCH')
            if not any(item['event']['kind']=='fetch' and item['event']['healthy'] and
                item['event']['baseline']==receipt['baseline'] and
                item['event']['baseline_commit']==receipt['baseline_commit'] and
                item['event']['candidates'].get(receipt['candidate_id'])==receipt['fingerprint']
                for item in self.history[:index+1]):raise SyncError('DELETION_RECEIPT_HISTORY_MISMATCH')
        self.manifests=load_approvals(root);self.pending=pending;self.recorded=False;self.targets=[];self.rows=[];self.results=set()
        carried={r['approval_id'] for r in self.ledger if r['approval_id']}
        self.active=[m for m in latest(self.manifests) if m['approval_id'] not in carried and m['baseline']==snapshot['sha256']]
        for m in self.manifests:
            for receipt in self.ledger:
                if receipt['approval_id']==m['approval_id'] and (
                    any(receipt[k]!=m[k] for k in ('candidate_id','fingerprint','baseline')) or
                    m['action'] not in {'approve','archive_research','retire_research','approve_research_photo'} or
                    instant(m['approved_at'])>instant(receipt['applied_at'])):raise SyncError('DELETION_APPROVAL_RECEIPT_CHANGED')
        if carried-{m['approval_id'] for m in self.manifests}:raise SyncError('DELETION_APPROVAL_HISTORY_MISSING')

    def prepare(self, articles, audit, excluded):
        validate_ledger(self.ledger,self.previous,articles)
        registry=read_json(self.root/'data/research-identifications.json')
        master=read_json(self.root/'data/mushroom-master.json')
        # Validate archive capsules before using their original registry to bind
        # references. No removal is accepted just because a config was edited.
        if any(m['baseline'] != self.snapshot['sha256'] for m in self.active):raise SyncError('DELETION_APPROVAL_STALE')
        present=occurrences(articles)
        provisional=[{'observation_id':r['observation_id']} for key,r in photo_keys(self.previous).items() if key not in present]
        registry_before=archive_context(self.active,self.previous,registry,master,provisional)
        self.registry_before=registry_before
        self.checked_pending=open_selections() if self.pending is None else self.pending
        self.protection=collect(self.previous,self.snapshot,self.root,self.checked_pending,registry_before=registry_before)
        self.rows=plan(self.snapshot,self.previous,articles,audit,excluded,self.protection)
        at=datetime.now(timezone.utc).isoformat()
        event=event_for(self.rows,self.snapshot,self.baseline_commit,self.protection,articles,self.run_id,at)
        if not self.preview:
            self.history=append_event(self.history,event)
            self.store.save(self.history);self.recorded=True
        # Only persisted evidence is used below. A store failure throws above.
        self.targets=select(self.rows,self.snapshot,self.history,self.protection,at,self.active)
        if len(self.targets)!=len(self.rows):raise SyncError('DELETION_CONFIRMATION_OR_APPROVAL_PENDING')
        if registry_before is not None:archive_context(self.active,self.previous,registry,master,self.targets)
        return without_targets(self.previous,self.targets) if self.targets else self.previous

    def failure(self, code):
        if self.preview:return
        if not self.recorded:
            at=datetime.now(timezone.utc).isoformat()
            ev=event_for([],self.snapshot,self.baseline_commit,{}, {},self.run_id,at,healthy=False,error=code)
            self.history=append_event(self.history,ev);self.store.save(self.history);self.recorded=True
        self.outcome('BLOCKED',error=code)

    def outcome(self, result, *, error=None, portal=None, articles=None):
        if self.preview or result in self.results:return
        at=datetime.now(timezone.utc).isoformat()
        ev=event_for(self.rows,self.snapshot,self.baseline_commit,getattr(self,'protection',{}),
            articles or {},self.run_id+':'+result,at,healthy=error is None,error=error)
        ev.update(kind='result',outcome=result,receipt_sha256=payload_hash(self.ledger),
            output_portal_sha256=payload_hash(portal) if portal else None)
        self.history=append_event(self.history,ev);self.store.save(self.history);self.results.add(result)

    def summary(self):
        from collections import Counter
        counts=Counter(r['status'] for r in self.rows)
        allowed={t['candidate_id'] for t in self.targets}
        return {'candidate_count':len(self.rows),'automatic_deletion_eligible':sum(t['mode']=='automatic' for t in self.targets),
            'manual_deletion_eligible':sum(t['mode']=='manual' for t in self.targets),
            'protected_pending':sum(bool(r['protection']) and r['candidate_id'] not in allowed for r in self.rows),
            'applied_automatic':sum(t['mode']=='automatic' for t in self.ledger if t['baseline']==self.snapshot['sha256']),
            'applied_manual':sum(t['mode']=='manual' for t in self.ledger if t['baseline']==self.snapshot['sha256']),
            'pending':len(self.rows)-len(self.targets),'states':dict(counts),
            'history_persisted':self.recorded,'history_head':validate_history(self.history)}

    def finish(self, portal, articles, output, now):
        # Recheck important references after generation, not only at capture.
        fresh_pending=open_selections() if self.pending is None else self.pending
        fresh=collect(self.previous,self.snapshot,self.root,fresh_pending,registry_before=self.registry_before)
        if fresh['sha256']!=self.protection['sha256']:raise SyncError('DELETION_REFERENCES_CHANGED_DURING_BUILD')
        from best_shot_ui import validate_best_shot_config
        for pr in fresh_pending:validate_best_shot_config(pr['config'],portal)
        # Public output contains no archived research records or broken retired
        # image references. Receipts themselves live only in snapshot metadata.
        removed_ids={r['observation_id'] for r in self.ledger+self.targets if r['observation_id']}
        removed_urls={r['url_hash'] for r in self.ledger+self.targets}
        removed_urls.update(r['article_url_hash'] for r in self.ledger if r['kind']=='article_deleted')
        locations={digest(r['article']['article_id']):digest(r['article']['url'])
            for r in self.previous['observations'] if r['article'].get('url')}
        locations.update({aid:a['article_url_hash'] for aid,a in self.snapshot['payload']['articles'].items() if a.get('article_url_hash')})
        removed_urls.update(locations[r['article_hash']] for r in self.targets if r['kind']=='article_deleted')
        urls=re.compile(r'https?://[^\s"\'<>\\]+')
        for path in Path(output).rglob('*'):
            if not path.is_file() or path.suffix not in {'.html','.json','.js','.css'}:continue
            if path.name in {'article-sync-snapshot.json','article-sync-status.json'}:continue
            text=html.unescape(path.read_text(encoding='utf-8')).replace('\\/','/')
            if any(oid in text for oid in removed_ids) or any(digest(u) in removed_urls for u in urls.findall(text)):
                raise SyncError('DELETION_RETIRED_REFERENCE_IN_OUTPUT')
        approvals={m['candidate_id']:m for m in self.active}
        additions={r['observation_id']:r for r in self.snapshot['payload'].get('automatic_additions',[])}
        for target in self.targets:
            first=next(e['event']['at'] for e in self.history if e['event']['candidates'].get(target['candidate_id'])==target['fingerprint'])
            m=approvals.get(target['candidate_id'])
            row={k:target[k] for k in ('candidate_id','observation_id','article_hash','url_hash','ordinal','kind','mode','fingerprint')}
            row.update(article_url_hash=locations[target['article_hash']],baseline=self.snapshot['sha256'],baseline_commit=self.baseline_commit,detected_at=first,
                applied_at=now,approval_id=m['approval_id'] if target['mode']=='manual' else None,
                history_head=validate_history(self.history),automatic_addition_receipt=additions.get(target['observation_id']))
            row['sha256']=payload_hash(row);self.ledger.append(row)
        validate_ledger(self.ledger,portal,articles)
        return self.ledger
