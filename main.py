import os
from bs4 import BeautifulSoup

ARTICLES_DIR = "articles"
OUTPUT_DIR = "output"

def fetch_entries_from_html():
    print("📂 ローカルHTMLから画像を取得中…")
    entries = []
    for filename in os.listdir(ARTICLES_DIR):
        if not filename.endswith(".html"):
            continue
        path = os.path.join(ARTICLES_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

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
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    # 各カテゴリページを作成
    for alt, imgs in grouped.items():
        html = f"<h1>{alt}</h1><div class='gallery'>\n"
        for i in imgs:
            html += f'<img src="{i}" alt="{alt}" loading="lazy">\n'
        html += "</div>"
        with open(f"{OUTPUT_DIR}/{alt}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # トップページを作成
    index = "<h1>フォトギャラリー</h1><ul>"
    for alt in grouped.keys():
        index += f'<li><a href="{alt}.html">{alt}</a></li>'
    index += "</ul>"
    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print(f"✅ ギャラリーページを生成しました！（{OUTPUT_DIR}/ 内）")

if __name__ == "__main__":
    entries = fetch_entries_from_html()
    generate_html(entries)
