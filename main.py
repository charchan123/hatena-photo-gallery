import os
import glob
import time
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re

# ====== 設定 ======
HATENA_USER = os.getenv("HATENA_USER")
HATENA_BLOG_ID = os.getenv("HATENA_BLOG_ID")
HATENA_API_KEY = os.getenv("HATENA_API_KEY")

if not all([HATENA_USER, HATENA_BLOG_ID, HATENA_API_KEY]):
    raise EnvironmentError(
        "環境変数が未設定です。HATENA_USER, HATENA_BLOG_ID, HATENA_API_KEY を確認してください。"
    )

ARTICLES_DIR = "articles"
OUTPUT_DIR = "output"

# ====== API エンドポイント ======
ATOM_ENDPOINT = f"https://blog.hatena.ne.jp/{HATENA_USER}/{HATENA_BLOG_ID}/atom/entry"
AUTH = (HATENA_USER, HATENA_API_KEY)
HEADERS = {}

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

# ====== 共通スタイル ======
STYLE_TAG = """<style>
html, body {
  margin: 0;
  padding: 0;
  overflow-y: hidden;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background:#fafafa;
  color:#333;
  padding:16px;
  box-sizing:border-box;
}
.gallery {
  column-count: 2;
  column-gap: 10px;
  max-width: 800px;
  margin: 0 auto;
}
.gallery img {
  width: 100%;
  margin-bottom: 10px;
  border-radius: 6px;
  cursor: zoom-in;
  transition: opacity 0.6s ease, transform 0.6s ease;
  opacity: 0;
  transform: translateY(10px);
}
.gallery img.visible {
  opacity: 1;
  transform: translateY(0);
}
@media (max-width: 480px) {
  .gallery { column-count: 1; }
}

/* Lightbox */
#lb-overlay {
  position: fixed;
  top:0; left:0;
  width:100vw; height:100vh;
  background: rgba(0,0,0,0.9);
  display:flex;
  justify-content:center;
  align-items:center;
  visibility:hidden;
  opacity:0;
  transition: opacity 0.3s ease;
  z-index:9999;
}
#lb-overlay.show { visibility:visible; opacity:1; }
#lb-overlay img { max-width:90%; max-height:80vh; border-radius:6px; box-shadow:0 0 10px rgba(0,0,0,0.8);}
#lb-overlay .lb-caption { position:absolute; top:20px; left:20px; color:#fff; font-size:16px; }
#lb-overlay .lb-link { position:absolute; bottom:20px; left:50%; transform:translateX(-50%); color:#ccc; font-size:14px; text-decoration:underline; }
#lb-overlay .lb-close { position:absolute; top:20px; right:30px; color:#fff; font-size:28px; cursor:pointer; }
</style>"""

# ====== 共通スクリプト ======
SCRIPT_TAG = """<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>
<script>
document.addEventListener("DOMContentLoaded", () => {
  function sendHeight() {
    const height = document.documentElement.scrollHeight;
    window.parent.postMessage({ type:"setHeight", height:height }, "*");
  }

  const gallery = document.querySelector(".gallery");
  if (gallery) {
    const fadeObs = new IntersectionObserver(entries=>{
      entries.forEach(e=>{
        if(e.isIntersecting){ e.target.classList.add("visible"); fadeObs.unobserve(e.target); }
      });
    }, {threshold:0.1});
    gallery.querySelectorAll("img").forEach(img=>fadeObs.observe(img));

    imagesLoaded(gallery, ()=>{ gallery.style.visibility="visible"; sendHeight(); });

    const lb = document.createElement("div");
    lb.id="lb-overlay";
    lb.innerHTML=`
      <span class="lb-close">&times;</span>
      <img src="" alt="">
      <div class="lb-caption"></div>
      <a class="lb-link" href="#" target="_blank">元記事を見る</a>
    `;
    document.body.appendChild(lb);

    const lbImg = lb.querySelector("img");
    const lbCaption = lb.querySelector(".lb-caption");
    const lbLink = lb.querySelector(".lb-link");
    const lbClose = lb.querySelector(".lb-close");

    gallery.querySelectorAll("img").forEach(img=>{
      img.addEventListener("click", ()=>{
        lb.classList.add("show");
        lbImg.src = img.src;
        lbCaption.textContent = img.alt || "";
        lbLink.href = img.dataset.url || "#";
        sendHeight();
      });
    });

    lbClose.addEventListener("click", ()=>lb.classList.remove("show"));
    lb.addEventListener("click", e=>{ if(e.target===lb) lb.classList.remove("show"); });
  }

  sendHeight();
  window.addEventListener("load", ()=>{
    sendHeight(); setTimeout(sendHeight,800); setTimeout(sendHeight,2000); setTimeout(sendHeight,4000);
  });
  window.addEventListener("message", e=>{ if(e.data?.type==="requestHeight") sendHeight(); });
  window.addEventListener("resize", sendHeight);
  new MutationObserver(sendHeight).observe(document.body,{childList:true,subtree:true});

  document.addEventListener("click", e=>{
    const a = e.target.closest("a");
    if(!a) return;
    const href = a.getAttribute("href")||"";
    if(href.startsWith("javascript:history.back") || href.endsWith(".html") || href.includes("index")){
      console.log("🖱 クリックリンク送信:", href);
      window.parent.postMessage({type:"scrollToTitle", offset:100}, "*");
    }
  });
});
</script>"""

