"""Safe git worktree and pull-request workflow (never merge or deploy)."""

import json
import os
from pathlib import Path
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
                              capture_output=True, shell=False)
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


def create_pull_request(files, validation, operation="changes", *, baseline=None):
    """Create a Draft PR from reviewed data; GitHub Actions performs all full tests.

    The server's original baseline must match *fresh origin/main* for all protected
    admin JSON. A stale or incompatible local draft is never silently rebased.
    """
    if not repository_status()["gh_authenticated"]:
        raise GitWorkflowError("GitHub認証が必要です（初回のみ gh auth login）")
    if not isinstance(files, dict) or set(files) != set(ADMIN_DATA_FILES):
        raise GitWorkflowError("管理室の変更対象ファイルが想定と異なります。安全のため停止しました")
    if not isinstance(baseline, dict) or set(baseline) != set(ADMIN_DATA_FILES):
        raise GitWorkflowError("元データの照合情報がありません。管理室を安全に再起動して確認してください")
    if not all(isinstance(files[p], dict) and isinstance(baseline[p], dict) for p in ADMIN_DATA_FILES):
        raise GitWorkflowError("変更データまたは元データが不正です")

    run(["git", "fetch", "origin", "main"])
    branch = safe_branch_name(operation)
    directory = Path(tempfile.mkdtemp(prefix="kinoko-admin-"))
    added = False
    try:
        run(["git", "worktree", "add", "-b", branch, str(directory), "origin/main"])
        added = True
        changed = []
        for relative in ADMIN_DATA_FILES:
            destination = directory / relative
            if not destination.is_file() or destination.is_symlink():
                raise GitWorkflowError("最新mainの管理データを安全に取得できませんでした")
            try:
                current = json.loads(destination.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise GitWorkflowError("最新mainの管理データを検証できません") from error
            if current != baseline[relative]:
                raise GitWorkflowError(
                    f"最新mainで {relative} が変更されています。"
                    "下書きを保持して停止しました。GitHubの公開済み変更と手動照合してください"
                )
            if current != files[relative]:
                changed.append(relative)
                destination.write_text(
                    json.dumps(files[relative], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8"
                )
        if not changed:
            raise GitWorkflowError("変更がありません。公開済みの内容を再度確認してください")

        # Stage only the three reviewed JSON files; disallow unexpected staged paths.
        run(["git", "add", "--", *changed], cwd=directory)
        staged = sorted(run(["git", "diff", "--cached", "--name-only"], cwd=directory).stdout.splitlines())
        if staged != sorted(changed):
            raise GitWorkflowError("Gitのステージ対象が変更予定と一致しません。安全のため停止しました")
        run(["git", "diff", "--cached", "--check"], cwd=directory)
        run(["git", "commit", "-m", f"Apply admin {operation} changes"], cwd=directory)
        run(["git", "push", "-u", "origin", branch], cwd=directory)
        changed_text = "\n".join(f"- \`{name}\`" for name in changed)
        body = (
            "## 管理室で確認したデータ変更\n" + changed_text
            + "\n\n## ローカル安全確認\n"
            + "- 最新origin/mainと管理室の元データが全3ファイル一致\n"
            + "- 変更ファイルの許可リスト・ステージ済み差分を検査済み\n"
            + "- 管理室の入力検証済み: " + json.dumps(validation, ensure_ascii=False)
            + "\n\n## CI\n"
            + "- 全Python/JavaScriptテスト、最新はてなデータの保護検証はGitHub Actionsで実施\n"
            + "- CI成功・人間による差分確認の前にはマージしない\n"
            + "- ローカルで全pytestを実行しない（Windows依存エラー回避）\n"
            + "\nDraft PRのみ。自動merge・deploy・公開は行いません。"
        )
        result = run([
            "gh", "pr", "create", "--draft", "--base", "main", "--head", branch,
            "--title", "Update mushroom blog from admin console", "--body", body
        ], cwd=directory)
        url = result.stdout.strip()
        if not url.startswith("https://github.com/"):
            raise GitWorkflowError("Draft PRのURLを確認できません。GitHubのブランチを確認してください")
        return {"branch": branch, "url": url, "ci_status": "pending"}
    finally:
        if added:
            run(["git", "worktree", "remove", "--force", str(directory)], check=False)
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
