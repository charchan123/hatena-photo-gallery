import os
import glob
import json
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import html
import piexif

# ===========================
# 追加：EXIF文字クリーン関数
# ===========================
def clean_exif_str(s):
    if not s:
        return ""
    s = s.replace("\x00", "")              # NULL文字除去
    s = re.sub(r"[�]+", "", s)             # 文字化け除去
    s = s.strip()
    return s

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

# ====== EXIF キャッシュ設定 ======
CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "exif-cache.json")

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

# ====== 共通スタイル（＋説明カードCSS追加） ======
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
</style>

<style>
/* LightGallery と同じスタイルのカメラアイコン */
.lg-exif-toggle.lg-icon::after {
  content: "";
  width: 22px;
  height: 22px;
  display: block;

  /* Camera の SVG（LightGallery と同じ白い線）*/
  mask: url("data:image/svg+xml,%3Csvg width='24' height='24' stroke='white' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3l2-3h8l2 3h3a2 2 0 0 1 2 2z'/%3E%3Ccircle cx='12' cy='13' r='4'/%3E%3C/svg%3E") no-repeat center;
  background-color: white;
}
</style>
"""

# ====== LightGallery 読み込みタグ ======
LIGHTGALLERY_TAGS = """
<link rel="stylesheet" href="./lightgallery/lightgallery-bundle.min.css">
<link rel="stylesheet" href="./lightgallery/lg-thumbnail.css">

<script src="./lightgallery/lightgallery.min.js"></script>
<script src="./lightgallery/lg-zoom.min.js"></script>
<script src="./lightgallery/lg-thumbnail.min.js"></script>
"""

# ====== LightGallery スクリプト ======
SCRIPT_TAG = """<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>
<script>
document.addEventListener("DOMContentLoaded", () => {

  function sendHeight() {
    const height = document.documentElement.scrollHeight;
    window.parent.postMessage({ type:"setHeight", height }, "*");
  }

  const gallery = document.querySelector(".gallery");
  if (gallery) {
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
      gallery.style.visibility="visible";
      sendHeight();

      const lg = lightGallery(gallery, {
        selector: 'a.gallery-item',
        plugins: [lgZoom, lgThumbnail],
        speed: 400,
        download: false,
        zoom: true,
        thumbnail: true
      });

      /* ==================================
         ① サムネイルクリック時に
            強制フルスクリーン発動
      =================================== */
      gallery.querySelectorAll("a.gallery-item").forEach((a) => {
        a.addEventListener("click", () => {
          const el = document.documentElement;

          if (el.requestFullscreen) el.requestFullscreen();
          else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
          else if (el.msRequestFullscreen) el.msRequestFullscreen();
        });
      });

      /* ==================================
         ② v2イベント（閉じる前）
      =================================== */
      gallery.addEventListener("lgBeforeClose", () => {
        console.log("📤 子：LG before close 発火");
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(()=>{});
        }
        window.parent.postMessage({ type: "lgClosed" }, "*");
      });

      /* ==================================
         ③ ESC → フルスクリーン解除 → 親へ通知
      =================================== */
      document.addEventListener("fullscreenchange", () => {
        if (!document.fullscreenElement) {
          console.log("📤 子：fullscreenchange発火 → 親に lgClosed を送信");
          try {
            lg.closeGallery();
            window.parent.postMessage({ type: "lgClosed" }, "*");
          } catch(e) {}
        }
      });
    });
  }

  /* ===========================================
       ★ クリック判定は gallery の外へ移動
       → 全ページで scrollToTitle を送信できる
  ============================================ */
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;

    const txt = a.textContent || "";
    const href = a.getAttribute("href") || "";

    console.log("[iframe] click anchor:", { text: txt, href });

    // 1) キノコ名ページ (xxx.html)
    if (href.endsWith(".html")) {
      console.log("[iframe] send scrollToTitle (html link)");
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }

    // 2) あ行〜わ行
    if (/^(あ行|か行|さ行|た行|な行|は行|ま行|や行|ら行|わ行)$/.test(txt)) {
      console.log("[iframe] send scrollToTitle (aiuo link)");
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }

    // 3) ← 戻る
    if (/戻る/.test(txt)) {
      console.log("[iframe] send scrollToTitle (back)");
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }
  });

  sendHeight();
  window.addEventListener("load", ()=>{ sendHeight(); setTimeout(sendHeight,800); setTimeout(sendHeight,2000); });
  window.addEventListener("message", e=>{ if(e.data?.type==="requestHeight") sendHeight(); });
  window.addEventListener("resize", sendHeight);
  new MutationObserver(sendHeight).observe(document.body,{childList:true,subtree:true});

});

</script>

