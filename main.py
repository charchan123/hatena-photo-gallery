import feedparser, re, os
from datetime import datetime

USER = os.getenv("HATENA_USER")
API_KEY = os.getenv("HATENA_API_KEY")
BLOG_ID = os.getenv("HATENA_BLOG_ID")
ATOM_URL = f"https://blog.hatena.ne.jp/{USER}/{BLOG_ID}/atom/entry"

def extract_images(html):
    return re.findall(r'<img [^>]*src="([^"]+)"', html)

def extract_categories(entry):
    return [c["term"] for c in entry.get("tags", [])]

def fetch_entries():
    feed = feedparser.parse(ATOM_URL)
    entries = []
    for e in feed.entries:
        images = extract_images(e.content[0].value)
        cats = extract_categories(e)
        for c in cats:
            if not images:
                continue
            entries.append({"category": c, "images": images})
    return entries

def build_galleries(entries):
    galleries = {}
    for e in entries:
        galleries.setdefault(e["category"], set()).update(e["images"])
    return galleries

def generate_html(galleries):
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

if __name__ == "__main__":
    entries = fetch_entries()
    galleries = build_galleries(entries)
    generate_html(galleries)
    print(f"✅ {len(galleries)}カテゴリの写真ギャラリーを生成しました！")
