"""Safe git worktree and pull-request workflow (never merge or deploy)."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from .core import ROOT, safe_branch_name


class GitWorkflowError(RuntimeError):
    pass


def run(args, *, cwd=ROOT, check=True):
    """Run only an argument vector; callers cannot provide a shell string."""
    if not isinstance(args, (list, tuple)) or not args or not all(isinstance(v, str) for v in args):
        raise GitWorkflowError("subprocess command must be a non-empty string list")
    try:
        return subprocess.run(list(args), cwd=cwd, check=check, text=True,
                              capture_output=True, shell=False)
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise GitWorkflowError(detail.strip()) from error


def repository_status():
    branch = run(["git", "branch", "--show-current"]).stdout.strip()
    dirty = bool(run(["git", "status", "--porcelain"]).stdout.strip())
    auth = shutil.which("gh") is not None and run(["gh", "auth", "status"], check=False).returncode == 0
    def revision(ref):
        result = run(["git", "rev-parse", "--verify", ref], check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    status = {"branch": branch, "dirty": dirty, "gh_authenticated": auth,
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


def create_pull_request(files, validation, operation="changes"):
    """Apply reviewed JSON in an isolated origin/main worktree and open a PR."""
    if not repository_status()["gh_authenticated"]:
        raise GitWorkflowError("GitHub認証が必要です（gh auth login）")
    run(["git", "fetch", "origin", "main"])
    branch = safe_branch_name(operation)
    directory = Path(tempfile.mkdtemp(prefix="kinoko-admin-"))
    added = False
    try:
        run(["git", "worktree", "add", "-b", branch, str(directory), "origin/main"])
        added = True
        for relative, value in files.items():
            if relative not in {"data/best-shots.json", "data/update-notices.json",
                                "data/research-identifications.json"}:
                raise GitWorkflowError("unexpected change path")
            destination = (directory / relative).resolve()
            if directory.resolve() not in destination.parents:
                raise GitWorkflowError("change path escaped worktree")
            destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run(["python", "-m", "pytest", "-q"], cwd=directory)
        run(["python", "-m", "compileall", "-q", "."], cwd=directory)
        run(["git", "add", "--", *files.keys()], cwd=directory)
        if not run(["git", "diff", "--cached", "--quiet"], cwd=directory, check=False).returncode:
            raise GitWorkflowError("変更がありません")
        run(["git", "commit", "-m", f"Apply admin {operation} changes"], cwd=directory)
        run(["git", "push", "-u", "origin", branch], cwd=directory)
        changed = "\n".join(f"- `{name}`" for name in files)
        body = ("## 管理画面操作\n" + operation + "\n\n## 変更ファイル\n" + changed +
                "\n\n## 検証\n- validators: " + json.dumps(validation, ensure_ascii=False) +
                "\n- pytest: pass\n- compileall: pass\n\nDeploy was not performed. Auto-merge is OFF.")
        result = run(["gh", "pr", "create", "--base", "main", "--head", branch,
                      "--title", "Update mushroom blog from admin console", "--body", body], cwd=directory)
        return {"branch": branch, "url": result.stdout.strip()}
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
        raise GitWorkflowError("GitHub認証が必要です（gh auth login）")
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