<!-- ▼▼▼ 追加スクリプト：EXIF ON/OFF 切替 ▼▼▼ -->
<script>
(function() {

  // LightGallery の DOM が準備できるまで待つ
  const ready = setInterval(() => {
    const toolbar = document.querySelector(".lg-toolbar");
    const subHtml = document.querySelector(".lg-sub-html");
    if (!toolbar || !subHtml) return;

    clearInterval(ready);

    // =============== ① カメラアイコン追加（正しくツールバーに並べる） ===================
    const btn = document.createElement("button");
    btn.className = "lg-icon lg-exif-toggle";
    btn.innerHTML = "📷";  // ← アイコン
    btn.style.cssText = `
      font-size: 22px;
      background: none;
      border: none;
      cursor: pointer;
      margin-left: 8px;
    `;
    toolbar.append(btn);

    // =============== ② EXIF の初期状態（LocalStorage） ===================
    let visible = localStorage.getItem("mushroom_exif_visible") !== "0";

    function applyExif(show) {
      const htmls = document.querySelectorAll(".lg-sub-html");
      htmls.forEach(el => {
        el.style.display = show ? "block" : "none";
      });

      // 重要！ LightGallery にレイアウト再計算を要求
      const evt = new Event("resize");
      window.dispatchEvent(evt);

      localStorage.setItem("mushroom_exif_visible", show ? "1" : "0");
    }

    applyExif(visible);

    // =============== ③ カメラアイコンクリックで EXIF 切替 ===================
    btn.addEventListener("click", () => {
      visible = !visible;
      applyExif(visible);
    });

    // スライド変更時にも適用
    document.addEventListener("lgAfterSlide", () => {
      applyExif(visible);
    });

    // =============== ④ フルスクリーン解除後の再レイアウト対策 ===================
    document.addEventListener("fullscreenchange", () => {
      setTimeout(() => {
        const evt2 = new Event("resize");
        window.dispatchEvent(evt2);
      }, 300);
    });

  }, 300);

})();
</script>
<!-- ▲▲▲ 追加スクリプトここまで ▲▲▲ -->
"""

# ===========================
# EXIF キャッシュ
# ===========================
def load_exif_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}

def save_exif_cache(cache: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def _rational_to_float(val):
    try:
        if isinstance(val, tuple) and len(val) == 2 and val[1]:
            return val[0] / val[1]
    except Exception:
        pass
    try:
        return float(val)
    except Exception:
        return None

def _exposure_to_str(val):
    if isinstance(val, tuple) and len(val) == 2 and val[1]:
        num, den = val
        return f"{num}/{den}"
    try:
        return str(val)
    except Exception:
        return ""

# ===========================
# EXIF 抽出
# ===========================
def extract_exif_from_bytes(jpeg_bytes: bytes):
    try:
        exif_dict = piexif.load(jpeg_bytes)
    except Exception:
        return {}

    zero = exif_dict.get("0th", {})
    exif = exif_dict.get("Exif", {})

    # Model
    model = zero.get(piexif.ImageIFD.Model, b"")
    if isinstance(model, bytes):
        model = clean_exif_str(model.decode(errors="ignore"))
    else:
        model = clean_exif_str(str(model))

    # LensModel
    lens = exif.get(piexif.ExifIFD.LensModel, b"")
    if isinstance(lens, bytes):
        lens = clean_exif_str(lens.decode(errors="ignore"))
    else:
        lens = clean_exif_str(str(lens))

    if "IS" in lens:
        lens = lens.split("IS")[0] + "IS"

    # ISO
    iso = exif.get(piexif.ExifIFD.ISOSpeedRatings) or exif.get(piexif.ExifIFD.ISO)
    if isinstance(iso, (list, tuple)):
        iso = iso[0]
    iso_str = str(iso) if iso is not None else ""

    # F値
    fnum = exif.get(piexif.ExifIFD.FNumber)
    f_str = ""
    fv = _rational_to_float(fnum)
    if fv:
        f_str = f"f/{fv:.1f}"

    # シャッタースピード
    exposure = exif.get(piexif.ExifIFD.ExposureTime)
    exposure_str = _exposure_to_str(exposure)

    # 焦点距離
    focal = exif.get(piexif.ExifIFD.FocalLength)
    focal_str = ""
    fv2 = _rational_to_float(focal)
    if fv2:
        if abs(fv2 - round(fv2)) < 0.1:
            focal_str = f"{int(round(fv2))}mm"
        else:
            focal_str = f"{fv2:.1f}mm"

    # 日付
    dt = exif.get(piexif.ExifIFD.DateTimeOriginal, b"")
    if isinstance(dt, bytes):
        dt = dt.decode(errors="ignore")
    date_str = ""
    if dt:
        parts = dt.split(" ")
        if parts:
            date_str = parts[0].replace(":", "/")

    return {
        "model": model or "",
        "lens": lens or "",
        "iso": iso_str or "",
        "f": f_str or "",
        "exposure": exposure_str or "",
        "focal": focal_str or "",
        "date": date_str or "",
    }

# ===========================
# EXIF キャッシュ構築
# ===========================
def build_exif_cache(entries, cache: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)

    all_srcs = sorted({e["src"] for e in entries})

    for src in all_srcs:
        if src in cache:
            continue

        print(f"🔍 EXIF取得: {src}")
        exif_data = {}
        try:
            r = requests.get(src, timeout=10)
            if r.status_code == 200:
                exif_data = extract_exif_from_bytes(r.content) or {}
                print(f"  ↪ EXIF取得OK: {exif_data}")
            else:
                print(f"  ↪ HTTP {r.status_code} → 空データとして保存")
        except Exception as e:
            print(f"  ↪ 取得エラー: {e} → 空データとして保存")

        cache[src] = exif_data

    return cache

# ===========================
# はてなAPI 全記事取得
# ===========================
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

# ===========================
# HTML から画像抽出
# ===========================
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

            entries.append({"alt": alt, "src": src})

    print(f"🧩 画像検出数: {len(entries)} 枚")
    return entries

# ===========================
# 五十音分類
# ===========================
def get_aiuo_group(name):
    if not name:
        return "その他"
    first = name[0]
    for group, chars in AIUO_GROUPS.items():
        if first in chars:
            return group
    return "その他"

# ===========================
# EXIF → caption HTML
# ===========================
def build_caption_html(alt, exif: dict):
    title = html.escape(alt)

    model = exif.get("model") or ""
    lens = exif.get("lens") or ""
    iso = exif.get("iso") or ""
    f = exif.get("f") or ""
    exposure = exif.get("exposure") or ""
    focal = exif.get("focal") or ""
    date = exif.get("date") or ""

    parts = []
    if model:
        parts.append(f"カメラ：{html.escape(model)}")
    if lens:
        parts.append(f"レンズ：{html.escape(lens)}")
    if iso:
        parts.append(f"ISO：{html.escape(iso)}")
    if f:
        parts.append(f"絞り：{html.escape(f)}")
    if exposure:
        parts.append(f"シャッター速度：{html.escape(exposure)}")
    if focal:
        parts.append(f"焦点距離：{html.escape(focal)}")
    if date:
        parts.append(f"撮影日：{html.escape(date)}")

    exif_line = " | ".join(parts)

    html_block = f"""
    <div style='text-align:center;'>
        <div style='font-weight:bold; font-size:1.2em; margin-bottom:6px;'>{title}</div>
        <div style='font-size:0.9em; line-height:1.4;'>{exif_line}</div>
    </div>
    """

    return html.escape(html_block, quote=True)

# ===========================
# ギャラリー生成
# ===========================
def generate_gallery(entries, exif_cache):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    group_links = " | ".join([f'<a href="{g}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px; text-align:center;'>{group_links}</div>"

    def safe_filename(name):
        name = re.sub(r'[:<>\"|*?\\\\/\\r\\n]', '_', name)
        name = name.strip()
        if not name:
            name = "unnamed"
        return name

    # ---- 各キノコページ ----
    for alt, imgs in grouped.items():
        html_parts = []

        # ====== ギャラリー ======
        html_parts.append("<div class='gallery'>")
        for src in imgs:
            thumb = src + "?width=300"
            exif = exif_cache.get(src, {}) or {}
            caption_attr = build_caption_html(alt, exif)

            html_parts.append(
                f'<a class="gallery-item" href="{src}" '
                f'data-exthumbimage="{thumb}" '
                f'data-sub-html="{caption_attr}">'
                f'<img src="{src}" alt="{html.escape(alt)}" loading="lazy">'
                f'</a>'
            )

        html_parts.append("</div>")

        html_parts.append("""
        <div style='margin-top:40px; text-align:center;'>
            <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """)

        html_parts.append(STYLE_TAG)
        html_parts.append(LIGHTGALLERY_TAGS)
        html_parts.append(SCRIPT_TAG)

        page_html = "".join(html_parts)

        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    # ---- 五十音ページ ----
    aiuo_dict = {k: [] for k in AIUO_GROUPS.keys()}
    for alt in grouped.keys():
        g = get_aiuo_group(alt)
        if g in aiuo_dict:
            aiuo_dict[g].append(alt)

    for g, names in aiuo_dict.items():
        html_parts = []
        html_parts.append(f"<h2>{g}のキノコ</h2><ul>")
        for n in sorted(names):
            safe = safe_filename(n)
            html_parts.append(f'<li><a href="{safe}.html">{html.escape(n)}</a></li>')
        html_parts.append("</ul>")
        html_parts.append(group_links_html)
        html_parts.append(STYLE_TAG)
        html_parts.append(LIGHTGALLERY_TAGS)
        html_parts.append(SCRIPT_TAG)

        page_html = "".join(html_parts)

        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    # ---- index ----
    index_parts = []
    index_parts.append("<h2>五十音別分類</h2><ul>")
    for g in AIUO_GROUPS.keys():
        index_parts.append(f'<li><a href="{safe_filename(g)}.html">{g}</a></li>')
    index_parts.append("</ul>")
    index_parts.append(STYLE_TAG)
    index_parts.append(LIGHTGALLERY_TAGS)
    index_parts.append(SCRIPT_TAG)

    index_html = "".join(index_parts)

    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    print("✅ ギャラリーページ生成完了")

# ===========================
# メイン
# ===========================
if __name__ == "__main__":
    fetch_hatena_articles_api()
    entries = fetch_images()
    if entries:
        exif_cache = load_exif_cache()
        exif_cache = build_exif_cache(entries, exif_cache)
        save_exif_cache(exif_cache)
        generate_gallery(entries, exif_cache)
    else:
        print("⚠️ 画像が見つかりませんでした。")
