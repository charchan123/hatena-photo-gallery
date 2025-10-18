import feedparser, re, os
from datetime import datetime

USER = os.getenv("HATENA_USER")
API_KEY = os.getenv("HATENA_API_KEY")
BLOG_ID = os.getenv("HATENA_BLOG_ID")

ATOM_URL = f"https://blog.hatena.ne.jp/{USER}/{BLOG_ID}/atom/entry"

def extract_images(html):
    """HTMLから画像URLを抽出"""
    return re.findall(r'<img [^>]*src="([^"]+)"', html)

def extract_categories(entry):
    """記事のカテゴリを取得"""
    return [c["term"] for c in entry.get("tags", [])]

def fetch_entries():
    """はてなブログから記事情報を取得"""
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
    """カテゴリごとに画像をまとめる"""
    galleries = {}
    for e in entries:
        galleries.setdefault(e["category"], set()).update(e["images"])
    return galleries

def generate_html(galleries):
    """HTMLを生成して /output に出力"""
    os.makedirs("output", exist_ok=True)

    css = """<style>
    body {font-family:sans-serif; background:#fafafa; color:#333; padding:20px;}
    a {text-decoration:none; color:#0070f3;}
    a:hover {text-decoration:underline;}
    .gallery {display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px; margin-top:20px;}
    .gallery img {width:100%; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    h1 {font-size:1.8em; border-bottom:2px solid #0070f3; padding-bottom:6px;}
    .cat-list {display:flex; flex-wrap:wrap; gap:10px; margin-top:20px;}
    .cat-list a {padding:6px 12px; border:1px solid #0070f3; border-radius:20px; font-size:0.9em;}
    </style>"""

    # 各カテゴリページ生成
    for cat, imgs in galleries.items():
        cat_slug = cat.replace(" ", "_")
        html = f"<html><head><meta charset='utf-8'><title>{cat}ギャラリー</title>{css}</head><body>"
        html += f"<h1>{cat}</h1><a href='index.html'>← カテゴリ一覧へ戻る</a>"
        html += "<div class='gallery'>\n"
        for i in imgs:
            html += f'<img src="{i}" alt="{cat}">\n'
        html += "</div></body></html>"
        with open(f"output/{cat_slug}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # トップページ（カテゴリ一覧）
    index_html = f"<html><head><meta charset='utf-8'><title>はてなフォトギャラリー</title>{css}</head><body>"
    index_html += "<h1>📸 はてなフォトギャラリー</h1><p>カテゴリをクリックすると写真ギャラリーを表示します。</p>"
    index_html += "<div class='cat-list'>"
    for cat in sorted(galleries.keys()):
        slug = cat.replace(' ', '_')
        index_html += f"<a href='{slug}.html'>{cat}</a>"
    index_html += "</div></body></html>"

    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"✅ {len(galleries)}カテゴリの写真ギャラリーを生成しました！")

if __name__ == "__main__":
    entries = fetch_entries()
    galleries = build_galleries(entries)
    generate_html(galleries)
