import os
import glob
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
from io import BytesIO
from PIL import Image, ExifTags

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

# ====== 共通スタイル（Masonry＋EXIFボックス） ======
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
  max-width: 900px;
  margin: 0 auto;
  visibility: hidden;
}
.gallery a.gallery-item{
  display: block;
  break-inside: avoid;
  margin-bottom: 10px;
  border-radius: 8px;
  overflow: hidden;
}
.gallery img {
  width: 100%;
  height: auto;
  display: block;
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

/* LightGallery のキャプション＆EXIF用 */
.lg-caption-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
}
.exif-box {
  margin-top: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(0,0,0,0.55);
  font-size: 13px;
  line-height: 1.6;
}
.exif-box strong {
  font-size: 13px;
}
</style>"""

# ====== LightGallery 読み込みタグ（bundle版 v2） ======
LIGHTGALLERY_TAGS = """
<!-- LightGallery CSS -->
<link rel="stylesheet" href="./lightgallery/lightgallery-bundle.min.css">

<!-- LightGallery JS (bundle版 → v2) -->
<script src="./lightgallery/lightgallery-bundle.min.js"></script>
"""

# ====== スクリプト（フルスクリーン＋親との連携のみ） ======
SCRIPT_TAG = """<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>
<script>
document.addEventListener("DOMContentLoaded", () => {
  function sendHeight() {
    const height = document.documentElement.scrollHeight;
    window.parent.postMessage({ type:"setHeight", height }, "*");
  }

  const gallery = document.querySelector(".gallery");
  if (gallery) {

    // フェードイン
    const fadeObs = new IntersectionObserver(entries=>{
      entries.forEach(e=>{
        if(e.isIntersecting){
          e.target.classList.add("visible");
          fadeObs.unobserve(e.target);
        }
      });
    }, {threshold:0.1});
    gallery.querySelectorAll("img").forEach(img=>fadeObs.observe(img));

    imagesLoaded(gallery, () => {
      console.log("✅ imagesLoaded 完了");
      gallery.style.visibility="visible";
      sendHeight();

      // ===== LightGallery v2 初期化 =====
      const lg = lightGallery(gallery, {
        selector: 'a.gallery-item',
        plugins: [lgZoom, lgThumbnail],
        speed: 400,
        download: false,
        zoom: true,
        thumbnail: true,
      });
      console.log("✅ lg インスタンス:", lg);

      // ① サムネイルクリック時に強制フルスクリーン
      gallery.querySelectorAll("a.gallery-item").forEach((a) => {
        a.addEventListener("click", () => {
          const el = document.documentElement;
          if (el.requestFullscreen) el.requestFullscreen();
          else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
          else if (el.msRequestFullscreen) el.msRequestFullscreen();
        });
      });

      // ② ギャラリーを閉じる前にフルスクリーン解除 + 親に通知
      gallery.addEventListener("lgBeforeClose", () => {
        console.log("📤 子：LG before close 発火");
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(()=>{});
        }
        window.parent.postMessage({ type: "lgClosed" }, "*");
      });

      // ③ ESC でフルスクリーン解除されたらギャラリー閉じて親へ通知
      document.addEventListener("fullscreenchange", () => {
        if (!document.fullscreenElement) {
          console.log("📤 子：fullscreenchange発火 → 親に lgClosed を送信");
          try {
            lg.closeGallery();
            window.parent.postMessage({ type: "lgClosed" }, "*");
          } catch(e) {}
        }
      });

      // ④ 五十音リンク/戻るリンクのクリック → 親にスクロール依頼
      document.addEventListener("click", (e) => {
        const a = e.target.closest("a");
        if (!a) return;
        const txt = a.textContent || "";

        if (/あ行|か行|さ行|た行|な行|は行|ま行|や行|ら行|わ行/.test(txt)) {
          window.parent.postMessage({ type: "scrollToIframeTop" }, "*");
          return;
        }
        if (a.href && a.href.endsWith(".html")) {
          window.parent.postMessage({ type: "scrollToIframeTop" }, "*");
          return;
        }
        if (/戻る/.test(txt)) {
          window.parent.postMessage({ type: "scrollToIframeTop" }, "*");
          return;
        }
      });

    }); // imagesLoaded end
  }

  sendHeight();
  window.addEventListener("load", ()=>{ sendHeight(); setTimeout(sendHeight,800); setTimeout(sendHeight,2000); });
  window.addEventListener("message", e=>{ if(e.data?.type==="requestHeight") sendHeight(); });
  window.addEventListener("resize", sendHeight);
  new MutationObserver(sendHeight).observe(document.body,{childList:true,subtree:true});
});
</script>
"""

# ==========================
#  EXIF 抽出（Python側）
# ==========================
def extract_exif_from_url(url: str) -> dict:
    """画像URLから EXIF を読み、表示用文字列を返す"""
    try:
        print(f"🔍 EXIF取得: {url}")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        img = Image.open(BytesIO(resp.content))
        exif_raw = img._getexif()
        if not exif_raw:
            print("  ↪ EXIFなし")
            return {}

        exif = {}
        for tag, value in exif_raw.items():
            tag_name = ExifTags.TAGS.get(tag, tag)
            exif[tag_name] = value

        # カメラ
        model = exif.get("Model", "")

        # レンズ
        lens = exif.get("LensModel", "") or exif.get("LensMake", "")

        # ISO
        iso = exif.get("ISOSpeedRatings") or exif.get("PhotographicSensitivity")
        if isinstance(iso, (list, tuple)):
            iso = iso[0] if iso else None

        # F値
        fnumber = exif.get("FNumber")
        if isinstance(fnumber, tuple) and len(fnumber) == 2 and fnumber[1] != 0:
            f_val = fnumber[0] / fnumber[1]
            f_str = f"f/{f_val:.1f}"
        else:
            f_str = ""

        # シャッタースピード
        exposure = exif.get("ExposureTime")
        if isinstance(exposure, tuple) and len(exposure) == 2 and exposure[1] != 0:
            # 1/200 みたいな表示
            if exposure[0] == 1:
                exposure_str = f"1/{exposure[1]}"
            else:
                exposure_str = f"{exposure[0]}/{exposure[1]}"
        else:
            exposure_str = str(exposure) if exposure else ""

        # 焦点距離
        focal = exif.get("FocalLength")
        if isinstance(focal, tuple) and len(focal) == 2 and focal[1] != 0:
            focal_val = focal[0] / focal[1]
            focal_str = f"{focal_val:.0f}mm"
        else:
            focal_str = ""

        # 撮影日（YYYY/MM/DD）
        dt = exif.get("DateTimeOriginal") or exif.get("DateTime")
        date_str = ""
        if isinstance(dt, str) and len(dt) >= 10:
            # 形式: 'YYYY:MM:DD HH:MM:SS'
            parts = dt.split(" ")[0].split(":")
            if len(parts) == 3:
                y, m, d = parts
                date_str = f"{y}/{m}/{d}"

        result = {
            "model": model or "",
            "lens": lens or "",
            "iso": str(iso) if iso else "",
            "f": f_str,
            "exposure": exposure_str,
            "focal": focal_str,
            "date": date_str,
        }
        print(f"  ↪ EXIF取得OK: {result}")
        return result

    except Exception as e:
        print(f"⚠️ EXIF取得失敗: {url} ({e})")
        return {}

# ==========================
#  APIから全記事を取得
# ==========================
def fetch_hatena_articles_api():
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    print("📡 はてなブログAPIから全記事取得中…")
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

# ==========================
#  HTMLから画像とalt+EXIFを抽出
# ==========================
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

        body_div = soup.find(class_="entry-body") or soup

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
            alt = (img.get("alt") or "").strip()
            src = img.get("src")
            if not alt or not src:
                continue
            if any(re.search(p, alt) for p in exclude_patterns):
                continue

            exif = extract_exif_from_url(src)

            entries.append({
                "alt": alt,
                "src": src,
                "exif": exif,
            })

    print(f"🧩 画像検出数: {len(entries)} 枚")
    return entries

# ==========================
#  五十音分類
# ==========================
def get_aiuo_group(name):
    if not name:
        return "その他"
    first = name[0]
    for group, chars in AIUO_GROUPS.items():
        if first in chars:
            return group
    return "その他"

# ==========================
#  data-sub-html 用 HTML生成
# ==========================
def build_sub_html(alt: str, exif: dict) -> str:
    parts = []
    parts.append("<div class='lg-caption'>")
    parts.append(f"<div class='lg-caption-title'>{alt}</div>")

    if exif:
        parts.append("<div class='exif-box'><strong>撮影情報</strong><br>")
        if exif.get("model"):
            parts.append(f"カメラ：{exif['model']}<br>")
        if exif.get("lens"):
            parts.append(f"レンズ：{exif['lens']}<br>")
        if exif.get("iso"):
            parts.append(f"ISO：{exif['iso']}<br>")
        if exif.get("f"):
            parts.append(f"絞り：{exif['f']}<br>")
        if exif.get("exposure"):
            parts.append(f"シャッター速度：{exif['exposure']}<br>")
        if exif.get("focal"):
            parts.append(f"焦点距離：{exif['focal']}<br>")
        if exif.get("date"):
            parts.append(f"撮影日：{exif['date']}<br>")
        parts.append("</div>")  # .exif-box

    parts.append("</div>")  # .lg-caption

    html = "".join(parts)
    # data-sub-html 用にシングルクォートをエスケープ
    return html.replace("'", "&#39;")

# ==========================
#  ギャラリー生成
# ==========================
def generate_gallery(entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # alt ごとにグループ化（同じキノコ名で複数枚対応）
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e)

    group_links = " | ".join([f'<a href="{g}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px; text-align:center;'>{group_links}</div>"

    def safe_filename(name):
        name = re.sub(r'[:<>"|*?\\\\/\\r\\n]', '_', name)
        name = name.strip()
        if not name:
            name = "unnamed"
        return name

    # ---- 各キノコのページ ----
    for alt, items in grouped.items():
        html = f"<h2>{alt}</h2><div class='gallery'>"
        for item in items:
            src = item["src"]
            exif = item.get("exif") or {}
            thumb = src + "?width=300"

            sub_html = build_sub_html(alt, exif)

            html += (
                f"<a class='gallery-item' href='{src}' "
                f"data-exthumbimage='{thumb}' "
                f"data-sub-html='{sub_html}'>"
                f"<img src='{src}' alt='{alt}' loading='lazy'>"
                f"</a>"
            )

        html += "</div>"
        html += """
        <div style='margin-top:40px; text-align:center;'>
            <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """
        html += STYLE_TAG + LIGHTGALLERY_TAGS + SCRIPT_TAG

        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # ---- 五十音グループページ ----
    aiuo_dict = {k: [] for k in AIUO_GROUPS.keys()}
    for alt in grouped.keys():
        g = get_aiuo_group(alt)
        if g in aiuo_dict:
            aiuo_dict[g].append(alt)

    for g, names in aiuo_dict.items():
        html = f"<h2>{g}のキノコ</h2><ul>"
        for n in sorted(names):
            safe = safe_filename(n)
            html += f"<li><a href='{safe}.html'>{n}</a></li>"
        html += "</ul>"
        html += group_links_html
        html += STYLE_TAG + LIGHTGALLERY_TAGS + SCRIPT_TAG

        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # ---- index ----
    index = "<h2>五十音別分類</h2><ul>"
    for g in AIUO_GROUPS.keys():
        index += f"<li><a href='{safe_filename(g)}.html'>{g}</a></li>"
    index += "</ul>"
    index += STYLE_TAG + LIGHTGALLERY_TAGS + SCRIPT_TAG

    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index)

    print("✅ ギャラリーページ生成完了")

# ==========================
#  メイン
# ==========================
if __name__ == "__main__":
    fetch_hatena_articles_api()
    entries = fetch_images()
    if entries:
        generate_gallery(entries)
    else:
        print("⚠️ 画像が見つかりませんでした。")
