import os
import glob
import json
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import html
import piexif
from openai import OpenAI
import time

# ======================================================
# 🧠 OpenAI クライアント（安定版 / timeout=20秒）
# ======================================================
# OPENAI_API_KEY は環境変数から自動取得（GitHub Actions もOK）
client = OpenAI(timeout=20)

# ===========================
# EXIF 文字クリーン関数
# ===========================
def clean_exif_str(s: str) -> str:
    if not s:
        return ""
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

# ====== EXIF キャッシュ ======
CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "exif-cache.json")

# ====== 説明文キャッシュ ======
DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")

# ====== はてな API ======
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

# ------------------------------------------------------
# CSS & JS（そのまま／あなたのコードと同じ）
# ------------------------------------------------------
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
...
</style>"""

LIGHTGALLERY_TAGS = """
<link rel="stylesheet" href="./lightgallery/lightgallery-bundle.min.css">
<link rel="stylesheet" href="./lightgallery/lg-thumbnail.css">
<script src="./lightgallery/lightgallery.min.js"></script>
<script src="./lightgallery/lg-zoom.min.js"></script>
<script src="./lightgallery/lg-thumbnail.min.js"></script>
"""

SCRIPT_TAG = """<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>
<script>
...
</script>
"""

# ===========================
# EXIF キャッシュ load/save
# ===========================
def load_exif_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

def save_exif_cache(cache: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ===========================
# EXIF 抽出
# ===========================
def extract_exif_from_bytes(jpeg_bytes: bytes):
    try:
        exif_dict = piexif.load(jpeg_bytes)
    except:
        return {}

    try:
        zero = exif_dict.get("0th", {})
        exif = exif_dict.get("Exif", {})

        # ---- Camera Model ----
        model = zero.get(piexif.ImageIFD.Model, b"")
        model = clean_exif_str(model.decode(errors="ignore")) if isinstance(model, bytes) else ""

        # ---- Lens ----
        lens = exif.get(piexif.ExifIFD.LensModel, b"")
        lens = clean_exif_str(lens.decode(errors="ignore")) if isinstance(lens, bytes) else ""

        if "IS" in lens:
            lens = lens.split("IS")[0] + "IS"

        # ---- ISO ----
        iso = exif.get(piexif.ExifIFD.ISOSpeedRatings)
        if isinstance(iso, (list, tuple)):
            iso = iso[0]
        iso_str = str(iso) if iso else ""

        # ---- F値 ----
        fnum = exif.get(piexif.ExifIFD.FNumber)
        f_str = ""
        if fnum and isinstance(fnum, tuple) and fnum[1]:
            f_str = f"f/{(fnum[0] / fnum[1]):.1f}"

        # ---- 露出 ----
        exposure = exif.get(piexif.ExifIFD.ExposureTime)
        exposure_str = ""
        if exposure and isinstance(exposure, tuple) and exposure[1]:
            exposure_str = f"{exposure[0]}/{exposure[1]}"

        # ---- 焦点距離 ----
        focal = exif.get(piexif.ExifIFD.FocalLength)
        focal_str = ""
        if focal and isinstance(focal, tuple) and focal[1]:
            fv = focal[0] / focal[1]
            focal_str = f"{int(round(fv))}mm" if abs(fv - round(fv)) < 0.1 else f"{fv:.1f}mm"

        # ---- 日付 ----
        dt = exif.get(piexif.ExifIFD.DateTimeOriginal, b"")
        dt = dt.decode(errors="ignore") if isinstance(dt, bytes) else ""
        date_str = dt.split(" ")[0].replace(":", "/") if dt else ""

        return {
            "model": model,
            "lens": lens,
            "iso": iso_str,
            "f": f_str,
            "exposure": exposure_str,
            "focal": focal_str,
            "date": date_str,
        }

    except:
        return {}

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

        try:
            r = requests.get(src, timeout=3)
            if r.status_code != 200:
                print(f"  ↪ HTTP {r.status_code} → 空データ")
                cache[src] = {}
                continue

            try:
                exif_data = extract_exif_from_bytes(r.content) or {}
                print(f"  ↪ EXIF取得OK: {exif_data}")
                cache[src] = exif_data
            except Exception as e:
                print(f"  ↪ EXIFエラー: {e} → 空データ")
                cache[src] = {}

        except Exception as e:
            print(f"  ↪ 取得失敗: {e} → 空データ")
            cache[src] = {}

    return cache


# ===========================
# ⭐ 説明文キャッシュ load/save
# ===========================
def load_description_cache():
    if not os.path.exists(DESC_CACHE_FILE):
        return {}
    try:
        with open(DESC_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

def save_description_cache(cache: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ===========================
# ⭐ GPT 説明文生成（安定版）
# ===========================
def generate_description_via_gpt(name: str) -> str:
    max_retry = 3
    timeout_sec = 15

    prompt = f"""
