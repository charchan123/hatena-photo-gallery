"""Build the LAN preview from pinned Git objects. No remote or production writes."""
import base64
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from best_shot_ui import _best_shots_hero, _card, _document

CANDIDATE = "02135b9adb5aaac03ee9006b55f724fa86356d17"
BASELINE = "ae08f456729e7d89619af9569b7daecdd85080cd"
FOOTER = "hatena/release-2026-10-24/footer-managed.html"
FOOTER_SHA = "60c08e60007b8f31a5dac61510a1a6d7bbeae51251c98aa519b5b71c93c2d3d3"
PATCH = "hatena/patches/lightgallery-overlay-scroll-lock-20261108.html"
MANUAL = "audit/lightgallery-toolbar-scrollbar-20261108/REAL_DEVICE_PREVIEW.md"
ASSETS = (
    "assets/gallery.css", "assets/gallery.js", "assets/best-shots.css",
    "assets/ai-best-shots-20261031.webp", "lightgallery/lightgallery-bundle.min.css",
    "lightgallery/lightgallery.min.js", "lightgallery/lg-zoom.min.js",
    "lightgallery/lg-thumbnail.min.js", "lightgallery/lg-autoplay.min.js",
    "lightgallery/lg-share.min.js", "lightgallery/fonts/lg.woff2",
    "lightgallery/fonts/lg.woff", "lightgallery/fonts/lg.ttf",
    "lightgallery/fonts/lg.svg",
)
HOST_STYLE = """
*{box-sizing:border-box}
html{overflow-y:scroll}
body{margin:0;background:#f6f4ed;color:#253529;font:16px/1.65 system-ui,sans-serif}
header{min-height:270px;max-width:72rem;margin:auto;padding:24px 20px}
h1{line-height:1.2;margin:.4em 0}
code,.sha{overflow-wrap:anywhere;font-family:monospace}
iframe{display:block;width:100%;border:0;min-height:0}
a{color:#245632}
html.body-case{overflow:hidden}
html.body-case body{height:100vh;height:100dvh;overflow-y:scroll}
::-webkit-scrollbar{width:15px}
::-webkit-scrollbar-thumb{background:#8b968a;border:3px solid #edeee9;border-radius:8px}
::-webkit-scrollbar-track{background:#edeee9}
"""

