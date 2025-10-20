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

            # ★ 記事本文内の画像だけを対象
            entry_content = soup.find("div", class_="entry-content hatenablog-entry")
            if not entry_content:
                continue

            imgs = entry_content.find_all("img")

            for img in imgs:
                alt = img.get("alt", "").strip()
                src = img.get("src")
                if alt and src:
                    entries.append({"alt": alt, "src": src})

    print(f"🧩 {len(entries)}枚の画像を検出しました")
    return entries


# ギャラリーページ生成
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
        a {color:#0066cc; text-decoration:none;}
        a:hover {text-decoration:underline;}
        </style>
        """
        safe_name = alt.replace(" ", "_")
        with open(f"{OUTPUT_DIR}/{safe_name}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # トップページ（全キノコ一覧 + 五十音リンク）
    index = """
    <h1>フォトギャラリー</h1>
    <p>五十音別ページ：</p>
    <p>
    <a href='あ.html'>あ行</a>｜
    <a href='か.html'>か行</a>｜
    <a href='さ.html'>さ行</a>｜
    <a href='た.html'>た行</a>｜
    <a href='な.html'>な行</a>｜
    <a href='は.html'>は行</a>｜
    <a href='ま.html'>ま行</a>｜
    <a href='や.html'>や行</a>｜
    <a href='ら.html'>ら行</a>｜
    <a href='わ.html'>わ行</a>
    </p>
    <ul>
    """
    for alt in sorted(grouped.keys()):
        safe_name = alt.replace(" ", "_")
        index += f'<li><a href="{safe_name}.html">{alt}</a></li>\n'
    index += "</ul>\n"

    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print(f"✅ ギャラリーページを生成しました！（{OUTPUT_DIR}/）")
    return grouped


# 五十音別インデックスページ生成
def generate_index_pages(grouped):
    kana_groups = {
        "あ": "あいうえお",
        "か": "かきくけこ",
        "さ": "さしすせそ",
        "た": "たちつてと",
        "な": "なにぬねの",
        "は": "はひふへほ",
        "ま": "まみむめも",
        "や": "やゆよ",
        "ら": "らりるれろ",
        "わ": "わをん",
    }

    for head, chars in kana_groups.items():
        html = f"<h1>{head}行のキノコ</h1><ul>\n"
        for alt in sorted(grouped.keys()):
            if alt[0] in chars:
                safe_name = alt.replace(" ", "_")
                html += f'<li><a href="{safe_name}.html">{alt}</a></li>\n'
        html += "</ul>\n"
        html += """
        <style>
        body {font-family:sans-serif; background:#fafafa; color:#333; padding:20px;}
        a {color:#0066cc; text-decoration:none;}
        a:hover {text-decoration:underline;}
        </style>
        """
        with open(f"{OUTPUT_DIR}/{head}.html", "w", encoding="utf-8") as f:
            f.write(html)

    print("🗂 五十音索引ページを生成しました！")


# 実行
if __name__ == "__main__":
    entries = fetch_images()
    grouped = generate_gallery(entries)
    generate_index_pages(grouped)
