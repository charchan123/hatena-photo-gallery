import os
import json
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import html
import piexif
import shutil
import unicodedata

# ===========================
# 珍しい / 人気キノコリスト（手動）
# ===========================
RARITY_LIST = [
    "センニンタケ",
]

POPULAR_LIST = [
    "ベニテングタケ",
    "タマゴタケ",
    "シイタケ",
]

# ===========================
# safe_filename
# ===========================
def safe_filename(name):
    name = re.sub(r'[:<>\"|*?\\/\r\n]', '_', name)
    name = name.strip()
    if not name:
        name = "unnamed"
    return name

# ===========================
# EXIF文字クリーン
# ===========================
def clean_exif_str(s):
    if not s:
        return ""
    s = s.replace("\x00", "")
    s = re.sub(r"[�]+", "", s)
    return s.strip()

# ===========================
# カメラ名正規化
# ===========================
def normalize_model(model: str) -> str:
    if not model:
        return ""
    m = model.strip()
    if m.startswith("Canon "):
        m = m[len("Canon "):]
    return m

# ====== 設定 ======
HATENA_USER = os.getenv("HATENA_USER")
HATENA_BLOG_ID = os.getenv("HATENA_BLOG_ID")
HATENA_API_KEY = os.getenv("HATENA_API_KEY")

ARTICLES_DIR = "articles"
OUTPUT_DIR = "output"
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# ====== EXIF キャッシュ設定 ======
CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "exif-cache.json")
SHADOW_METADATA_FILE = os.path.join(CACHE_DIR, "phase3-shadow-metadata.json")

SHADOW_EXCLUDE_PATTERNS = [
    r'はてなブックマーク',
    r'^\d{4}年',
    r'^この記事をはてなブックマークに追加$',
    r'^ワ行$',
    r'キノコと田舎遊び',
]

SUBJECT_BLOCK_TAGS = ("p", "h1", "h2", "h3", "h4", "h5", "h6")
SUBJECT_LABEL_STOPWORDS = {"幼菌", "傘の裏"}

# ====== API ======
ATOM_ENDPOINT = f"https://blog.hatena.ne.jp/{HATENA_USER}/{HATENA_BLOG_ID}/atom/entry"
AUTH = (HATENA_USER, HATENA_API_KEY)
HEADERS = {}

