"""Replay pinned gh-pages HTML with the candidate's guide panel only."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from detail_ui import build_detail_views, render_detail_sections

PUBLISHED = sys.argv[2] if len(sys.argv) > 2 else "345927a33c429d6846c3a08e00092ca7cbef883e"
OUTPUT = Path(sys.argv[1]).resolve()
PANEL = re.compile(r'<section class="knowledge-panel">.*?</section>', re.DOTALL)

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)

def read_published(name):
    return git("show", f"{PUBLISHED}:{name}")

def write(relative, content):
    destination = OUTPUT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

portal = json.loads(read_published("portal-data.json"))
views = build_detail_views(portal)
pages = {}
for row in portal["subjects"]:
    if not row["knowledge_available"]:
        continue
    subject = row["gallery_name"]
    filename = re.sub(r'[:<>"|*?\\/\r\n]', "_", subject).strip() + ".html"
    pages[row["mushroom_master_id"]] = filename
    original = read_published(filename)
    html = original.decode()
    view = {**views[subject], "articles": []}
    markup = render_detail_sections(view)
    result, count = PANEL.subn(lambda _: markup, html)
    assert count == 1, filename
    assert PANEL.sub("", result) == PANEL.sub("", html), filename
    write("base/" + filename, original)
    write("draft/" + filename, result.encode())
assert len(pages) == 85
for path in git("ls-tree", "-rz", "--name-only", PUBLISHED).decode().split("\0"):
    if path.startswith(("assets/", "lightgallery/")) and Path(path).suffix in (".js", ".css", ".woff", ".woff2", ".ttf", ".svg", ".json"):
        content = read_published(path)
        write("base/" + path, content)
        write("draft/" + path, content)
write("published-85.json", json.dumps(pages, ensure_ascii=False).encode())
(OUTPUT / "screens").mkdir(exist_ok=True)
