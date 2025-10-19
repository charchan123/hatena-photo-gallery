import feedparser, os
from bs4 import BeautifulSoup

USER = os.getenv("HATENA_USER")
BLOG_ID = os.getenv("HATENA_BLOG_ID")
ATOM_URL = f"https://blog.hatena.ne.jp/exsudoporus_ruber/exsudoporus-ruber.hatenablog.jp/atom/entry"

def fetch_entries():
    print(f"📡 はてなブログから画像を取得中…")
    feed = feedparser.parse(ATOM_URL)
    entries = []
    for e in feed.entries:
        html = e.content[0].value
        soup = BeautifulSoup(html, "html.parser")
        imgs = soup.find_all("img")

        for img in imgs:
            alt = img.get("alt", "").strip()
            src = img.get("src")
            if alt and src:
                entries.append({"alt": alt, "src": src})

    print(f"🧩 {len(entries)}枚の画像を検出しました")
    return entries

def generate_html(entries):
    os.makedirs("output", exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    for alt, imgs in grouped.items():
        html = f"<h1>{alt}</h1><div class='gallery'>\n"
        for i in imgs:
            html += f'<img src="{i}" alt="{alt}" loading="lazy">\n'
        html += "</div>"
        with open(f"output/{alt}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # トップページ
    index = "<h1>フォトギャラリー</h1><ul>"
    for alt in grouped.keys():
        index += f'<li><a href="{alt}.html">{alt}</a></li>'
    index += "</ul>"
    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print(f"✅ ギャラリーページを生成しました！（/output）")

if __name__ == "__main__":
    entries = fetch_entries()
    generate_html(entries)