def git_file(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=REPO)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def sample_image(number):
    width, height = (900, 1350) if number % 2 else (1500, 900)
    hue = (number * 39) % 360
    rings = "".join(
        f'<circle cx="{width / 2}" cy="{height / 2}" r="{radius}" fill="none" stroke="white" opacity=".24"/>'
        for radius in range(15, max(width, height), 15)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="hsl({hue} 55% 22%)"/>
<stop offset="1" stop-color="hsl({hue} 52% 43%)"/></linearGradient></defs>
<rect width="100%" height="100%" fill="url(#g)"/>{rings}
<rect x="14" y="14" width="{width-28}" height="{height-28}" fill="none" stroke="white" stroke-width="5"/>
<text x="50%" y="48%" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="sans-serif" font-size="112">{number:02d}</text>
<text x="50%" y="60%" text-anchor="middle" fill="white" font-family="sans-serif" font-size="42">PREVIEW SAMPLE</text>
</svg>'''

def child_pages():
    cards = []
    for number in range(1, 17):
        title = f"確認用サンプル {number:02d}"
        card = _card({
            "src": f"photos/sample-{number:02d}.svg", "gallery_name": title,
            "capture_date": "2025-10-05", "is_annual_best": False,
            "location": "", "article_url": "", "article_title": "",
            "comment": "テスト用の画像・撮影情報です。",
            "selection_id": f"preview-{number:02d}",
        })
        caption = html.escape(
            f'<div class="exif-wrap"><div class="exif-title">{title}</div>'
            '<div class="exif-middle">検証用カメラ / Macro 60mm</div>'
            '<div class="exif-bottom-row"><span>60mm</span><span>F5.6</span>'
            '<span>1/125s</span><span>ISO400</span><span>2025/10/05</span></div></div>',
            quote=True,
        )
        cards.append(re.sub(r'data-sub-html="[^"]*"', f'data-sub-html="{caption}"', card, count=1))
    gallery = (
        '<section class="best-shots-hub">'
        + _best_shots_hero("LightGallery 実機確認", "写真08以降までスクロールして開いてください。",
                           "best-shots.html", "確認用一覧へ戻る")
        + '</section><section class="best-shots-content">'
        + '<section class="best-shot-month"><h2>確認用写真 01–16</h2><div class="best-shot-grid">'
        + ''.join(cards) + '</div></section></section>'
        + '<footer class="best-shots-footer"><a href="best-shots.html">確認用一覧へ戻る</a></footer>'
    )
    index = (
        '<section class="best-shots-hub">'
        + _best_shots_hero("確認用一覧", "ブラウザの戻る・進むを確認できます。",
                           "best-shots-2025.html", "確認用の写真を開く")
        + '</section><section class="best-shots-content"><a href="best-shots-2025.html">写真01–16を表示</a></section>'
    )
    return {
        "best-shots-2025.html": _document("LightGallery 確認用写真", gallery),
        "best-shots.html": _document("LightGallery 確認用一覧", index),
    }

def host_page(version, mode, handler, patch):
    body_mode = mode == "body"
    mode_name = "独立BODYスクロール" if body_mode else "通常埋め込み"
    label = "修正後" if version == "after" else "修正前"
    wrapper = "galleryWrapper" if body_mode else "kinoko-home-portal"
    return f'''<!doctype html>
<html lang="ja" class="{'body-case' if body_mode else 'root-case'}">
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{mode_name} / {label} / PR #142</title><style>{HOST_STYLE}</style>
<header><a href="__PREVIEW_HOME__">← 確認メニュー</a><h1>{mode_name} · {label}</h1>
<p>写真の一覧を下にスクロールし、写真08以降を1枚開いてください。閉じた後に同じ番号の写真へ戻るかを確認します。</p>
<p>確認用の画像・撮影情報を使用しています。</p></header>
<section id="{wrapper}"><iframe id="photoGallery" title="確認用ギャラリー"
src="__PREVIEW_CHILD__/best-shots-2025.html" scrolling="no"
sandbox="allow-scripts allow-same-origin" allow="fullscreen"></iframe></section>
{handler}
{patch if version == 'after' else ''}
</html>'''

LANDING = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>きのこブログ｜LightGallery 実機確認</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#f6f4ed;color:#233b2a;font:16px/1.6 system-ui,sans-serif}
main{max-width:60rem;padding:clamp(18px,5vw,50px);margin:auto}
h1{font-size:clamp(1.7rem,4vw,2.7rem);line-height:1.2}
.kicker{font-size:.8rem;font-weight:750;letter-spacing:.13em}
section{background:#fff;border:1px solid #d9dfd4;border-radius:14px;padding:20px;margin-top:16px}
h2{margin:0}
.sha{overflow-wrap:anywhere;font:12px monospace;color:#485d4c}
nav{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:8px;margin-top:16px}
a{padding:12px 8px;text-align:center;color:#fff;background:#2c5839;text-decoration:none;border-radius:8px;font-weight:700}
a:focus-visible{outline:3px solid #ae701e;outline-offset:3px}
</style>
<main><p class="kicker">きのこブログ / PR #142</p><h1>LightGallery 実機確認</h1>
<p>「修正後」を開き、写真08以降を選んでください。同じケースの「修正前」と比べられます。</p>
<!-- MODES -->
<p>同じWi-Fi内だけのプレビューです。終了は起動したウィンドウで Ctrl+C。</p>
</main></html>
"""

def build(output):
    footer = git_file(CANDIDATE, FOOTER)
    if sha(footer) != FOOTER_SHA:
        raise ValueError("Frozen Hatena footer changed")
    handler = footer.decode("utf-8")
    handler = handler[handler.rindex("<script>"):]
    patch = git_file(CANDIDATE, PATCH).decode("utf-8")
    guard = (HERE / "share-guard.js").read_bytes()
    files = {"host/index.html": LANDING.encode()}
    originals = {}
    pages = child_pages()
    for version, commit in (("before", BASELINE), ("after", CANDIDATE)):
        for name in ASSETS:
            data = git_file(commit, name)
            files[f"{version}/{name}"] = data
        for name in ("assets/gallery.css", "assets/gallery.js"):
            originals[f"{version}/{name}"] = sha(files[f"{version}/{name}"])
        if files[f"{version}/assets/gallery.js"].count(b"'https://exsudoporus-ruber.hatenablog.jp'") != 1:
            raise ValueError("Expected exactly one trusted parent origin")
        for name, page in pages.items():
            guarded = page.replace("</head>", '<script src="assets/share-guard.js"></script></head>')
            files[f"{version}/{name}"] = guarded.encode()
        files[f"{version}/assets/share-guard.js"] = guard
        # The checked-in bundle references an omitted spinner. Serve a neutral
        # offline placeholder at that exact path without changing vendor CSS.
        files[f"{version}/lightgallery/images/loading.gif"] = base64.b64decode(
            "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
        )
        for number in range(1, 17):
            files[f"{version}/photos/sample-{number:02d}.svg"] = sample_image(number).encode()
        for mode in ("normal", "body"):
            files[f"host/{version}/{mode}.html"] = host_page(version, mode, handler, patch).encode()

    manifest = {
        "candidate": CANDIDATE, "published_baseline": BASELINE,
        "frozen_footer_sha256": FOOTER_SHA, "candidate_parent_patch_sha256": sha(patch.encode()),
        "original_gallery_sha256": originals,
        "files": {name: sha(data) for name, data in sorted(files.items())},
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    files["server.mjs"] = (HERE / "server.mjs").read_bytes()
    files["START-WINDOWS.cmd"] = (HERE / "start-windows.cmd").read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    files["REAL_DEVICE_PREVIEW.md"] = (REPO / MANUAL).read_bytes()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry = ZipInfo(name, date_time=(2026, 11, 8, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, data)
    print(output)
    print("SHA-256", sha(output.read_bytes()))


if __name__ == "__main__":
    build(Path(sys.argv[1]).resolve())
