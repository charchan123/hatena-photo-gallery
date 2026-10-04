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
