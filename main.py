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

    // imagesLoaded コールバック開始
    imagesLoaded(gallery, () => {
      gallery.style.visibility="visible";
      sendHeight();

      // ===== LightGallery 初期化 =====
      if (typeof lightGallery === 'function') {
        console.log('🎬 LightGallery 初期化開始 (imagesLoaded後)');
        lightGallery(gallery, {
          plugins: [lgZoom, lgThumbnail],
          speed: 500,
          licenseKey: '0000-0000-000-0000',
          download: false,
          thumbnail: true,
          zoom: true,
        });
      } else {
        console.warn('⚠️ LightGallery 初期化失敗: 関数が見つかりません');
      }

    }); // imagesLoaded コールバック終了
  }

  sendHeight();
  window.addEventListener("load", ()=>{ sendHeight(); setTimeout(sendHeight,800); setTimeout(sendHeight,2000); setTimeout(sendHeight,4000); });
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

# ====== LightGallery タグ ======
LIGHTGALLERY_TAGS = """
<!-- LightGallery (CSS/JS) -->
<link rel="stylesheet" href="./lightgallery/lightgallery-bundle.min.css">
<link rel="stylesheet" href="./lightgallery/lg-thumbnail.css">
<script type="text/javascript" src="./lightgallery/lightgallery.min.js"></script>
<script type="text/javascript" src="./lightgallery/lg-zoom.min.js"></script>
<script type="text/javascript" src="./lightgallery/lg-thumbnail.min.js"></script>

<script>
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('.gallery').forEach(gallery => {
    const imgs = Array.from(gallery.querySelectorAll('img'));
    if (imgs.length === 0) return;

    const items = imgs.map(img => ({
      src: img.src,
      thumb: img.src,
      subHtml: `<h4>${(img.alt || '').replace(/"/g,'&quot;')}</h4>`
    }));

    imgs.forEach((img, idx) => {
      img.style.cursor = 'zoom-in';

      img.addEventListener('click', () => {

        /* =========================
            フルスクリーン突入
        ========================== */
        const el = document.documentElement;
        if (el.requestFullscreen) el.requestFullscreen();
        else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
        else if (el.msRequestFullscreen) el.msRequestFullscreen();

        /* =========================
            LightGallery 起動
        ========================== */
        const galleryInstance = lightGallery(document.body, {
          dynamic: true,
          dynamicEl: items,
          index: idx,
          plugins: [lgZoom, lgThumbnail],
          speed: 400,
          thumbnail: true,
          exThumbImage: 'data-exthumbimage',
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

        /* =========================
            ギャラリーが閉じたら
            フルスクリーン解除
        ========================== */
        galleryInstance.on('lgAfterClose', () => {
          if (document.fullscreenElement) {
            document.exitFullscreen().catch(()=>{});
          }
        });

        /* =========================
            ESC でフルスクリーン解除時
            ギャラリーも閉じる
        ========================== */
        document.addEventListener('fullscreenchange', () => {
          if (!document.fullscreenElement) {
            try { galleryInstance.closeGallery(); } catch(e) {}
          }
        });

      });
    });
  });
});
</script>
"""

# ====== LightGallery デバッグ ======
LIGHTGALLERY_DEBUG = """
<script>
console.log("🧪 LightGalleryテスト開始");
console.log("window.lightGallery =", window.lightGallery);
console.log("typeof lightGallery =", typeof lightGallery);
</script>

<script>
fetch('./lightgallery/lightgallery.min.js')
  .then(r => r.text())
  .then(code => {
    console.log("📦 LightGallery 手動ロード開始");
    eval(code);
    console.log("✅ eval後 typeof lightGallery =", typeof lightGallery);
  })
  .catch(e => console.error("❌ 読み込みエラー:", e));
</script>
"""

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

# ====== ギャラリー生成 ======
def generate_gallery(entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    group_links = " | ".join([f'<a href="{g}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px; text-align:center;'>{group_links}</div>"

    def safe_filename(name):
        name = re.sub(r'[:<>\"|*?\\/\r\n]', '_', name)
        name = name.strip()
        if not name:
            name = "unnamed"
        return name

    for alt, imgs in grouped.items():
        html = f"<h2>{alt}</h2><div class='gallery'>"
        for src in imgs:
            article_url = f"https://{HATENA_BLOG_ID}.hatena.blog/"
            html += f'<img src="{src}" alt="{alt}" loading="lazy" data-url="{article_url}" data-exthumbimage="{src}">'
        html += "</div>"
        html += """
        <div style='margin-top:40px; text-align:center;'>
            <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """
        html += STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS + LIGHTGALLERY_DEBUG
        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(html)

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
        html += STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS + LIGHTGALLERY_DEBUG
        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write(html)

    index = "<h2>五十音別分類</h2><ul>"
    for g in AIUO_GROUPS.keys():
        index += f'<li><a href="{safe_filename(g)}.html">{g}</a></li>'
    index += "</ul>" + STYLE_TAG + SCRIPT_TAG + LIGHTGALLERY_TAGS + LIGHTGALLERY_DEBUG
    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print("✅ ギャラリーページ生成完了")

# ====== メイン ======
if __name__ == "__main__":
    fetch_hatena_articles_api()
    entries = fetch_images()
    if entries:
        generate_gallery(entries)
    else:
        print("⚠️ 画像が見つかりませんでした。")
