import os
import glob
import json
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import html
import piexif
from openai import OpenAI  # ★ GPT用
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import time

# ===========================
# OpenAI クライアント（15秒タイムアウト）
# ===========================
# OPENAI_API_KEY は環境変数から自動取得（GitHub Actions の env で渡す）
client = OpenAI(timeout=15)

# ===========================
# EXIF 文字クリーン関数
# ===========================
def clean_exif_str(s: str) -> str:
    if not s:
        return ""
    # NULL文字・文字化けっぽい文字を除去
    s = s.replace("\x00", "")
    s = re.sub(r"[�]+", "", s)
    return s.strip()


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

# ====== AI説明文キャッシュ設定 ======
DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")

# ====== はてな API エンドポイント ======
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

# ====== 共通スタイル（図鑑カード + Masonry） ======
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

/* Masonry ギャラリー */
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

/* 図鑑風 説明カード */
.info-card {
  background: radial-gradient(circle at top left, #fff7e6 0, #ffffff 45%, #ffffff 100%);
  border: 1px solid #e2dfd9;
  padding: 20px 22px;
  border-radius: 14px;
  box-shadow: 0 4px 10px rgba(0,0,0,0.08);
  max-width: 780px;
  margin: 0 auto 40px auto;
  line-height: 1.7;
  font-size: 0.96em;
  color: #444;
  position: relative;
}
.info-card::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.8);
  pointer-events: none;
}
.info-card h3 {
  text-align: center;
  margin-top: 0;
  margin-bottom: 14px;
  font-size: 1.5em;
  font-weight: 650;
  letter-spacing: 0.05em;
  color: #222;
}
.info-card p {
  margin: 0 0 10px 0;
}
</style>"""

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

      gallery.querySelectorAll("a.gallery-item").forEach((a) => {
        a.addEventListener("click", () => {
          const el = document.documentElement;
          if (el.requestFullscreen) el.requestFullscreen();
          else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
          else if (el.msRequestFullscreen) el.msRequestFullscreen();
        });
      });

      gallery.addEventListener("lgBeforeClose", () => {
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(()=>{});
        }
        window.parent.postMessage({ type: "lgClosed" }, "*");
      });

      document.addEventListener("fullscreenchange", () => {
        if (!document.fullscreenElement) {
          try {
            lg.closeGallery();
            window.parent.postMessage({ type: "lgClosed" }, "*");
          } catch(e) {}
        }
      });

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

    });
  }

  sendHeight();
  window.addEventListener("load", ()=>{ sendHeight(); setTimeout(sendHeight,800); setTimeout(sendHeight,2000); });
  window.addEventListener("message", e=>{ if(e.data?.type==="requestHeight") sendHeight(); });
  window.addEventListener("resize", sendHeight);
  new MutationObserver(sendHeight).observe(document.body,{childList:true,subtree:true});
});
</script>
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

    try:
        zero = exif_dict.get("0th", {})
        exif = exif_dict.get("Exif", {})

        model = zero.get(piexif.ImageIFD.Model, b"")
        if isinstance(model, bytes):
            model = clean_exif_str(model.decode(errors="ignore"))
        else:
            model = clean_exif_str(str(model))

        lens = exif.get(piexif.ExifIFD.LensModel, b"")
        if isinstance(lens, bytes):
            lens = clean_exif_str(lens.decode(errors="ignore"))
        else:
            lens = clean_exif_str(str(lens))

        if "IS" in lens:
            lens = lens.split("IS")[0] + "IS"

        iso = exif.get(piexif.ExifIFD.ISOSpeedRatings) or exif.get(piexif.ExifIFD.ISO)
        if isinstance(iso, (list, tuple)):
            iso = iso[0]
        iso_str = str(iso) if iso is not None else ""

        fnum = exif.get(piexif.ExifIFD.FNumber)
        f_str = ""
        fv = _rational_to_float(fnum)
        if fv:
            f_str = f"f/{fv:.1f}"

        exposure = exif.get(piexif.ExifIFD.ExposureTime)
        exposure_str = _exposure_to_str(exposure)

        focal = exif.get(piexif.ExifIFD.FocalLength)
        focal_str = ""
        fv2 = _rational_to_float(focal)
        if fv2:
            if abs(fv2 - round(fv2)) < 0.1:
                focal_str = f"{int(round(fv2))}mm"
            else:
                focal_str = f"{fv2:.1f}mm"

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

    except Exception:
        return {}

# ===========================
# EXIF キャッシュ構築
# ===========================
def build_exif_cache(entries, cache: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)

    all_srcs = sorted({e["src"] for e in entries})

    for src in all_srcs:

        # --- すでにキャッシュ済みならスキップ ---
        if src in cache:
            continue

        print(f"🔍 EXIF取得: {src}")

        try:
            # ★ 3秒タイムアウトに短縮
            r = requests.get(src, timeout=3)
            if r.status_code != 200:
                print(f"  ↪ HTTP {r.status_code} → 空データで続行")
                cache[src] = {}
                continue

            jpeg_bytes = r.content

            # ★ piexif.load が固まるケースに強制バリア
            try:
                exif_data = extract_exif_from_bytes(jpeg_bytes) or {}
                print(f"  ↪ EXIF取得OK: {exif_data}")
                cache[src] = exif_data
            except Exception as e:
                print(f"  ↪ EXIF読み取りエラー: {e} → 空データで続行")
                cache[src] = {}

        except Exception as e:
            print(f"  ↪ 取得エラー: {e} → 空データで続行")
            cache[src] = {}

    return cache

# ===========================
# AI 説明文キャッシュ
# ===========================
def load_description_cache():
    if not os.path.exists(DESC_CACHE_FILE):
        return {}
    try:
        with open(DESC_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_description_cache(cache: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def generate_description_via_gpt(name: str) -> str:
    """
    GPT 説明文生成（最大3回リトライ + 各10秒タイムアウト）
    """
    max_retry = 3
    timeout_sec = 10

    prompt = (
        "あなたは「キノコ専門フィールド図鑑の編集ライター」です。\n"
        "以下のキノコ名について、写真観察を前提にしたフィールド図鑑向けの説明文を作成してください。\n\n"
        "【トーン・文体】\n"
        "・専門的すぎず、一般向け図鑑として読みやすい文体にする\n"
        "・断定を避け、「〜ことが多い」「〜可能性がある」など観察ベースの表現を使う\n"
        "・名称に「?」「or」「仲間」「広義」などが含まれる場合は、同定が難しい種類として安全に説明する\n\n"
        "【内容に必ず含める要素】\n"
        "1. 形態の特徴（傘・柄・ひだ/管孔・?面の質感・色の変化など）\n"
        "2. 発生環境（どのような森・樹種・地面の状態などに出ることが多いか）\n"
        "3. 発生時期（おおまかな季節）\n"
        "4. 同定の注意点や、似たキノコとのざっくりした違い\n"
        "5. 写真映え・観察のポイント（どんなところを見ると楽しいか）\n"
        "6. 食毒に関して：外見からの判断は危険であるため、決して口にしないようにという安全な一文を入れる\n\n"
        "【曖昧名ルール】\n"
        "キノコ名に「?」「or」「仲間」「広義」が含まれる場合、\n"
        "最初に必ず「この名称は観察名として用いられるもので、外見だけでは確定同定が難しい種類です。」という一文を入れてください。\n\n"
        "【文字数】\n"
        "・全体でだいたい 300〜500文字程度に収める\n"
        "・2〜3段落に自然に分ける\n\n"
        "【禁止事項】\n"
        "・学名を勝手に決めない\n"
        "・食べられる／毒がある と断言しない\n"
        "・「写真を見て」など、実際には見ていないのに見たと書かない\n\n"
        f"キノコ名: {name}\n\n"
        "上記条件をすべて守って、日本語で説明文のみを出力してください。"
    )

    def call_openai():
        client = OpenAI()  # OPENAI_API_KEYは環境変数から自動
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )

    for attempt in range(1, max_retry + 1):
        try:
            print(f"🧠 説明文生成中（試行 {attempt}/{max_retry}）: {name}")

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_openai)
                res = future.result(timeout=timeout_sec)

            text = (res.choices[0].message.content or "").strip()
            if text:
                return text

        except FutureTimeout:
            print(f"⚠️ GPTタイムアウト: {name} → リトライ")
        except Exception as e:
            print(f"⚠️ GPT生成エラー: {name} → {e}")

        time.sleep(1)

    print(f"⚠️ GPT失敗: {name} → プレースホルダを返す")
    return f"{name} の説明文は準備中です。"

def get_ai_description(name: str, desc_cache: dict) -> str:
    """
    説明文キャッシュ → GPT の順で取得。
    1種につき 1回だけ GPT を叩き、結果は JSON に保存。
    """
    key = name.strip()
    if key in desc_cache:
        return desc_cache[key]

    text = generate_description_via_gpt(key)
    desc_cache[key] = text
    save_description_cache(desc_cache)
    return text


# ===========================
# はてな API から全記事取得
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
# HTML から画像と alt 抽出
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
# EXIF → caption HTML（2行で中央揃え）
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

    html_block = (
        "<div style='text-align:center;'>"
        f"<div style='font-weight:bold; font-size:1.2em; margin-bottom:6px;'>{title}</div>"
        f"<div style='font-size:0.9em; line-height:1.4;'>{exif_line}</div>"
        "</div>"
    )

    return html.escape(html_block, quote=True)


# ===========================
# ギャラリー生成
# ===========================
def generate_gallery(entries, exif_cache, desc_cache):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    group_links = " | ".join([f'<a href="{g}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px; text-align:center;'>{group_links}</div>"

    def safe_filename(name):
        name = re.sub(r'[:<>"|*?/\\\r\n]', '_', name)
        name = name.strip()
        if not name:
            name = "unnamed"
        return name

    # ---- 各キノコページ ----
    for alt, imgs in grouped.items():
        html_parts = []

        # ★ 図鑑スタイル説明カード（GPT＋キャッシュ）
        ai_text = get_ai_description(alt, desc_cache)
        paragraphs = [p.strip() for p in ai_text.split("\n") if p.strip()]

        body_html = ""
        for p in paragraphs:
            body_html += f"<p>{html.escape(p)}</p>"

        card_html = (
            "<div class=\"info-card\">"
            f"<h3>{html.escape(alt)}</h3>"
            f"{body_html}"
            "</div>"
        )
        html_parts.append(card_html)

        # ギャラリー本体
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

        # 戻るリンク
        html_parts.append("""
        <div style='margin-top:40px; text-align:center;'>
            <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """)

        # 共通タグ
        html_parts.append(STYLE_TAG)
        html_parts.append(LIGHTGALLERY_TAGS)
        html_parts.append(SCRIPT_TAG)

        page_html = "".join(html_parts)

        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    # ---- 五十音グループページ ----
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
        # EXIF
        exif_cache = load_exif_cache()
        exif_cache = build_exif_cache(entries, exif_cache)
        save_exif_cache(exif_cache)

        # 説明文キャッシュ
        desc_cache = load_description_cache()

        # ギャラリー生成
        generate_gallery(entries, exif_cache, desc_cache)
    else:
        print("⚠️ 画像が見つかりませんでした。")