# ====== APIから全記事を取得 ======
def fetch_hatena_articles_api():
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    print(f"📡 はてなブログAPIから全記事取得中…")
    url = ATOM_ENDPOINT
    count = 0
    while url:
        print(f"🔗 Fetching: {url}")
        r = requests.get(url, auth=AUTH, headers=HEADERS)
        if r.status_code != 200:
            raise RuntimeError(f"❌ API取得失敗: {r.status_code} {r.text}")

        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)

        for i, entry in enumerate(entries, 1):
            content = entry.find("atom:content", ns)
            if content is None:
                continue
            html_content = content.text or ""
            filename = f"{ARTICLES_DIR}/article_{count+i}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"✅ 保存完了: {filename}")

        count += len(entries)
        next_link = root.find("atom:link[@rel='next']", ns)
        url = next_link.attrib["href"] if next_link is not None else None

    print(f"📦 合計 {count} 件の記事を保存しました。")

# ====== HTMLから画像とaltを抽出 ======
def fetch_images():
    print("📂 HTMLから画像抽出中…")
    entries = []

    exclude_patterns = [
        r'はてなブックマーク',
        r'^\d{4}年',
        r'^この記事をはてなブックマークに追加$',
        r'^ワ行$',
        r'キノコと田舎遊び',
    ]

    for html_file in glob.glob(f"{ARTICLES_DIR}/*.html"):
        with open(html_file, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        body_div = soup.find(class_="entry-body")
        if not body_div:
            body_div = soup

        for iframe in body_div.find_all("iframe"):
            title = iframe.get("title", "")
            if any(re.search(p, title) for p in exclude_patterns):
                iframe.decompose()

        for a in body_div.find_all("a"):
            text = a.get_text(strip=True)
            if any(re.search(p, text) for p in exclude_patterns):
                a.decompose()

        imgs = body_div.find_all("img")
        for img in imgs:
            alt = img.get("alt", "").strip()
            src = img.get("src")
            if not alt or not src:
                continue
            if any(re.search(p, alt) for p in exclude_patterns):
                continue
            entries.append({"alt": alt, "src": src})

    print(f"🧩 画像検出数: {len(entries)} 枚")
    return entries

# ====== 五十音分類 ======
def get_aiuo_group(name):
    if not name:
        return "その他"
    first = name[0]
    for group, chars in AIUO_GROUPS.items():
        if first in chars:
            return group
    return "その他"

# ====== ギャラリー生成（LightGalleryスライド完全対応版） ======
def generate_gallery(entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    # 五十音リンク
    group_links = " | ".join([f'<a href="{g}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px; text-align:center;'>{group_links}</div>"

    # ファイル名安全化
    def safe_filename(name):
        name = re.sub(r'[:<>\"|*?\\/\r\n]', '_', name)
        name = name.strip()
        if not name:
            name = "unnamed"
        return name

    # LightGallery関連タグ（スライドショー機能完全対応）
    LIGHTGALLERY_TAGS = """
<!-- LightGallery -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/lightgallery@2.8.0/css/lightgallery-bundle.min.css">
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.0/lightgallery.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.0/plugins/zoom/lg-zoom.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.0/plugins/thumbnail/lg-thumbnail.umd.min.js"></script>
<script>
document.addEventListener("DOMContentLoaded", () => {
    const galleries = document.querySelectorAll('.gallery');
    galleries.forEach(gallery => {
        lightGallery(gallery, {
            selector: 'a', // <a>タグ単位でスライド
            plugins: [lgZoom, lgThumbnail],
            speed: 400,
            thumbnail: true,
            download: false,
            zoom: true,
            fullScreen: true,
            actualSize: false,
            slideShow: true,
            autoplay: false,
            mobileSettings: {
                controls: true,
                showCloseIcon: true,
                download: false
            }
        });
    });
});
</script>

<style>
/* ---- LightGallery ＋ Masonry ---- */
.gallery {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
}

.gallery a {
    display: block;
    position: relative;
    flex: 1 1 calc(33.333% - 8px);
    max-width: 300px;
    overflow: hidden;
}

.gallery img {
    width: 100%;
    height: auto;
    border-radius: 6px;
    cursor: zoom-in;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.gallery img:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
}

/* LightGallery内の背景と矢印の色など */
.lg-backdrop {
    background: rgba(0, 0, 0, 0.9);
}

.lg-prev, .lg-next {
    color: white !important;
    font-size: 28px !important;
}

.lg-close {
    color: white !important;
    font-size: 26px !important;
}
</style>
"""

    # ==== 各ページ生成 ====
    for alt, imgs in grouped.items():
        html = f"<h2>{alt}</h2><div class='gallery'>"
        for src in imgs:
            article_url = f"https://{HATENA_BLOG_ID}.hatena.blog/"
            # LightGallery用に必ず<a>で囲む
            html += f'<a href="{src}" data-sub-html="<h4>{alt}</h4><p>{article_url}</p>"><img src="{src}" alt="{alt}" loading="lazy"></a>'
        html += "</div>"

        # 戻るリンク
        html += """
        <div style='margin-top:40px; text-align:center;'>
            <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """

        # スタイル・スクリプト統合
        html += STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS

        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # ==== 五十音別ページ ====
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
        html += "</ul>" + group_links_html
        html += STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS
        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # ==== index.html ====
    index = "<h2>五十音別分類</h2><ul>"
    for g in AIUO_GROUPS.keys():
        index += f'<li><a href="{safe_filename(g)}.html">{g}</a></li>'
    index += "</ul>" + STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS
    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print("✅ ギャラリーページ生成完了（LightGalleryスライド対応）")

# ====== メイン ======
if __name__ == "__main__":
    fetch_hatena_articles_api()
    entries = fetch_images()
    if entries:
        generate_gallery(entries)
    else:
        print("⚠️ 画像が見つかりませんでした。")
