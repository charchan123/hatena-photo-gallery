"""Safe git worktree and pull-request workflow (never merge or deploy)."""

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .core import ROOT, safe_branch_name


class GitWorkflowError(RuntimeError):
    pass


def locate_gh():
    """Resolve GitHub CLI even if admin started before Windows PATH updated."""
    discovered = shutil.which("gh")
    if discovered:
        return discovered
    for variable, parts in (
        ("ProgramFiles", ("GitHub CLI", "gh.exe")),
        ("ProgramW6432", ("GitHub CLI", "gh.exe")),
        ("ProgramFiles(x86)", ("GitHub CLI", "gh.exe")),
        ("LOCALAPPDATA", ("Programs", "GitHub CLI", "gh.exe")),
    ):
        folder = os.environ.get(variable)
        if folder:
            candidate = Path(folder).joinpath(*parts)
            if candidate.is_file():
                return str(candidate)
    return None


def run(args, *, cwd=ROOT, check=True):
    """Run only an argument vector; callers cannot provide a shell string."""
    if not isinstance(args, (list, tuple)) or not args or not all(isinstance(v, str) for v in args):
        raise GitWorkflowError("subprocess command must be a non-empty string list")
    command = list(args)
    if command[0] == "gh":
        command[0] = locate_gh()
        if command[0] is None:
            raise GitWorkflowError("GitHub CLIが見つかりません。インストールを確認してください")
    try:
        return subprocess.run(command, cwd=cwd, check=check, text=True,
                              capture_output=True, shell=False, encoding="utf-8", errors="replace")
    except subprocess.CalledProcessError as error:
        # Show a bounded, actionable error rather than only the exit status.
        detail = (error.stderr or error.stdout or "").strip()
        if not detail:
            detail = f"{command[0]} が終了コード {error.returncode} で失敗しました"
        raise GitWorkflowError(detail[:1500]) from error
    except OSError as error:
        raise GitWorkflowError(f"外部コマンドを実行できません: {command[0]} ({error})") from error


