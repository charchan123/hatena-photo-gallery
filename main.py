import os
import re

# ====== 設定 ======
OUTPUT_DIR = "output"
HATENA_BLOG_ID = "charchan123"
AIUO_GROUPS = {
    "あ行": "あいうえお",
    "か行": "かきくけこ",
    "さ行": "さしすせそ",
    "た行": "たちつてと",
    "な行": "なにぬねの",
    "は行": "はひふへほ",
    "ま行": "まみむめも",
    "や行": "やゆよ",
    "ら行": "らりるれろ",
    "わ行": "わをん",
}

# ====== LightGallery関連タグ ======
LIGHTGALLERY_TAGS = """
<!-- LightGallery CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/lightgallery@2.7.2/css/lightgallery-bundle.min.css">

<!-- LightGallery JS (プラグインは先に) -->
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.7.2/plugins/thumbnail/lg-thumbnail.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.7.2/plugins/zoom/lg-zoom.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.7.2/lightgallery.min.js"></script>
"""

# ====== LightGallery初期化スクリプト ======
LIGHTGALLERY_INIT = """
<script>
document.addEventListener("DOMContentLoaded", function() {
    console.log("✅ LightGallery init start");
    console.log("window.lgThumbnail =", window.lgThumbnail);
    console.log("window.lgZoom =", window.lgZoom);

    const galleries = document.querySelectorAll('.gallery');
    galleries.forEach(gallery => {
        lightGallery(gallery, {
            plugins: [lgThumbnail, lgZoom],
            speed: 500,
            thumbnail: true
        });
    });

    console.log("✅ LightGallery initialized");
});
</script>
"""

# ====== CSS / JS（Masonryなど） ======
STYLE_TAG = """
<style>
body {
    font-family: "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
    background: #fafafa;
    color: #333;
    margin: 0;
    padding: 20px;
}
.gallery {
    column-count: 4;
    column-gap: 10px;
}
.gallery img {
    width: 100%;
    margin-bottom: 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: transform 0.2s;
}
.gallery img:hover {
    transform: scale(1.03);
}
@media (max-width: 800px) {
    .gallery { column-count: 2; }
}
@media (max-width: 500px) {
    .gallery { column-count: 1; }
}
</style>
"""

SCRIPT_TAG = """
<script>
// Masonry風レイアウト調整
window.addEventListener('load', function() {
    document.querySelectorAll('.gallery').forEach(gallery => {
        gallery.querySelectorAll('img').forEach(img => {
            img.style.breakInside = 'avoid';
        });
    });
});
</script>
"""

# ====== ギャラリー生成 ======
def generate_gallery(entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    def safe_filename(name):
        name = re.sub(r'[:<>\"|*?\\/\r\n]', '_', name)
        name = name.strip()
        if not name:
            name = "unnamed"
        return name

    group_links = " | ".join([f'<a href="{g}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px; text-align:center;'>{group_links}</div>"

    # 各キノコページ
    for alt, imgs in grouped.items():
        html = f"<h2>{alt}</h2><div class='gallery'>"
        article_url = f"https://{HATENA_BLOG_ID}.hatena.blog/"
        for src in imgs:
            html += f'<img src="{src}" alt="{alt}" loading="lazy" data-url="{article_url}">'
        html += "</div>"
        html += """
        <div style='margin-top:40px; text-align:center;'>
            <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """
        html += STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS + LIGHTGALLERY_INIT
        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # 五十音別ページ
    aiuo_dict = {k: [] for k in AIUO_GROUPS.keys()}
    for alt in grouped.keys():
        g = get_aiuo_group(alt)
        if g in aiuo_dict:
            aiuo_dict[g].append(alt)

    for g, names in aiuo_dict.items():
        html = f"<h2>{g}のキノコ</h2><ul>"
        for n in sorted(names):
            safe = safe_filename(n)
            html += f'<li><a href="{safe}.html">{n}</a></li>'
        html += "</ul>"
        html += group_links_html
        html += STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS + LIGHTGALLERY_INIT
        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # index.html
    index = "<h2>五十音別分類</h2><ul>"
    for g in AIUO_GROUPS.keys():
        index += f'<li><a href="{safe_filename(g)}.html">{g}</a></li>'
    index += "</ul>" + STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS + LIGHTGALLERY_INIT
    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print("✅ ギャラリーページ生成完了")


# ====== 行グループ判定関数 ======
def get_aiuo_group(name):
    kana = name[0]
    for g, chars in AIUO_GROUPS.items():
        if kana in chars:
            return g
    return "その他"


if __name__ == "__main__":
    print("⚙️ ギャラリー生成スクリプト開始")
    # テスト用エントリ例（実運用では別処理で取得）
    entries = [
        {"alt": "アカヤマタケ", "src": "https://example.com/img1.jpg"},
        {"alt": "カワラタケ", "src": "https://example.com/img2.jpg"},
    ]
    generate_gallery(entries)