AIUO_GROUPS = {
    "あ行": list("あいうえおアイウエオゔヴ"),
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

VOICED_KANA_TO_SEION = str.maketrans(
    "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽゔ"
    "ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポヴ",
    "かきくけこさしすせそたちつてとはひふへほはひふへほう"
    "カキクケコサシスセソタチツテトハヒフヘホハヒフヘホウ",
)


def normalize_kana_initial(name):
    """Return the first kana normalized to its unvoiced gojuon equivalent."""
    if not isinstance(name, str) or not name:
        return ""
    return unicodedata.normalize("NFKC", name)[0].translate(VOICED_KANA_TO_SEION)


def normalize_japanese_search(value):
    """Build the same hiragana search key used by the browser UI."""
    normalized = unicodedata.normalize("NFKC", value or "").lower()
    return "".join(
        chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char
        for char in normalized
    )

# ====== 共通スタイル（EXIF gap レイアウト採用版） ======
STYLE_TAG = '<link rel="stylesheet" href="assets/gallery.css">'

# ====== LightGallery 読み込みタグ ======
LIGHTGALLERY_TAGS = """
<link rel="stylesheet" 
      href="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/css/lightgallery-bundle.min.css">

<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/lightgallery.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/zoom/lg-zoom.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/thumbnail/lg-thumbnail.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/autoplay/lg-autoplay.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/share/lg-share.min.js"></script>
"""

# ====== LightGallery スクリプト ======
SCRIPT_TAG = """<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>
<script src="assets/gallery.js"></script>"""


def copy_shared_assets():
    """Copy the versioned gallery assets into the Pages output directory."""
    output_assets_dir = os.path.join(OUTPUT_DIR, "assets")
    os.makedirs(output_assets_dir, exist_ok=True)

    for filename in ("gallery.css", "gallery.js"):
        shutil.copy2(
            os.path.join(ASSETS_DIR, filename),
            os.path.join(output_assets_dir, filename),
        )

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
    model = normalize_model(model)

    # LensModel
    lens = exif.get(piexif.ExifIFD.LensModel, b"")
    if isinstance(lens, bytes):
        lens = clean_exif_str(lens.decode(errors="ignore"))
    else:
        lens = clean_exif_str(str(lens))

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

    # シャッター速度
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
    hits = 0
    fetched = 0
    failed = 0

    for src in all_srcs:
        if src in cache:
            hits += 1
            continue

        print(f"🔍 EXIF取得: {src}")
        try:
            r = requests.get(src, timeout=10)
            if r.status_code == 200:
                exif_data = extract_exif_from_bytes(r.content) or {}
                cache[src] = exif_data
                fetched += 1
                print(f"  ↪ EXIF取得OK: {exif_data}")
            else:
                failed += 1
                print(f"  ↪ HTTP {r.status_code} → キャッシュせず次回再試行")
        except Exception as e:
            failed += 1
            print(f"  ↪ 取得エラー: {e} → キャッシュせず次回再試行")

    print("EXIF cache summary:")
    print(f"total={len(all_srcs)}")
    print(f"hits={hits}")
    print(f"fetched={fetched}")
    print(f"failed={failed}")

    return cache

# ===========================
# EXIF → caption HTML（gap方式・日付統合）
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

    # 2行目：カメラ名 / レンズ名
    middle_parts = []
    if model:
        middle_parts.append(model)
    if lens:
        middle_parts.append(lens)
    middle_html = " / ".join(middle_parts)

    # 3行目：焦点距離 / F値 / SS / ISO / 日付（gap方式）
    bottom_spans = []

    if focal:
        bottom_spans.append(f"<span>{html.escape(focal)}</span>")
    if f:
        bottom_spans.append(f"<span>{html.escape(f)}</span>")
    if exposure:
        exp_str = exposure if exposure.endswith("s") else f"{exposure}s"
        bottom_spans.append(f"<span>{html.escape(exp_str)}</span>")
    if iso:
        bottom_spans.append(f"<span>ISO{html.escape(iso)}</span>")
    if date:
        bottom_spans.append(f"<span>{html.escape(date)}</span>")

    bottom_html = ""
    if bottom_spans:
        bottom_html = f"<div class='exif-bottom-row'>{''.join(bottom_spans)}</div>"

    html_block = "<div class='exif-wrap'>"
    html_block += f"<div class='exif-title'>{title}</div>"

    if middle_html:
        html_block += f"<div class='exif-middle'>{html.escape(middle_html)}</div>"

    if bottom_html:
        html_block += bottom_html

    html_block += "</div>"

    return html.escape(html_block, quote=True)

# ===========================
# はてなAPI 全記事取得
# ===========================
def fetch_hatena_articles_api():
    if not all([HATENA_USER, HATENA_BLOG_ID, HATENA_API_KEY]):
        raise EnvironmentError(
            "環境変数 HATENA_USER / HATENA_BLOG_ID / HATENA_API_KEY が未設定です。"
        )

    os.makedirs(ARTICLES_DIR, exist_ok=True)
    print("📡 はてなブログAPIから全記事取得中…")
    url = ATOM_ENDPOINT
    count = 0
    article_files = []
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
            article_files.append(filename)
            print(f"✅ 保存完了: {filename}")

        count += len(entries)
        next_link = root.find("atom:link[@rel='next']", ns)
        url = next_link.attrib["href"] if next_link is not None else None

    print(f"📦 合計 {count} 件の記事を保存しました。")
    return article_files

# ===========================
# HTML から画像抽出
# ===========================
def fetch_images(article_files):
    """明示的に指定されたAPI記事本文だけから画像を抽出する。

    articles ディレクトリを自動走査しないことで、旧 full-page HTML や
    過去のAPI取得ファイルが通常ビルドに混入するのを防ぐ。
    """
    print("📂 HTMLから画像抽出中…")
    entries = []

    exclude_patterns = [
        r'はてなブックマーク',
        r'^\d{4}年',
        r'^この記事をはてなブックマークに追加$',
        r'^ワ行$',
        r'キノコと田舎遊び',
    ]

    for html_file in article_files:
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
# Phase 3A 本文 metadata（shadow mode）
# ===========================
def normalize_subject_text(text):
    """本文ラベル候補の空白だけを安全に整える（表記自体は維持する）。"""
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_subject_comparison(text):
    """本文ラベルと legacy alt の一致監査用に NFKC と空白を整える。"""
    return unicodedata.normalize("NFKC", normalize_subject_text(text))


def is_subject_label_candidate(text):
    """短い単独テキストが保守的な本文 subject 候補かを返す。"""
    candidate = normalize_subject_text(text)
    if not candidate or len(candidate) > 24:
        return False
    if candidate in SUBJECT_LABEL_STOPWORDS:
        return False
    if any(mark in candidate for mark in ("。", "！", "!")):
        return False
    if re.search(r"(?:https?://|www\.)", candidate, re.IGNORECASE):
        return False
    if re.search(r"\d{4}\s*[/年.-]\s*\d{1,2}", candidate):
        return False
    if any(re.search(pattern, candidate) for pattern in SHADOW_EXCLUDE_PATTERNS):
        return False

    # Unknown labels are explicitly useful even though they contain kanji.
    if "不明" in candidate:
        return True

    allowed = r"ァ-ヶぁ-ゖー・?？()（）「」『』【】\[\]"
    if not re.fullmatch(fr"[{allowed}]+", candidate):
        return False
    kana_count = len(re.findall(r"[ァ-ヶぁ-ゖ]", candidate))
    return kana_count >= 3


def normalize_gallery_name(detected_label):
    """将来用の gallery 名を作る。Phase 3A の production では未使用。"""
    if detected_label is None:
        return None
    if "?" in detected_label or "？" in detected_label or "不明" in detected_label:
        return "不明"
    return detected_label


def _shadow_confidence(detected_label, legacy_alt):
    if detected_label is None:
        return "low"
    if normalize_subject_comparison(detected_label) == normalize_subject_comparison(
        legacy_alt
    ):
        return "high"
    return "medium"


def extract_shadow_metadata(article_files):
    """記事本文を DOM 順に走査し、画像単位の Phase 3A metadata を返す。"""
    metadata = []
    for html_file in article_files:
        with open(html_file, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        body = soup.find(class_="entry-body") or soup
        for iframe in body.find_all("iframe"):
            title = iframe.get("title", "")
            if any(re.search(pattern, title) for pattern in SHADOW_EXCLUDE_PATTERNS):
                iframe.decompose()
        for link in body.find_all("a"):
            link_text = link.get_text(strip=True)
            if any(
                re.search(pattern, link_text) for pattern in SHADOW_EXCLUDE_PATTERNS
            ):
                link.decompose()

        current_subject = None
        for element in body.find_all((*SUBJECT_BLOCK_TAGS, "img")):
            if element.name in SUBJECT_BLOCK_TAGS:
                if element.find("img") is not None:
                    continue
                candidate = normalize_subject_text(element.get_text(" ", strip=True))
                if is_subject_label_candidate(candidate):
                    current_subject = candidate
                continue

            src = element.get("src")
            if not src:
                continue
            legacy_alt = (element.get("alt") or "").strip()
            if any(
                re.search(pattern, legacy_alt) for pattern in SHADOW_EXCLUDE_PATTERNS
            ):
                continue
            metadata.append(
                {
                    "src": src,
                    "detected_label": current_subject,
                    "gallery_name": normalize_gallery_name(current_subject),
                    "legacy_alt": legacy_alt,
                    "subject_type": "review",
                    "source": "standalone_text_state",
                    "confidence": _shadow_confidence(current_subject, legacy_alt),
                    "article_path": os.fspath(html_file),
                }
            )
    return metadata


def summarize_shadow_metadata(metadata):
    """Shadow metadata の監査用カウントを返す。"""
    detected = [item for item in metadata if item["detected_label"] is not None]
    matches = [item for item in detected if item["confidence"] == "high"]
    return {
        "total_images": len(metadata),
        "detected": len(detected),
        "undetected": len(metadata) - len(detected),
        "legacy_alt_match": len(matches),
        "legacy_alt_mismatch": len(detected) - len(matches),
        "unknown_mapped": sum(
            item["detected_label"] is not None and item["gallery_name"] == "不明"
            for item in metadata
        ),
    }


def report_shadow_metadata(metadata, audit_limit=25):
    """集計と要確認レコードを Actions で読める量に制限して表示する。"""
    summary = summarize_shadow_metadata(metadata)
    print("Phase 3A metadata shadow summary:")
    for key, value in summary.items():
        print(f"{key}={value}")

    audit_entries = [
        item
        for item in metadata
        if item["detected_label"] is None or item["confidence"] == "medium"
    ]
    for item in audit_entries[:audit_limit]:
        print(
            "Phase 3A shadow audit: "
            f"{item['article_path']} | detected={item['detected_label']} | "
            f"alt={item['legacy_alt']} | src={item['src']}"
        )
    if len(audit_entries) > audit_limit:
        print(f"Phase 3A shadow audit: {len(audit_entries) - audit_limit} more omitted")
    return summary


def save_shadow_metadata(metadata):
    """ローカル監査用 JSON を cache 配下へ保存する。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SHADOW_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

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
# ギャラリー生成（キノコページ & 五十音ページ）
# ===========================
def generate_gallery(entries, exif_cache):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    copy_shared_assets()

    # alt → [画像URL1, 画像URL2…]
    grouped = {}
    for e in entries:
        grouped.setdefault(e["alt"], []).append(e["src"])

    # index & 各ページ共通：五十音タイル HTML
    group_links_html = "<div class='aiuo-links' style='margin-top:40px;'>"
    for g in AIUO_GROUPS.keys():
        group_links_html += f'<a class="aiuo-link" href="{safe_filename(g)}.html">{g}</a>'
    group_links_html += "</div>"

    # ① 各キノコページ
    for alt, imgs in grouped.items():
        html_parts = []

        # タイトル（キノコ名 + 枚数）
        html_parts.append(
            f"<h2 style='font-size:24px; font-weight:600; text-align:center; margin-top:20px;'>"
            f"{html.escape(alt)}"
            f"<span style='font-size:15px; font-weight:400; color:#666; margin-left:6px;'>"
            f"— {len(imgs)} photos"
            f"</span>"
            f"</h2>"
        )

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
                f'<span class="thumb-fav">☆</span>'   # ← ★これだけ追加
                f'<span class="spores"></span>'
                f'<img src="{src}" alt="{html.escape(alt)}" loading="lazy">'
                f'</a>'
            )
        html_parts.append("</div>")

        # 五十音タイル
        html_parts.append(group_links_html)

        # スタイル・LG・JS
        html_parts.append(STYLE_TAG)
        html_parts.append(LIGHTGALLERY_TAGS)
        html_parts.append(SCRIPT_TAG)

        page_html = "".join(html_parts)

        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(page_html)

    # ===========================
    # ② 五十音ページ（完全修正版）
    # ===========================
    
    # 五十音 → キノコ名一覧
    aiuo_dict = {k: [] for k in AIUO_GROUPS.keys()}
    
    for alt in grouped.keys():
        if not isinstance(alt, str) or not alt:
            continue
        g = get_aiuo_group(alt)
        if g in aiuo_dict:
            aiuo_dict[g].append(alt)
    
    for g, names in aiuo_dict.items():
        # ★ 何も無い行はページを作らない
        if not names:
            continue
    
        html_parts = []
    
        # -------------------------
        # ページタイトル & フィルター枠
        # -------------------------
        html_parts.append(f"""
        <div class="aiuo-page">
    
          <h2 class="aiuo-title">{html.escape(g)}のキノコ</h2>
    
          <div class="aiuo-filter">
            <div class="kana-grid">
              <button class="kana-btn active" data-kana="all">すべて</button>
        """)
    
        # -------------------------
        # ★ ここで initials を正しく生成
        # -------------------------
        initials = sorted({
            normalize_kana_initial(n)
            for n in names
            if isinstance(n, str) and len(n) > 0
        })
    
        for ch in initials:
            esc_ch = html.escape(ch)
            html_parts.append(
                f'<button class="kana-btn" data-kana="{esc_ch}">{esc_ch}</button>'
            )
    
        html_parts.append("""
            </div>
          </div>
    
          <div class="search-wrap search-wrap--page">
            <input type="text" class="search-input" placeholder="キノコ名で絞り込み">
          </div>
        """)
    
        # -------------------------
        # カード一覧
        # -------------------------
        html_parts.append("<div class='mushroom-list'>")
    
        for n in sorted(names):
            if not isinstance(n, str) or not n:
                continue
    
            safe = safe_filename(n)
            first_char = normalize_kana_initial(n)
            imgs_for_name = grouped.get(n, [])
            thumb_src = imgs_for_name[0] if imgs_for_name else ""
    
            esc_name = html.escape(n)
            esc_kana = html.escape(first_char)
    
            img_tag = ""
            if thumb_src:
                img_tag = (
                    f"<img src='{thumb_src}?width=400' "
                    f"alt='{esc_name}' loading='lazy'>"
                )
    
            html_parts.append(f"""
            <a href="{safe}.html?from=aiuo&kana={html.escape(g)}"
               class="mushroom-card"
               data-name="{esc_name}"
               data-kana="{esc_kana}">
              <div class="mushroom-card-thumb">
                <span class="card-fav">☆</span>
                {img_tag}
              </div>
              <div class="mushroom-card-name">{esc_name}</div>
            </a>
            """)
    
        html_parts.append("</div>")  # .mushroom-list
    
        # -------------------------
        # 戻るボタン
        # -------------------------
        html_parts.append("""
          <div style="text-align:center; margin:40px 0 20px;">
            <a href="index.html" class="back-btn">
              ◀ トップに戻る
            </a>
          </div>
        </div>
        """)
    
        # -------------------------
        # 共通タグ
        # -------------------------
        html_parts.append(STYLE_TAG)
        html_parts.append(LIGHTGALLERY_TAGS)
        html_parts.append(SCRIPT_TAG)
    
        page_html = "".join(html_parts)
    
        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write(page_html)
    
    return grouped

# ===========================
# index.html を生成（最終確定版）
# ===========================
def generate_index(grouped, exif_cache):
    copy_shared_assets()
    index_parts = []

    # ===========================
    # HTML 骨格（head）
    # ===========================
    index_parts.append(f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>キノコ図鑑</title>
<div class="hero-world">
  <p class="hero-world-text">
    写真でたどる、キノコの観察記録
  </p>
</div>
<p class="gallery-guide">
  📷 写真をクリックするとフルスクリーンでじっくり観察できます<br>
  ⭐ 気になった写真は★で保存して、あとで「観察ノート」で見返せます
</p>
{STYLE_TAG}
{LIGHTGALLERY_TAGS}
""")

    # --------------------------
    # 検索用 JS データ（headに置く）
    # --------------------------
    all_mushrooms_js = []

    for alt, srcs in grouped.items():
        thumb = srcs[0] if srcs else ""
        all_mushrooms_js.append({
            "name": alt,
            "name_norm": normalize_japanese_search(alt),
            "href": f"{safe_filename(alt)}.html",
            "thumb": thumb + "?width=300"
        })

    index_parts.append(f"""
<script>
window.ALL_MUSHROOMS = {json.dumps(all_mushrooms_js, ensure_ascii=False)};
</script>
</head>
<body>
""")

    # ==========================================================
    # 🔍 全キノコ横断検索
    # ==========================================================
    index_parts.append("""
    <div class="section">
      <div class="feature-block">
      <h2 class="section-title">🔍 全キノコ横断検索</h2>
      <p class="section-desc">キノコ名からブログ内のキノコを検索できます</p>
    
      <div class="index-search-box">
        <input type="text"
               class="index-search-input"
               placeholder="キノコ名で検索（例：ベニタケ）">
      </div>
    
      <div class="index-search-results"></div>
    
      <div class="search-empty" style="display:none;">
        🔍 該当するキノコが見つかりませんでした<br>
        <small>ひらがな・カタカナを変えて試してみてください</small>
      </div>
    
      <div class="index-pagination"></div>
      </div>
    </div>
    """)

    # ==========================================================
    # 五十音別分類
    # ==========================================================
    index_parts.append("""
    <div class="section">
    <div class="feature-block">
      <h2 class="section-title">📂 五十音別分類</h2>
      <p class="section-desc">五十音順でキノコを探せます</p>
    
      <div class="aiuo-links">
    """)

    for g in AIUO_GROUPS.keys():
        index_parts.append(
            f'<a class="aiuo-link" href="{safe_filename(g)}.html">{g}</a>'
        )

    index_parts.append("""
  </div>
  </div>
</div>
""")

    # ==========================================================
    # 観察ノート専用セクション
    # ==========================================================
    index_parts.append("""
    <div class="section">
    <div class="feature-block">
      <h2 class="section-title">📓 観察ノート</h2>
      <p class="section-desc">出会ったキノコを、時間の流れとともに記録として残せます。</p>
    
      <a class="aiuo-link note-link" href="favorite.html">
        ⭐ 観察中の写真 <span id="favorite-count"></span>
      </a>
      </div>
    </div>
    """)

    # ==========================================================
    # おすすめキノコ
    # ==========================================================
    # altごとに最新撮影日
    alt_latest = {}
    for alt, srcs in grouped.items():
        best = ""
        for src in srcs:
            d = (exif_cache.get(src) or {}).get("date") or ""
            key = d.replace("/", "")
            if len(key) == 8 and key > best:
                best = key
        if best:
            alt_latest[alt] = best

    sorted_new = sorted(alt_latest.items(), key=lambda x: x[1], reverse=True)
    new_names = [n for n, _ in sorted_new][:3]

    def pick(names):
        out = []
        for n in names:
            if n in grouped and grouped[n]:
                out.append({
                    "name": n,
                    "thumb": grouped[n][0] + "?width=400",
                    "href": f"{safe_filename(n)}.html"
                })
        return out

    recommend_new = pick(new_names)
    recommend_rarity = pick(RARITY_LIST)
    recommend_popular = pick(POPULAR_LIST)

    index_parts.append("""
    <div class="section">
    <div class="feature-block">
      <h2 class="section-title">🍄 おすすめキノコ</h2>
      <p class="section-desc">写真の中から、いくつかの切り口でピックアップしています。</p>
    
      <div class="recommend-grid">
    """)

    def append_cards(title, items):
        index_parts.append(
            f"<div class='recommend-card'><h3>{title}</h3><div class='rec-items'>"
        )
        for it in items:
            index_parts.append(f"""
<a class="rec-item" href="{it['href']}">
  <img src="{it['thumb']}" alt="{it['name']}">
  <div>{it['name']}</div>
</a>
""")
        index_parts.append("</div></div>")

    append_cards("新着キノコ", recommend_new)
    append_cards("珍しいキノコ", recommend_rarity)
    append_cards("人気キノコTOP3", recommend_popular)

    index_parts.append("""
  </div>
  </div>
</div>
""")

    # ===========================
    # footer（JS）
    # ===========================
    index_parts.append(f"""
{SCRIPT_TAG}
</body>
</html>
""")

    # ===========================
    # 書き出し
    # ===========================
    with open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write("".join(index_parts))

    print("✅ index.html 生成完了")

# ===========================
# ⭐ お気に入り専用ページ生成（写真単位）
# ===========================
def generate_favorite_page(grouped):
    copy_shared_assets()
    parts = []

    parts.append("""
<h2 class="section-title">⭐ 観察ノート</h2>
<section class="note-intro" aria-label="観察ノートの説明">
  <p class="note-intro__lead">
    写真で出会ったキノコを、あとからゆっくり見返せる場所です。
  </p>
  <p class="note-intro__hint">
    ★をつけた写真は、あとでもう一度見たいと思ったものとして残ります。
  </p>
</section>
<hr class="note-divider">
<div class="section-card">
    <div class="favorite-empty" style="display:none; text-align:center; line-height:1.9;">
      まだ、ここは静かです。<br>
      <small>気になった写真に ★ をつけると、少しずつ並びはじめます。</small>
    </div>

  <!-- ★ JSが描画するので空 -->
  <div class="favorite-gallery"></div>

  <div style="text-align:center; margin-top:30px;">
    <a href="index.html" class="back-btn">
      ◀ トップに戻る
    </a>
  </div>
</div>
""")

    exif_cache = load_exif_cache()
    
    parts.append(f"""
    <script>
    window.EXIF_CACHE = {json.dumps(exif_cache, ensure_ascii=False)};
    </script>
    """)

    # src → alt（キノコ名）対応表
    src_to_alt = {}
    for alt, srcs in grouped.items():
        for src in srcs:
            src_to_alt[src] = alt
    
    parts.append(f"""
    <script>
    window.SRC_TO_ALT = {json.dumps(src_to_alt, ensure_ascii=False)};
    </script>
    """)

    parts.append(STYLE_TAG)
    parts.append(LIGHTGALLERY_TAGS)
    parts.append(SCRIPT_TAG)

    with open(f"{OUTPUT_DIR}/favorite.html", "w", encoding="utf-8") as f:
        f.write("".join(parts))

    print("⭐ favorite.html（JS描画方式）生成完了")

# ===========================
# メイン
# ===========================
def build_gallery():
    """APIの最新取得結果からギャラリー一式を生成する。"""
    article_files = fetch_hatena_articles_api()
    if not article_files:
        raise RuntimeError(
            "Hatena APIから記事ファイルを1件も取得できなかったため、"
            "空のギャラリーで上書きしないよう生成を中止します。"
        )

    entries = fetch_images(article_files)
    if not entries:
        raise RuntimeError(
            "記事から画像を1件も抽出できなかったため、"
            "空のギャラリーで上書きしないよう生成を中止します。"
        )

    # Phase 3A is audit-only. Failure is visible, but must not replace or block
    # the legacy alt-based production entries below.
    try:
        shadow_metadata = extract_shadow_metadata(article_files)
        report_shadow_metadata(shadow_metadata)
        save_shadow_metadata(shadow_metadata)
    except Exception as error:
        print(f"Phase 3A shadow metadata extraction failed: {error}")

    exif_cache = load_exif_cache()
    exif_cache = build_exif_cache(entries, exif_cache)
    save_exif_cache(exif_cache)

    grouped = generate_gallery(entries, exif_cache)
    generate_index(grouped, exif_cache)
    generate_favorite_page(grouped)


if __name__ == "__main__":
    build_gallery()