def repository_status():
    branch = run(["git", "branch", "--show-current"]).stdout.strip()
    dirty = bool(run(["git", "status", "--porcelain"]).stdout.strip())
    gh_available = locate_gh() is not None
    auth = gh_available and run(["gh", "auth", "status"], check=False).returncode == 0
    def revision(ref):
        result = run(["git", "rev-parse", "--verify", ref], check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    status = {"branch": branch, "dirty": dirty, "gh_available": gh_available,
              "gh_authenticated": auth,
              "head_sha": revision("HEAD"), "origin_main_sha": revision("origin/main"),
              "gh_pages_sha": revision("origin/gh-pages"), "latest_action": None}
    if auth:
        result = run(["gh", "run", "list", "--workflow", "generate.yml", "--limit", "1",
                      "--json", "status,conclusion,url,headSha"], check=False)
        if result.returncode == 0:
            try:
                rows = json.loads(result.stdout)
                status["latest_action"] = rows[0] if rows else None
            except json.JSONDecodeError:
                pass
    return status


ADMIN_DATA_FILES = (
    "data/best-shots.json",
    "data/update-notices.json",
    "data/research-identifications.json",
)


def _json_identity(value):
    # Ignore platform line endings/formatting, but retain JSON types and list order.
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _read_admin_json(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    _json_identity(value)
    return value


def create_pull_request(files, validation, operation="changes", *, baseline=None):
    """Publish only a validated, durable snapshot as a Draft; full tests run in CI.

    No checkout/reset/rebase of the administrator's checkout or draft is allowed.
    Both the executing code and all original admin data must match fresh main.
    """
    files, baseline = deepcopy(files), deepcopy(baseline)
    if not repository_status()["gh_authenticated"]:
        raise GitWorkflowError("GitHub認証が必要です。GitHub CLIを確認し、gh auth loginで再認証してください。下書きは保持しています")
    for value in (files, baseline):
        if (not isinstance(value, dict) or set(value) != set(ADMIN_DATA_FILES)
                or not all(isinstance(value[p], dict) for p in ADMIN_DATA_FILES)):
            raise GitWorkflowError("変更データまたは元データの照合情報が不正です。下書きを保持し、管理室の起動元を確認してください")
    if (not isinstance(validation, dict)
            or set(validation) != {"best_shots", "notices", "identifications"}
            or any(type(n) is not int or n < 0 for n in validation.values())):
        raise GitWorkflowError("管理室の入力検証が完了していません。変更内容を確認して検証し直してください")
    try:
        identities = {p: _json_identity(baseline[p]) for p in ADMIN_DATA_FILES}
        proposed = {p: _json_identity(files[p]) for p in ADMIN_DATA_FILES}
    except (TypeError, ValueError) as error:
        raise GitWorkflowError("管理データをJSONとして安全に保存できません。入力内容を確認してください") from error

    directory = None
    added = False
    branch = None
    pushed = False
    phase = "最新mainの取得（ネットワークとGit認証を確認してください）"
    try:
        run(["git", "fetch", "origin", "main"])
        fresh = run(["git", "rev-parse", "--verify", "origin/main"]).stdout.strip()
        current = run(["git", "rev-parse", "--verify", "HEAD"]).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", fresh) or current != fresh:
            raise GitWorkflowError("実行中のコードが最新mainと一致しません。下書きをバックアップし、差分を手動照合してから管理室を更新・再起動してください。自動rebaseは行いません")
        phase = "最新mainの元データ照合"
        branch = safe_branch_name(operation)
        directory = Path(tempfile.mkdtemp(prefix="kinoko-admin-"))
        run(["git", "worktree", "add", "-b", branch, str(directory), fresh])
        added = True
        # Check every original before writing even one proposed document.
        for relative in ADMIN_DATA_FILES:
            destination = directory / relative
            if not destination.is_file() or destination.is_symlink():
                raise GitWorkflowError("最新mainの管理データを安全に取得できません。Gitの状態を確認してください")
            if _json_identity(_read_admin_json(destination)) != identities[relative]:
                raise GitWorkflowError(
                    f"最新mainで {relative} が変更されています。下書きを保持して停止しました。"
                    "バックアップを取り、GitHubの変更と手動照合してください"
                )
        changed = [p for p in ADMIN_DATA_FILES if identities[p] != proposed[p]]
        if not changed:
            raise GitWorkflowError("変更がありません。公開済みの内容と変更予定を確認してください")
        phase = "一時worktreeへの保存（空き容量と書き込み権限を確認してください）"
        for relative in changed:
            (directory / relative).write_text(
                json.dumps(files[relative], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8"
            )
        run(["git", "add", "--", *changed], cwd=directory)
        staged = sorted(run(["git", "diff", "--cached", "--name-only"], cwd=directory).stdout.splitlines())
        if staged != sorted(changed):
            raise GitWorkflowError("Gitのステージ対象が変更予定と一致しません。安全のため停止しました")
        run(["git", "diff", "--cached", "--check"], cwd=directory)
        phase = "コミット（gitのuser.name・user.email設定を確認してください）"
        run(["git", "commit", "-m", f"Apply admin {operation} changes"], cwd=directory)
        # Refuse a main advance during preparation, rather than silently rebase.
        phase = "push直前の最新main再照合（通信状態を確認してください）"
        remote = run(["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"]).stdout.split()
        if remote != [fresh, "refs/heads/main"]:
            raise GitWorkflowError("作成中にmainが更新されました。下書きを保持しました。最新mainとの差分を手動確認してから再実行してください")
        phase = "ブランチのpush（GitHub認証・ネットワーク・書き込み権限を確認してください）"
        run(["git", "push", "-u", "origin", branch], cwd=directory)
        pushed = True
        changed_text = "\n".join(f"- `{name}`" for name in changed)
        body = (
            "## 管理室で確認したデータ変更\n" + changed_text
            + "\n\n## ローカル安全確認\n"
            + f"- 照合したmain: `{fresh}`\n"
            + "- 実行コードと最新main、元データ全3ファイルが一致\n"
            + "- 許可リスト・ステージ済み差分を検査済み\n"
            + "- 管理室の入力検証済み: " + json.dumps(validation, ensure_ascii=False)
            + "\n\n## CI\n"
            + "- 全Python/JavaScriptテスト・保護参照・非公開の生成検証はGitHub Actionsで実施\n"
            + "- ローカルで全pytestを実行しない。CI失敗時はDraftのまま修正・再検証\n"
            + "- CI成功だけではマージしない。人間の差分確認と管理者の明示承認が必要\n"
            + "\nDraft PRのみ。自動merge・deploy・公開は行いません。"
        )
        # A UTF-8 file preserves real newlines and Japanese on Windows, and avoids
        # command-line length limits for descriptions. No shell interpolation.
        body_path = directory.parent / (directory.name + "-pr-body.md")
        phase = "Draft PR作成（GitHub CLIの認証・PR作成権限を確認してください）"
        try:
            body_path.write_text(body, encoding="utf-8")
            result = run([
                "gh", "pr", "create", "--draft", "--base", "main", "--head", branch,
                "--title", "Update mushroom blog from admin console", "--body-file", str(body_path)
            ], cwd=directory)
        finally:
            try:
                body_path.unlink(missing_ok=True)
            except OSError:
                pass
        url = result.stdout.strip()
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*", url):
            raise GitWorkflowError("Draft PRのURLを確認できません。GitHubでPRの作成状況を確認してください")
        return {"branch": branch, "url": url, "ci_status": "pending", "draft": True}
    except (GitWorkflowError, OSError, ValueError) as error:
        recovery = f" GitHubのブランチ {branch} と既存PRを確認してから再試行してください。" if pushed else ""
        raise GitWorkflowError(f"{phase}で停止しました: {error}。下書きは保持しています。{recovery}") from error
    finally:
        # Cleanup must never mask a successful PR URL or the original error.
        if added:
            try:
                run(["git", "worktree", "remove", "--force", str(directory)], check=False)
            except GitWorkflowError:
                pass
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)


def validate_knowledge_changed_paths(paths, batch_id):
    """Enforce the deliberately narrow knowledge-promotion PR allow-list."""
    from .knowledge import _safe_id
    _safe_id(batch_id)
    exact = {"audit/feature-overlays/index.json", "data/mushroom-master.json",
             "data/sources.json", "data/feature-facets.json"}
    prefix = f"audit/knowledge-batches/{batch_id}/"
    invalid = [path for path in paths if path not in exact and not path.startswith(prefix)]
    if invalid:
        raise GitWorkflowError("knowledge PR contains unexpected paths: " + ", ".join(invalid))
    return True


def collect_knowledge_changed_paths(directory):
    """Collect tracked and untracked promotion paths before allow-listing/staging."""
    tracked = run(["git", "diff", "--name-only"], cwd=directory).stdout.splitlines()
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"], cwd=directory).stdout.splitlines()
    return sorted(set(tracked) | set(untracked))


def create_knowledge_pull_request(batch_id):
    """Revalidate a reviewed batch on fresh origin/main and open a PR (never merge)."""
    from feature_overlay import reconstruct_feature_production_state, validate_feature_production_state
    from .knowledge import load_batch, materialize_promotion_package, _dump, _hash
    if not repository_status()["gh_authenticated"]:
        raise GitWorkflowError("GitHub認証が必要です（CLI未検出または認証切れ。初回のみ gh auth login）")
    if run(["git", "status", "--porcelain"]).stdout.strip():
        raise GitWorkflowError("管理画面の実行checkoutに未保存の変更があります")
    run(["git", "fetch", "origin", "main"])
    fresh = run(["git", "rev-parse", "origin/main"]).stdout.strip()
    current = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    if current != fresh:
        raise GitWorkflowError("管理画面の実行checkoutがfresh origin/mainと一致しません")
    batch = load_batch(batch_id)
    if fresh != batch["manifest"]["base_main_sha"]:
        raise GitWorkflowError("batch base_main_sha does not match fresh origin/main")
    branch = safe_branch_name("knowledge")
    directory = Path(tempfile.mkdtemp(prefix="kinoko-knowledge-")); added = False
    try:
        run(["git", "worktree", "add", "-b", branch, str(directory), "origin/main"]); added = True
        package = directory / "audit/knowledge-batches" / batch_id
        report = materialize_promotion_package(batch_id, package, base_sha=fresh,
                                               contract_root=directory)
        registry_path = directory / "audit/feature-overlays/index.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if any(row["overlay_id"] == batch_id for row in registry["overlays"]):
            raise GitWorkflowError("duplicate existing overlay ID")
        manifest = package / "promotion-manifest.json"
        registry["overlays"].append({"overlay_id":batch_id,
            "manifest_path":f"audit/knowledge-batches/{batch_id}/promotion-manifest.json",
            "manifest_sha256":_hash(manifest.read_bytes())})
        registry["overlays"].sort(key=lambda row: row["overlay_id"])
        registry_path.write_bytes(_dump(registry))
        expected = reconstruct_feature_production_state(root=directory, registry_path=registry_path)
        for name,key in (("mushroom-master.json","mushroom_master"),("sources.json","sources"),("feature-facets.json","feature_facets")):
            (directory/"data"/name).write_bytes(_dump(expected[key]))
        validate_feature_production_state(root=directory, registry_path=registry_path)
        run(["python", "-m", "pytest", "-q"], cwd=directory)
        run(["python", "-m", "compileall", "-q", "."], cwd=directory)
        # The generator regression suite intentionally emits ignored-from-promotion
        # public previews. Remove only those known untracked test products before
        # applying the strict changed-path allow-list.
        run(["git", "clean", "-fd", "--", "output"], cwd=directory)
        changed = collect_knowledge_changed_paths(directory)
        validate_knowledge_changed_paths(changed, batch_id)
        run(["git", "add", "--", *changed], cwd=directory)
        staged = sorted(run(["git", "diff", "--cached", "--name-only"], cwd=directory).stdout.splitlines())
        if staged != changed:
            raise GitWorkflowError("knowledge staged paths differ from validated paths")
        run(["git", "diff", "--cached", "--check"], cwd=directory)
        run(["git", "commit", "-m", f"Promote knowledge batch {batch_id}"], cwd=directory)
        run(["git", "push", "-u", "origin", branch], cwd=directory)
        body=(f"## Knowledge Expansion\n- batch ID: `{batch_id}`\n"
              f"- approved: {report['approved_count']}\n- held: {report['held_count']}\n"
              f"- promoted assignments: {report['promoted_assignment_count']}\n"
              f"- new mushrooms: {report['promoted_mushroom_count']}\n"
              f"- new sources: {report['promoted_source_count']}\n- snapshots: {report['promoted_snapshot_count']}\n\n"
              "## Validation\n- validator: PASS\n- pytest: PASS\n- compileall: PASS\n"
              "- merge/deploy: NOT performed\n")
        result=run(["gh","pr","create","--base","main","--head",branch,"--title",f"Promote knowledge batch {batch_id}","--body",body],cwd=directory)
        return {"branch":branch,"url":result.stdout.strip()}
    finally:
        if added: run(["git","worktree","remove","--force",str(directory)],check=False)
        shutil.rmtree(directory,ignore_errors=True)
