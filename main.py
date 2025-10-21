import os, glob
from bs4 import BeautifulSoup

ARTICLES_DIR = "articles"
OUTPUT_DIR = "output"

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

# 💡 iframe高さ自動調整スクリプト
SCRIPT_TAG = """
<script>
function sendHeight() {
  window.parent.postMessage({ type: "setHeight", height: document.body.scrollHeight }, "*");
}
window.addEventListener("load", sendHeight);
window.addEventListener("resize", sendHeight);
</script>
"""

# 共通スタイル
STYLE_TAG = """
<style>
html, body {
  margin: 0;
  padding: 0;
  overflow-x: hidden;
  height: auto !important;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #fafafa;
  color: #333;
  padding: 16px;
}
h2 {
  font-size: 1.4em;
  margin-bottom: 12px;
  text-align: center;
}
ul { list-style: none; padding: 0; }
li { margin: 6px 0; text-align: center; }
a { color: #007acc; text-decoration: none; }
a:hover { text-decoration: underline; }
.nav { margin-top: 24px; font-size: 1.1em; text-align: center; flex-wrap: wrap; line-height: 2em; }
strong { color: #000; text-decoration: underline; }

.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  margin-top: 20px;
}
.gallery img {
  width: 100%;
  border-radius: 8px;
  opacity: 0;
  transform: translateY(10px);
  transition: opacity 0.6s ease-out, transform 0.6s ease-out;
}
.gallery img.visible {
  opacity: 1;
  transform: translateY(0);
}

/* スマホ向け最適化 */
@media (max-width: 600px) {
  body { padding: 12px; }
  h2 { font-size: 1.2em; }
  .gallery { gap: 6px; }
}
</style>

<script>
document.addEventListener("DOMContentLoaded", () => {
  const imgs = document.querySelectorAll(".gallery img");
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  imgs.forEach(img => observer.observe(img));
});
</script>
"""

# 画像抽出
def fetch_images():
    print("📂 HTMLから画像を取得中…")
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

# 五十音判定
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

    # 各キノコページ生成
    for alt, imgs in grouped.items():
        html = f"<h2>{alt}</h2>\n<div class='gallery'>\n"
        for src in imgs:
            html += f'<img src="{src}" alt="{alt}" loading="lazy">\n'
        html += "</div>\n" + SCRIPT_TAG + STYLE_TAG

        safe_name = alt.replace(" ", "_")
        with open(f"{OUTPUT_DIR}/{safe_name}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # 五十音別ページ生成
    aiuo_dict = {k: [] for k in AIUO_GROUPS.keys()}
    for alt in grouped.keys():
        group = get_aiuo_group(alt)
        if group in aiuo_dict:
            aiuo_dict[group].append(alt)

    for group, names in aiuo_dict.items():
        html = f"<h2>{group}のキノコ</h2>\n\n<ul>\n"
        for alt in sorted(names):
            safe_name = alt.replace(" ", "_")
            html += f'<li><a href="{safe_name}.html">{alt}</a></li>\n'
        html += "</ul>\n\n"

        # ナビ生成
        nav_links = []
        for g in AIUO_GROUPS.keys():
            if g == group:
                nav_links.append(f"<strong>{g}</strong>")
            else:
                nav_links.append(f'<a href="{g}.html">{g}</a>')
        html += "<div class='nav'>" + "｜".join(nav_links) + "</div>\n"
        html += SCRIPT_TAG + STYLE_TAG

        with open(f"{OUTPUT_DIR}/{group}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # index.html
    index = "<h2>五十音別分類</h2>\n\n<ul>\n"
    for group in AIUO_GROUPS.keys():
        index += f'<li><a href="{group}.html">{group}</a></li>\n'
    index += "</ul>\n" + SCRIPT_TAG + STYLE_TAG

    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print(f"✅ ギャラリーページ生成完了！（{OUTPUT_DIR}/）")

if __name__ == "__main__":
    entries = fetch_images()
    generate_gallery(entries)
