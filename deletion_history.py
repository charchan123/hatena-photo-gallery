"""Durable append-only fetch evidence in a dedicated Git branch.

Uses ordinary non-force Git push. A race or persistence failure blocks publishing.
Only hash-only evidence goes to this branch; raw API bodies/credentials never do.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from article_sync import SyncError
from sync_deletions import validate_history, ROOT_HASH

BRANCH = 'sync-deletion-audit'


def git(*args, cwd=None, data=None, check=True):
    p = subprocess.run(['git', *args], cwd=cwd, input=data, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode: raise SyncError('DELETION_HISTORY_STORAGE_UNAVAILABLE')
    return p


class GitHistory:
    def __init__(self, root):
        self.root = Path(root); self.commit = None; self.rows = []

    def load(self, anchor=None):
        lookup = git('ls-remote', '--exit-code', '--heads', 'origin', BRANCH, cwd=self.root, check=False)
        if lookup.returncode == 2:
            if anchor and anchor != ROOT_HASH: raise SyncError('DELETION_HISTORY_MISSING')
            self.rows = []; self.commit = None; return self.rows
        if lookup.returncode: raise SyncError('DELETION_HISTORY_STORAGE_UNAVAILABLE')
        sha = lookup.stdout.split()[0]
        git('fetch', '--no-tags', 'origin', sha, cwd=self.root)
        def read(path):
            try:return json.loads(git('show',sha+':'+path,cwd=self.root).stdout)
            except (ValueError,TypeError):raise SyncError('DELETION_HISTORY_CORRUPT') from None
        index=read('head.json')
        paths=git('ls-tree','-r','--name-only',sha,cwd=self.root).stdout.splitlines()
        event_paths=sorted(p for p in paths if p.startswith('events/'))
        if set(paths)!=set(event_paths)|{'head.json'}:raise SyncError('DELETION_HISTORY_STORAGE_UNSAFE')
        self.rows=[read(path) for path in event_paths]
        head=validate_history(self.rows,anchor)
        if index!={'version':1,'head':head,'count':len(self.rows)}:raise SyncError('DELETION_HISTORY_CORRUPT')
        self.commit=sha
        commits=git('rev-list','--reverse','--first-parent',sha,cwd=self.root).stdout.splitlines()
        if len(commits)!=len(self.rows):raise SyncError('DELETION_HISTORY_REWRITTEN')
        for i,(commit,row,path) in enumerate(zip(commits,self.rows,event_paths)):
            expected=f"events/{i+1:08d}-{row['sha256']}.json"
            if path!=expected:raise SyncError('DELETION_HISTORY_CORRUPT')
            changes=git('diff-tree','--root','--no-commit-id','--name-status','-r',commit,cwd=self.root).stdout.splitlines()
            if set(changes)!={('A' if i==0 else 'M')+'\thead.json','A\t'+path}:
                raise SyncError('DELETION_HISTORY_REWRITTEN')
        return self.rows

    def save(self, rows):
        validate_history(rows)
        if rows == self.rows: return self.commit
        if rows[:-1] != self.rows: raise SyncError('DELETION_HISTORY_APPEND_ONLY')
        env = os.environ.copy()
        env.update(GIT_AUTHOR_NAME='kinoko sync audit', GIT_AUTHOR_EMAIL='audit@users.noreply.github.com',
                   GIT_COMMITTER_NAME='kinoko sync audit', GIT_COMMITTER_EMAIL='audit@users.noreply.github.com')
        def plumbing(*args, data=None):
            p = subprocess.run(['git', *args], cwd=self.root, env=env, input=data,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode: raise SyncError('DELETION_HISTORY_STORAGE_UNAVAILABLE')
            return p.stdout.strip()
        # One immutable event blob per run: avoid quadratic full-history files.
        # A private index leaves the caller's working tree and index untouched.
        with tempfile.TemporaryDirectory(prefix='kinoko-history-index-') as temporary:
            env['GIT_INDEX_FILE']=str(Path(temporary)/'index')
            plumbing('read-tree',self.commit) if self.commit else plumbing('read-tree','--empty')
            head={'version':1,'head':validate_history(rows),'count':len(rows)}
            row=rows[-1]
            for path,value in [('head.json',head),(f"events/{len(rows):08d}-{row['sha256']}.json",row)]:
                blob=plumbing('hash-object','-w','--stdin',data=json.dumps(value,ensure_ascii=False,indent=2)+'\n')
                plumbing('update-index','--add','--cacheinfo','100644',blob,path)
            tree=plumbing('write-tree')
        env.pop('GIT_INDEX_FILE',None)
        args = ['commit-tree', tree]
        if self.commit: args += ['-p', self.commit]
        commit = plumbing(*args, data='Persist independent deletion observation\n')
        # No force, deletion, main, gh-pages, or publication ref is ever used.
        git('push', 'origin', commit + ':refs/heads/' + BRANCH, cwd=self.root)
        if git('ls-remote', '--heads', 'origin', BRANCH, cwd=self.root).stdout.split()[0] != commit:
            raise SyncError('DELETION_HISTORY_PERSISTENCE_NOT_CONFIRMED')
        self.commit = commit; self.rows = rows
        return commit
