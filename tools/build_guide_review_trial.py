"""Package the review-only localhost trial without local data or credentials."""
import argparse
import hashlib
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = r"""@echo off
cd /d "%~dp0"
py.exe -3 tools\guide_review_trial.py
if errorlevel 1 pause
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "admin", "*.py", "requirements.txt",
         "docs/guide-review-admin.md", "comments/cases.json", "data/research-identifications.json"], cwd=ROOT,
    ).decode("utf-8").strip("\0").split("\0")
    with ZipFile(args.output, "w", ZIP_DEFLATED) as archive:
        for name in paths:
            if (name.startswith("admin/") and not name.startswith("admin/local-state/")
                    or name in {"requirements.txt", "docs/guide-review-admin.md", "tools/guide_review_trial.py",
                                "comments/cases.json", "data/research-identifications.json"}
                    or ("/" not in name and name.endswith(".py"))):
                archive.write(ROOT / name, name)
        archive.writestr("Start-Guide-Review.cmd", LAUNCHER.replace("\n", "\r\n"))
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(".sha256").write_text(f"{digest}  {args.output.name}\n", encoding="ascii")


if __name__ == "__main__":
    main()
