import feedparser
from bs4 import BeautifulSoup
import os

# --- 環境変数（GitHub Actionsまたはローカルで設定） ---
USER = os.getenv("HATENA_USER")
API_KEY = os.getenv("HATENA_API_KEY")
BLOG_ID = os.getenv("HATENA_BLOG_ID")
ATOM_URL = f"https://blog.hatena.ne.jp/exsudoporus_ruber/exsudoporus-ruber.hatenablog.jp/atom/entry"

# --- 記事を取得し、画像とalt属性を抽出 ---
def fetch_images_by_alt():
    feed = feedparser.parse(ATOM_URL)
    data = {}
    for e in feed.entries:
        html = e.content[0].value
        soup = BeautifulSoup(html, "html.parser")

        for img in soup.find_all("img"):
            src = img.get("src")
            alt = img.get("alt", "").strip() or "未分類"
            if not src:
                continue
            if alt not in data:
                data[alt] = set()
            data[alt].add(src)

    return data


# --- HTMLギャラリー生成 ---
def generate_html(galleries):
    os.makedirs("output", exist_ok=True)

    # CSS（全ページ共通）
    css = """<style>
    body { font-family: "Helvetica", "Hiragino Sans", sans-serif; background:#fafafa; color:#333; margin:2em; }
    h1 { text-align:center; }
    .gallery { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px,1fr)); gap:12px; margin-top:20px; }
    .gallery img { width:100%; border-radius:12px; box-shadow:0 2px 6px rgba(0,0,0,0.1); transition:transform 0.2s; }
    .gallery img:hover { transform:scale(1.03); }
    nav { text-align:center; margin-bottom:2em; }
    nav a { margin:0 8px; text-decoration:none; color:#0078ff; font-weight:bold; }
    nav a:hover { text-decoration:underline; }
    </style>"""

    # トップページ
    index_html = f"<h1>🍄 フォトギャラリー</h1>{css}<nav>\n"
    for cat in sorted(galleries.keys()):
        slug = cat.replace(" ", "_")
        index_html += f'<a href="{slug}.html">{cat}</a>\n'
    index_html += "</nav><p>画像のalt属性をもとに自動生成しています。</p>"

    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    # 各カテゴリページ
    for cat, imgs in galleries.items():
        slug = cat.replace(" ", "_")
        html = f"<h1>{cat}</h1>{css}<nav><a href='index.html'>← 戻る</a></nav><div class='gallery'>\n"
        for i in imgs:
            html += f'<img src="{i}" alt="{cat}">\n'
        html += "</div>"
        with open(f"output/{slug}.html", "w", encoding="utf-8") as f:
            f.write(html)


# --- 実行 ---
if __name__ == "__main__":
    print("📡 はてなブログから画像を取得中…")
    galleries = fetch_images_by_alt()
    print(f"🧩 {len(galleries)}カテゴリの画像を検出")
    generate_html(galleries)
    print("✅ ギャラリーページを生成しました！（/output）")
