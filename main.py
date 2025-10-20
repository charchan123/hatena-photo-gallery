import os, glob
from bs4 import BeautifulSoup

# 記事HTMLを置いたフォルダ
ARTICLES_DIR = "articles"
OUTPUT_DIR = "output"

# 五十音分類表
AIUO_GROUPS = {
    "あ行": list("あいうえおアイウエオ"),
    "か行": list("かきくけこカキクケコがぎぐげごガギグゲゴ"),
    "さ行": list("さしすせそサシスセソざじずぜぞザジズゼゾ"),
    "た行": list("たちつてとタチツテトだぢづでどダヂヅデド"),
    "な行": list("なにぬねのナニヌネノ"),
    "は行": list("はひふへほハヒフヘホばびぶべぼバビブベボぱぴぷぺぽパピプペポ"),
    "ま行": list("まみむめもマミムメモ"),
    "や行": list("やゆよヤユヨ"),
    "ら行": list("らりるれろラリルレロ"),
    "わ行": list("わをんワヲン"),
}


# 画像を抽出
def fetch_images():
    print("📂 ローカルHTMLから画像を取得中…")
    entries = []
    html_files = glob.glob(f"{ARTICLES_DIR}/*.html")
    for html_file in html_files:
        with open(html_file, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

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


# 五十音を判定する関数
def get_aiuo_group(name):
    if not name:
        return "その他"
    first = name[0]
    for group, chars in AIUO_GROUPS.items():
        if first in chars:
            return group
    return "その他"


# HTML生成
def generate_gallery(entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    # 各キノコページ
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

    # 五十音別分類
    aiuo_dict = {k: [] for k in AIUO_GROUPS.keys()}
    for alt in grouped.keys():
        group = get_aiuo_group(alt)
        if group in aiuo_dict:
            aiuo_dict[group].append(alt)

    # 各行ページ生成
    for group, names in aiuo_dict.items():
        html = f"<h2>{group}のキノコ</h2>\n<ul>\n"
        for alt in sorted(names):
            safe_name = alt.replace(" ", "_")
            html += f'<li><a href="{safe_name}.html">{alt}</a></li>\n'
        html += "</ul>\n"

        # ナビゲーション生成（現在の行を太字表示）
        nav_links = []
        for g in AIUO_GROUPS.keys():
            if g == group:
                nav_links.append(f"<strong>{g}</strong>")
            else:
                nav_links.append(f'<a href="{g}.html">{g}</a>')
        nav_html = "<div class='nav'>" + "｜".join(nav_links) + "</div>"

        # スタイル
        html += f"""
        {nav_html}
        <style>
        body {{font-family:sans-serif; background:#fafafa; color:#333; padding:20px;}}
        ul {{list-style:none; padding:0;}}
        li {{margin:4px 0;}}
        a {{color:#007acc; text-decoration:none;}}
        a:hover {{text-decoration:underline;}}
        .nav {{margin-top:20px; font-size:1.1em;}}
        strong {{color:#000; text-decoration:underline;}}
        </style>
        """

        with open(f"{OUTPUT_DIR}/{group}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # トップページ
    index = "<h2>五十音別分類</h2>\n<ul>\n"
    for group in AIUO_GROUPS.keys():
        index += f'<li><a href="{group}.html">{group}</a></li>\n'
    index += "</ul>\n"
    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print(f"✅ ギャラリーページを生成しました！（{OUTPUT_DIR}/）")


if __name__ == "__main__":
    entries = fetch_images()
    generate_gallery(entries)
