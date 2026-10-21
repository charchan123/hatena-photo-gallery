"""Local-only, atomic recovery of owner-reviewed admin ChangeSet data.

Only the three allowlisted admin JSON data documents are persisted.
Never write production data or Git history here, and never silently rebase a draft.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .core import ROOT


FILES = ("data/best-shots.json", "data/update-notices.json",
         "data/research-identifications.json")
SCHEMA = 1
MAX_BYTES = 1_000_000


class DraftRecoveryError(RuntimeError):
    """Preserve the local file and stop instead of losing a saved draft."""


def _fingerprint(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DraftStore:
    """Persist valid draft snapshots outside Git; stop on incompatible recovery."""

    def __init__(self, root=ROOT):
        self.path = Path(root) / "admin" / "local-state" / "admin-draft.json"
        self.baseline = None
        self.base_hashes = None
        self.restored = False
        self.saved = False

    def _check_path(self):
        if self.path.is_symlink():
            raise DraftRecoveryError("下書き保存先がシンボリックリンクです。安全のため停止しました")

    def recover(self, draft):
        self._check_path()
        self.baseline = deepcopy(draft.files())
        if set(self.baseline) != set(FILES):
            raise DraftRecoveryError("下書きの対象ファイルが想定と異なります")
        self.base_hashes = {name: _fingerprint(value)
                            for name, value in self.baseline.items()}
        self.restored = False
        self.saved = False
        if not self.path.exists():
            return draft
        try:
            if self.path.stat().st_size > MAX_BYTES:
                raise ValueError("draft too large")
            snapshot = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(snapshot, dict) or snapshot.get("version") != SCHEMA
                    or set(snapshot.get("files", {})) != set(FILES)
                    or set(snapshot.get("base", {})) != set(FILES)):
                raise ValueError("invalid draft schema")
            data = snapshot["files"]
            if not all(isinstance(data[name], dict) for name in FILES):
                raise ValueError("invalid draft content")
            # When a PR has already been merged and local data is synced,
            # the old draft is no longer pending.
            if data == self.baseline:
                self.path.unlink()
                return draft
            if snapshot["base"] != self.base_hashes:
                raise DraftRecoveryError(
                    "保存済み下書きと現在のmainの元データが異なります。"
                    "admin/local-state/admin-draft.jsonを削除せず、"
                    "バックアップを取ってから差分を確認してください")
            proposed = deepcopy(data)
            original = deepcopy(draft.files())
            try:
                draft.best_shots = proposed[FILES[0]]
                draft.notices = proposed[FILES[1]]
                draft.identifications = proposed[FILES[2]]
                draft.validate()
            except Exception:
                draft.best_shots = original[FILES[0]]
                draft.notices = original[FILES[1]]
                draft.identifications = original[FILES[2]]
                raise
        except DraftRecoveryError:
            raise
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise DraftRecoveryError(
                "保存済み下書きを安全に復元できません。"
                "admin/local-state/admin-draft.jsonを保持して起動を停止しました") from exc
        self.restored = True
        self.saved = True
        return draft

    def verify_saved(self, draft):
        """Read-only PR gate: never refresh, overwrite, or discard a local draft."""
        self._check_path()
        try:
            if not self.saved or self.path.stat().st_size > MAX_BYTES:
                raise ValueError("no durable draft")
            snapshot = json.loads(self.path.read_text(encoding="utf-8"))
            files = draft.files()
            if (snapshot.get("version") != SCHEMA
                    or snapshot.get("base") != self.base_hashes
                    or set(snapshot.get("files", {})) != set(FILES)
                    or any(_fingerprint(snapshot["files"][name]) != _fingerprint(files[name])
                           for name in FILES)):
                raise ValueError("saved draft differs from reviewed changes")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise DraftRecoveryError(
                "保存済み下書きと変更予定を安全に照合できません。ファイルは上書き・削除していません。"
                "バックアップを取り、保存先の権限と変更内容を確認してください") from error

    def save(self, draft):
        """Atomic replace; retain the old snapshot on a failed write."""
        if self.baseline is None:
            raise DraftRecoveryError("下書き保存の初期化が必要です")
        self._check_path()
        files = deepcopy(draft.files())
        if set(files) != set(FILES):
            raise DraftRecoveryError("下書きの対象ファイルが想定と異なります")
        if files == self.baseline:
            # The user deliberately reverted all changes to the local baseline.
            if self.path.exists():
                self.path.unlink()
            self.saved = False
            return
        snapshot = {"version": SCHEMA, "base": self.base_hashes,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "files": files}
        content = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
        if len(content.encode("utf-8")) > MAX_BYTES:
            raise DraftRecoveryError("下書きが保存サイズの上限を超えています")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.path.parent,
                                             prefix=".admin-draft-",
                                             suffix=".tmp", delete=False) as fh:
                temporary = Path(fh.name)
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            if os.name != "nt":
                temporary.chmod(0o600)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.saved = True