あなたは「キノコ専門フィールド図鑑の編集ライター」です。
以下のキノコ名について、一般向け図鑑として安全で読みやすい説明を作成してください。

キノコ名: {name}

【条件】
・外見から断定しない表現（〜ことが多い等）
・発生環境・季節・観察ポイント・似た種の注意
・食毒は絶対断言しない。安全注意を入れる
・300〜500文字
・2〜3段落に分ける
""".strip()

    def call_openai():
        # 最新API（Responses）を使用
        return client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
        )

    # ★ Responses API のテキストを安全に抽出する関数
    def extract_text(res):
        try:
            return res.output[0].content[0].text
        except:
            try:
                return res.output_text
            except:
                return ""

    for attempt in range(1, max_retry + 1):
        try:
            print(f"🧠 説明文生成中（試行 {attempt}/{max_retry}）: {name}")

            # タイムアウトガード
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_openai)
                res = future.result(timeout=timeout_sec)

            text = extract_text(res).strip()
            if text:
                return text

        except FutureTimeout:
            print(f"⚠️ GPTタイムアウト: {name} → 再試行")
        except Exception as e:
            print(f"⚠️ GPTエラー: {name}: {e}")

        time.sleep(1)

    print(f"⚠️ GPT失敗: {name} → プレースホルダ返却")
    return f"{name} の説明文は準備中です。"

# ===========================
# ⭐ 説明文キャッシュ → GPT（安定処理）
# ===========================
def get_ai_description(name: str, desc_cache: dict) -> str:
    """
    ・すでにキャッシュにあれば即返す（API無料）
    ・なければ GPT 生成 → キャッシュ保存
    """
    key = name.strip()
    if key in desc_cache:
        return desc_cache[key]

    text = generate_description_via_gpt(key)
    desc_cache[key] = text
    save_description_cache(desc_cache)
    return text

# ===========================
# はてなブログ API → 全記事取得
# ===========================
def fetch_hatena_articles_api():
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    print("📡 はてなブログAPI取得中…")
    url = ATOM_ENDPOINT
    count = 0

    while url:
        print(f"🔗 Fetch: {url}")
        r = requests.get(url, auth=AUTH, headers=HEADERS)
        if r.status_code != 200:
            raise RuntimeError(f"❌ API失敗: {r.status_code} {r.text}")

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
            print(f"  → 保存: {filename}")

        count += len(entries)
        next_link = root.find("atom:link[@rel='next']", ns)
        url = next_link.attrib["href"] if next_link is not None else None

    print(f"📦 合計 {count} 件の記事を保存完了")


# ===========================
# HTML → 画像 + alt 抽出
# ===========================
def fetch_images():
    print("📂 HTML→画像抽出中…")
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
            if any(re.search(p, iframe.get("title", "")) for p in exclude_patterns):
                iframe.decompose()

        for a in body_div.find_all("a"):
            if any(re.search(p, a.get_text(strip=True)) for p in exclude_patterns):
                a.decompose()

        for img in body_div.find_all("img"):
            alt = (img.get("alt") or "").strip()
            src = img.get("src")
            if not alt or not src:
                continue
            if any(re.search(p, alt) for p in exclude_patterns):
                continue

            entries.append({"alt": alt, "src": src})

    print(f"🧩 抽出画像数: {len(entries)}")
    return entries


# ===========================
# 五十音分類
# ===========================
def get_aiuo_group(name):
    if not name:
        return "その他"
    first = name[0]
    for g, chars in AIUO_GROUPS.items():
        if first in chars:
            return g
    return "その他"


# ===========================
# EXIF → caption HTML
# ===========================
def build_caption_html(alt, exif):
    title = html.escape(alt)

    parts = []
    if exif.get("model"):
        parts.append(f"カメラ：{html.escape(exif['model'])}")
    if exif.get("lens"):
        parts.append(f"レンズ：{html.escape(exif['lens'])}")
    if exif.get("iso"):
        parts.append(f"ISO：{html.escape(exif['iso'])}")
    if exif.get("f"):
        parts.append(f"絞り：{html.escape(exif['f'])}")
    if exif.get("exposure"):
        parts.append(f"シャッター速度：{html.escape(exif['exposure'])}")
    if exif.get("focal"):
        parts.append(f"焦点距離：{html.escape(exif['focal'])}")
    if exif.get("date"):
        parts.append(f"撮影日：{html.escape(exif['date'])}")

    exif_line = " | ".join(parts)

    block = (
        "<div style='text-align:center;'>"
        f"<div style='font-weight:bold; font-size:1.2em; margin-bottom:6px;'>{title}</div>"
        f"<div style='font-size:0.9em;'>{exif_line}</div>"
        "</div>"
    )

    return html.escape(block, quote=True)


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
        name = re.sub(r'[:<>"|*?/\\\r\n]', "_", name).strip()
        return name if name else "unnamed"

    # ---- 各キノコページ ----
    for alt, imgs in grouped.items():
        html_parts = []

        # ⭐ GPT説明文（キャッシュ優先）
        ai_text = get_ai_description(alt, desc_cache)
        body_html = "".join(f"<p>{html.escape(p)}</p>" for p in ai_text.split("\n") if p.strip())

        card_html = (
            "<div class='info-card'>"
            f"<h3>{html.escape(alt)}</h3>"
            f"{body_html}"
            "</div>"
        )
        html_parts.append(card_html)

        # 画像ギャラリー
        html_parts.append("<div class='gallery'>")
        for src in imgs:
            caption_attr = build_caption_html(alt, exif_cache.get(src, {}))
            thumb = src + "?width=300"

            html_parts.append(
                f'<a class="gallery-item" href="{src}" '
                f'data-exthumbimage="{thumb}" '
                f'data-sub-html="{caption_attr}">'
                f'<img src="{src}" alt="{html.escape(alt)}" loading="lazy">'
                "</a>"
            )
        html_parts.append("</div>")

        html_parts.append("""
        <div style='margin-top:40px;text-align:center;'>
            <a href='javascript:history.back()' style='color:#007acc;'>← 戻る</a>
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
    aiuo_dict = {k: [] for k in AIUO_GROUPS}
    for alt in grouped:
        g = get_aiuo_group(alt)
        aiuo_dict[g].append(alt)

    for g, names in aiuo_dict.items():
        html_parts = [f"<h2>{g}のキノコ</h2><ul>"]
        for n in sorted(names):
            html_parts.append(f'<li><a href="{safe_filename(n)}.html">{html.escape(n)}</a></li>')
        html_parts.append("</ul>")
        html_parts.append(group_links_html)
        html_parts.append(STYLE_TAG)
        html_parts.append(LIGHTGALLERY_TAGS)
        html_parts.append(SCRIPT_TAG)

        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write("".join(html_parts))

    # ---- index ----
    index_parts = ["<h2>五十音分類</h2><ul>"]
    for g in AIUO_GROUPS:
        index_parts.append(f'<li><a href="{safe_filename(g)}.html">{g}</a></li>')
    index_parts.append("</ul>")
    index_parts.append(STYLE_TAG)
    index_parts.append(LIGHTGALLERY_TAGS)
    index_parts.append(SCRIPT_TAG)

    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write("".join(index_parts))

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

        desc_cache = load_description_cache()

        generate_gallery(entries, exif_cache, desc_cache)
    else:
        print("⚠️ 画像が見つかりませんでした。")
