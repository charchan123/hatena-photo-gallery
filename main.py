import feedparser, re, os
from datetime import datetime

# 環境変数から取得
USER = os.getenv("HATENA_USER")
API_KEY = os.getenv("HATENA_API_KEY")
BLOG_ID = os.getenv("HATENA_BLOG_ID")
ATOM_URL = f"https://blog.hatena.ne.jp/{USER}/{BLOG_ID}/atom/entry"

# --- ヘルパー関数 ---
def extract_images(html):
    return re.findall(r'<img [^>]*src="([^"]+)"', html)

def extract_categories(entry):
    return [c["term"] for c in entry.get("tags", [])]

def fetch_entries():
    feed = feedparser.parse(ATOM_URL)
    entries = []
    for e in feed.entries:
        images = extract_images(e.content[0].value) if hasattr(e, "content") else []
        cats = extract_categories(e)
        if not images:
            continue
        for c in cats:
            entries.append({"category": c, "images": images})
    return entries

def build_galleries(entries):
    galleries = {}
    for e in entries:
        galleries.setdefault(e["category"], set()).update(e["images"])
    return galleries

# --- カテゴリ別ページ生成 ---
def generate_category_pages(galleries):
    os.makedirs("output", exist_ok=True)
    css = """<style>
    body {font-family:sans-serif; background:#fafafa; color:#333;}
    .gallery {display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:8px;}
    .gallery img {width:100%; border-radius:8px;}
    </style>"""
    for cat, imgs in galleries.items():
        cat_slug = cat.replace(" ", "_")
        html = f"<h1>{cat}</h1>{css}<div class='gallery'>\n"
        for i in imgs:
            html += f'<img src="{i}" alt="{cat}">\n'
        html += "</div>"
        with open(f"output/{cat_slug}.html", "w", encoding="utf-8") as f:
            f.write(html)

# --- まとめページ生成 ---
def generate_index_page(entries):
    os.makedirs("output", exist_ok=True)
    html = """<html><head><meta charset="utf-8"><title>キノコ写真集</title>
    <style>
    body {font-family:sans-serif; padding:20px;}
    h1 {text-align:center;}
    .gallery {display:flex; flex-wrap:wrap; gap:10px; justify-content:center;}
    .gallery img {width:200px; height:auto; border-radius:5px; box-shadow:0 2px 5px rgba(0,0,0,0.2);}
    </style></head><body><h1>キノコ写真集</h1><div class="gallery">"""

    for e in entries:
        for img in e["images"]:
            html += f'<img src="{img}" alt="{e["category"]}">'
    html += "</div></body></html>"

    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(html)

# --- メイン処理 ---
if __name__ == "__main__":
    entries = fetch_entries()
    galleries = build_galleries(entries)
    generate_category_pages(galleries)  # カテゴリ別ページ
    generate_index_page(entries)         # まとめページ
    print(f"✅ {len(galleries)}カテゴリの写真ギャラリーを生成し、まとめページも作成しました！")
