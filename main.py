import os, glob
from bs4 import BeautifulSoup

# 記事HTMLを置いたフォルダ
ARTICLES_DIR = "articles"
OUTPUT_DIR = "output"

# 画像を抽出
def fetch_images():
    print("📂 ローカルHTMLから画像を取得中…")
    entries = []
    html_files = glob.glob(f"{ARTICLES_DIR}/*.html")
    for html_file in html_files:
        with open(html_file, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            imgs = soup.find_all("img")
            for img in imgs:
                alt = img.get("alt", "").strip()
                src = img.get("src")
                if alt and src:
                    entries.append({"alt": alt, "src": src})
    print(f"🧩 {len(entries)}枚の画像を検出しました")
    return entries

# HTML生成
def generate_gallery(entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    # 各カテゴリページ
    for alt, imgs in grouped.items():
        html = f"<h1>{alt}</h1><div class='gallery'>\n"
        for src in imgs:
            html += f'<img src="{src}" alt="{alt}" loading="lazy">\n'
        html += "</div>\n"
        html += """
        <style>
        .gallery {display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:8px;}
        .gallery img {width:100%; border-radius:8px;}
        body {font-family:sans-serif; background:#fafafa; color:#333; padding:20px;}
        </style>
        """
        safe_name = alt.replace(" ", "_")
        with open(f"{OUTPUT_DIR}/{safe_name}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # トップページ
    index = "<h1>フォトギャラリー</h1><ul>\n"
    for alt in grouped.keys():
        safe_name = alt.replace(" ", "_")
        index += f'<li><a href="{safe_name}.html">{alt}</a></li>\n'
    index += "</ul>\n"
    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print(f"✅ ギャラリーページを生成しました！（{OUTPUT_DIR}/）")

if __name__ == "__main__":
    entries = fetch_images()
    generate_gallery(entries)
