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
        self.rows = json.loads(git('show', sha + ':history.json', cwd=self.root).stdout)
        validate_history(self.rows, anchor); self.commit = sha
        # Every earlier event in the Git branch must be a prefix. A rewritten
        # index cannot silently discard confirmations even before first publish.
        parents = git('rev-list', '--first-parent', sha, cwd=self.root).stdout.splitlines()
        previous = self.rows
        for parent in parents[1:]:
            old = json.loads(git('show', parent + ':history.json', cwd=self.root).stdout)
            validate_history(old)
            if previous[:len(old)] != old or len(previous) != len(old) + 1:
                raise SyncError('DELETION_HISTORY_REWRITTEN')
            previous = old
        if previous and len(previous) != 1: raise SyncError('DELETION_HISTORY_ROOT_INVALID')
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
        blob = plumbing('hash-object', '-w', '--stdin', data=json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        tree = plumbing('mktree', data='100644 blob ' + blob + '\thistory.json\n')
        args = ['commit-tree', tree]
        if self.commit: args += ['-p', self.commit]
        commit = plumbing(*args, data='Persist independent deletion observation\n')
        # No force, deletion, main, gh-pages, or publication ref is ever used.
        git('push', 'origin', commit + ':refs/heads/' + BRANCH, cwd=self.root)
        if git('ls-remote', '--heads', 'origin', BRANCH, cwd=self.root).stdout.split()[0] != commit:
            raise SyncError('DELETION_HISTORY_PERSISTENCE_NOT_CONFIRMED')
        self.commit = commit; self.rows = rows
        return commit
