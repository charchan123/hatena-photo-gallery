import os
import json
import inspect
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import html
import piexif
import shutil
import unicodedata
from collections import Counter, defaultdict, deque

from mushroom_knowledge import load_mushroom_master, load_sources
from portal_data import (
    build_portal_data, failure_status, save_json, success_status,
)
from season_ui import generate_season_page, load_fresh_portal_data
from records_ui import generate_records_page, render_record_cards
from detail_ui import build_detail_views, render_detail_sections

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
ARTICLE_METADATA_FILE = os.path.join(CACHE_DIR, "phase3-article-metadata.json")
SUBJECT_TAXONOMY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "subject-taxonomy.json"
)
SUBJECT_TAXONOMY_CANDIDATES_FILE = os.path.join(
    CACHE_DIR, "phase3-subject-taxonomy-candidates.json"
)
RESIDUAL_GAP_AUDIT_FILE = os.path.join(
    CACHE_DIR, "phase3b4-residual-gap-audit.json"
)
PHASE3C_READINESS_FILE = os.path.join(OUTPUT_DIR, "phase3c-readiness.json")
PHASE3C_HYBRID_PREVIEW_FILE = os.path.join(
    OUTPUT_DIR, "phase3c-hybrid-preview.json"
)
PHASE3C_PRODUCTION_STATUS_FILE = os.path.join(
    OUTPUT_DIR, "phase3c-production-status.json"
)
PORTAL_DATA_FILE = os.path.join(OUTPUT_DIR, "portal-data.json")
PORTAL_DATA_STATUS_FILE = os.path.join(OUTPUT_DIR, "portal-data-status.json")
TAXONOMY_SUBJECT_TYPES = {"mushroom", "non_mushroom"}

SHADOW_EXCLUDE_PATTERNS = [
    r'はてなブックマーク',
    r'^\d{4}年',
    r'^この記事をはてなブックマークに追加$',
    r'^ワ行$',
    r'キノコと田舎遊び',
]

SUBJECT_BLOCK_TAGS = ("p", "h1", "h2", "h3", "h4", "h5", "h6")
SUBJECT_LABEL_STOPWORDS = {"幼菌", "傘の裏"}
SUBJECT_ALLOWED_ANNOTATIONS = ("仮称", "広義")
MUSHROOM_CONTEXT_CATEGORIES = {"キノコ探索日記"}
EXPLICIT_MUSHROOM_CATEGORIES = {"キノコ", "きのこ", "菌類", "茸"}
EXPLICIT_NON_MUSHROOM_CATEGORIES = {"野鳥", "鳥類", "鳥", "昆虫", "植物", "花", "風景"}


class SubjectTaxonomyError(ValueError):
    """The version-controlled subject taxonomy does not satisfy its schema."""

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

    for filename in ("gallery.css", "gallery.js", "detail.css"):
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

def _extract_iso(exif: dict):
    """Return the first usable ISO value from piexif's supported ISO tags."""
    for tag_name in (
        "ISOSpeedRatings",
        "ISOSpeed",
        "StandardOutputSensitivity",
        "RecommendedExposureIndex",
    ):
        tag = getattr(piexif.ExifIFD, tag_name, None)
        if tag is None:
            continue

        value = exif.get(tag)
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            value = value[0]
        if value is not None:
            return value
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
    iso = _extract_iso(exif)
    iso_str = str(iso) if iso != "" else ""

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
    article_metadata = {}
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
            article_metadata[os.path.normpath(filename)] = {
                "article_id": _atom_text(entry, "atom:id", ns),
                "title": _atom_text(entry, "atom:title", ns),
                "categories": [
                    node.attrib["term"]
                    for node in entry.findall("atom:category", ns)
                    if node.attrib.get("term") is not None
                ],
                "url": _atom_entry_url(entry, ns),
                "published": _atom_text(entry, "atom:published", ns),
                "updated": _atom_text(entry, "atom:updated", ns),
            }
            print(f"✅ 保存完了: {filename}")

        count += len(entries)
        next_link = root.find("atom:link[@rel='next']", ns)
        url = next_link.attrib["href"] if next_link is not None else None

    try:
        save_article_metadata(article_metadata)
    except Exception as error:
        print(f"Phase 3B article metadata capture failed: {error}")
    print(f"📦 合計 {count} 件の記事を保存しました。")
    return article_files


def _atom_text(entry, selector, namespace):
    node = entry.find(selector, namespace)
    return node.text if node is not None else None


def _atom_entry_url(entry, namespace):
    link = entry.find("atom:link[@rel='alternate']", namespace)
    return link.attrib.get("href") if link is not None else None


def save_article_metadata(article_metadata):
    """Atom metadata を shadow 専用 sidecar に保存する。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(ARTICLE_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(article_metadata, f, ensure_ascii=False, indent=2)


def load_article_metadata():
    try:
        with open(ARTICLE_METADATA_FILE, encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}

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
# Phase 3B 本文 metadata（shadow mode）
# ===========================
def normalize_subject_text(text):
    """本文ラベル候補の空白だけを安全に整える（表記自体は維持する）。"""
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_subject_comparison(text):
    """本文ラベルと legacy alt の一致監査用に NFKC と空白を整える。"""
    return unicodedata.normalize("NFKC", normalize_subject_text(text))


def strip_subject_operational_suffix(text):
    """Remove only the allowlisted, trailing blog-operation annotation."""
    return re.sub(
        r"(?:\((?:編集中|(?:[1-9]|[12]\d|3[01])日(?:撮影)?)\)|"
        r"（(?:編集中|(?:[1-9]|[12]\d|3[01])日(?:撮影)?)）)$",
        "",
        normalize_subject_text(text),
    ).strip()


def extract_subject_candidate_label(text):
    """Return the narrowly cleaned effective subject label, or ``None``."""
    candidate = strip_subject_operational_suffix(text)
    latin_without_japanese_name = re.fullmatch(
        r"([A-Z][a-z]{2,} [a-z][a-z-]{2,})(?:\(和名無し\)|（和名無し）)([?？]?)",
        candidate,
    )
    if latin_without_japanese_name:
        candidate = "".join(latin_without_japanese_name.groups())
    return candidate if is_subject_label_candidate(candidate) else None


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

    if is_latin_scientific_label(candidate):
        return True

    validation_text = strip_subject_annotation_for_validation(candidate)
    if validation_text is None:
        return False

    # Unknown labels are explicitly useful even though they contain kanji.
    if "不明" in candidate:
        return True

    allowed = r"ァ-ヶぁ-ゖー・?？()（）「」『』【】\[\]"
    if not re.fullmatch(fr"[{allowed}]+", validation_text):
        return False
    kana_count = len(re.findall(r"[ァ-ヶぁ-ゖ]", validation_text))
    return kana_count >= 3


def strip_subject_annotation_for_validation(text):
    """許可済み注記だけを検証時に除き、未知の括弧注記は拒否する。"""
    result = text
    for annotation in SUBJECT_ALLOWED_ANNOTATIONS:
        result = re.sub(fr"(?:\({annotation}\)|（{annotation}）)", "", result)
    # Descriptive, not operational: preserve it in the returned detected label.
    result = re.sub(r"(?:\(アルビノ\)|（アルビノ）)", "", result)
    if re.search(r"[()（）]", result):
        return None
    return result


def is_latin_scientific_label(text):
    """一般英文を避けた、保守的な二名法風 Latin label 判定。"""
    return bool(re.fullmatch(r"[A-Z][a-z]{2,} [a-z][a-z-]{2,}[?？]?", text))


def diagnose_subject_label_candidate(text):
    """Explain the unchanged subject predicate for Phase 3B.4 audits only."""
    candidate = normalize_subject_text(text)
    accepted = is_subject_label_candidate(text)
    if not candidate:
        reason = "empty"
    elif len(candidate) > 24:
        reason = "too_long"
    elif candidate in SUBJECT_LABEL_STOPWORDS:
        reason = "stopword"
    elif any(mark in candidate for mark in ("。", "！", "!")):
        reason = "sentence_punctuation"
    elif re.search(r"(?:https?://|www\.)", candidate, re.IGNORECASE):
        reason = "url"
    elif re.search(r"\d{4}\s*[/年.-]\s*\d{1,2}", candidate):
        reason = "date_like"
    elif any(re.search(pattern, candidate) for pattern in SHADOW_EXCLUDE_PATTERNS):
        reason = "excluded_pattern"
    elif is_latin_scientific_label(candidate):
        reason = "accepted_latin_label"
    else:
        validation_text = strip_subject_annotation_for_validation(candidate)
        if validation_text is None:
            reason = "unsupported_annotation"
        elif "不明" in candidate:
            reason = "accepted_unknown_label"
        elif not re.fullmatch(r"[ァ-ヶぁ-ゖー・?？()（）「」『』【】\[\]]+", validation_text):
            reason = "unsupported_characters"
        elif len(re.findall(r"[ァ-ヶぁ-ゖ]", validation_text)) < 3:
            reason = "too_few_kana"
        else:
            reason = "accepted_kana_label"
    return {"candidate": accepted, "candidate_reason": reason}


def classify_subject_block(text):
    """Classify a text block without treating rejected boundaries as subjects."""
    raw_text = normalize_subject_text(text)
    candidate = extract_subject_candidate_label(raw_text)
    diagnostic = diagnose_subject_label_candidate(raw_text)
    if candidate is not None:
        return {
            "status": "accepted_subject", "label": candidate,
            "candidate_reason": diagnostic["candidate_reason"],
            "boundary_reason": None,
        }

    # These exclusions deliberately precede the subject-like patterns.  A boundary
    # is a short heading-shaped safety signal, never an additional classifier.
    if (not raw_text or len(raw_text) > 80
            or raw_text in SUBJECT_LABEL_STOPWORDS
            or any(mark in raw_text for mark in ("。", "！", "!"))
            or re.search(r"(?:https?://|www\.)", raw_text, re.IGNORECASE)
            or re.search(r"\d{4}\s*[/年.-]\s*\d{1,2}", raw_text)
            or any(re.search(pattern, raw_text) for pattern in SHADOW_EXCLUDE_PATTERNS)):
        return {
            "status": "ordinary_non_subject_text", "label": None,
            "candidate_reason": diagnostic["candidate_reason"],
            "boundary_reason": None,
        }

    reason = None
    if "の仲間" in raw_text:
        reason = "family_or_group_heading"
    elif "の残骸" in raw_text:
        reason = "remains_heading"
    elif "の事について" in raw_text:
        reason = "about_subject_heading"
    elif "＆" in raw_text or "&" in raw_text:
        reason = "multiple_subject_separator"
    elif re.search(r"\S(?:or|OR)\S", raw_text):
        reason = "multiple_subject_separator"
    elif "不明" in raw_text:
        reason = "unsupported_unknown_heading"
    elif (re.search(r"[（(][^）)]*(?:可能性|候補)[^）)]*[）)]", raw_text)
          and re.search(r"[ァ-ヶぁ-ゖ]", raw_text)):
        reason = "unsupported_candidate_annotation"
    return {
        "status": "rejected_subject_boundary" if reason else "ordinary_non_subject_text",
        "label": None, "candidate_reason": diagnostic["candidate_reason"],
        "boundary_reason": reason,
    }


def normalize_category_term(term):
    return unicodedata.normalize("NFKC", normalize_subject_text(term)).casefold()


def get_category_evidence(categories):
    """Separate article context from exact, explicit category signals.

    Short category words are deliberately never substring-matched. Categories describe
    an article, so even explicit mushroom categories are not image-level proof.
    """
    normalized = {normalize_category_term(term) for term in categories}
    contexts = {normalize_category_term(value) for value in MUSHROOM_CONTEXT_CATEGORIES}
    mushrooms = {normalize_category_term(value) for value in EXPLICIT_MUSHROOM_CATEGORIES}
    non_mushrooms = {
        normalize_category_term(value) for value in EXPLICIT_NON_MUSHROOM_CATEGORIES
    }
    return {
        "has_mushroom_context": bool(normalized & contexts),
        "has_explicit_mushroom_signal": bool(normalized & mushrooms),
        "has_explicit_non_mushroom_signal": bool(normalized & non_mushrooms),
    }


def get_category_signals(categories):
    """Compatibility helper returning explicit mushroom/non-mushroom directions."""
    evidence = get_category_evidence(categories)
    return (
        evidence["has_explicit_mushroom_signal"],
        evidence["has_explicit_non_mushroom_signal"],
    )


def normalize_category_match_text(text):
    """Normalize only the allowlisted variations used for corroboration audits."""
    value = normalize_category_term(text)
    for annotation in SUBJECT_ALLOWED_ANNOTATIONS:
        value = re.sub(fr"\s*\({annotation}\)\s*", "", value)
    return re.sub(r"[?？]+$", "", value).strip()


def match_label_to_categories(detected_label, categories):
    if detected_label is None:
        return [], "none"
    label_exact = normalize_subject_text(detected_label)
    exact = [term for term in categories if normalize_subject_text(term) == label_exact]
    if exact:
        return exact, "exact"
    label_normalized = normalize_category_match_text(detected_label)
    normalized = [
        term for term in categories
        if normalize_category_match_text(term) == label_normalized
    ]
    return (normalized, "normalized") if normalized else ([], "none")


def normalize_taxonomy_key(value):
    """Conservatively normalize a taxonomy key for comparison only."""
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value).strip().casefold()
    for annotation in SUBJECT_ALLOWED_ANNOTATIONS:
        value = re.sub(fr"\s*\({annotation}\)\s*", "", value)
    return re.sub(r"[?？]+$", "", value).strip()


def load_subject_taxonomy(path=None):
    """Load and strictly validate the static taxonomy master."""
    path = path or SUBJECT_TAXONOMY_FILE
    try:
        with open(path, encoding="utf-8") as stream:
            raw = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise SubjectTaxonomyError(str(error)) from error
    if not isinstance(raw, dict):
        raise SubjectTaxonomyError("taxonomy root must be an object")
    if "version" not in raw:
        raise SubjectTaxonomyError("taxonomy version is required")
    version = raw["version"]
    if type(version) is not int or version != 1:
        raise SubjectTaxonomyError("taxonomy version must be integer 1")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise SubjectTaxonomyError("taxonomy entries must be a list")

    exact_canonical = {}
    exact_alias = {}
    normalized = {}
    validated = []
    for index, original in enumerate(entries):
        if not isinstance(original, dict):
            raise SubjectTaxonomyError(f"entry {index} must be an object")
        canonical = original.get("canonical_name")
        subject_type = original.get("subject_type")
        aliases = original.get("aliases")
        sources = original.get("sources")
        verification = original.get("verification_status")
        notes = original.get("notes")
        if "verification_status" not in original:
            raise SubjectTaxonomyError(f"entry {index} verification_status is required")
        if "notes" not in original:
            raise SubjectTaxonomyError(f"entry {index} notes is required")
        if not isinstance(canonical, str) or not canonical.strip():
            raise SubjectTaxonomyError(f"entry {index} canonical_name must be a non-empty string")
        if not isinstance(subject_type, str):
            raise SubjectTaxonomyError(f"entry {index} subject_type must be a string")
        if subject_type not in TAXONOMY_SUBJECT_TYPES:
            raise SubjectTaxonomyError(f"entry {index} has invalid subject_type")
        if not isinstance(aliases, list):
            raise SubjectTaxonomyError(f"entry {index} aliases must be a list")
        if any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
            raise SubjectTaxonomyError(f"entry {index} aliases must contain non-empty strings")
        if not isinstance(sources, list):
            raise SubjectTaxonomyError(f"entry {index} sources must be a list")
        if any(not isinstance(source, str) or not source.strip() for source in sources):
            raise SubjectTaxonomyError(f"entry {index} sources must contain non-empty strings")
        if not isinstance(verification, str) or not verification.strip():
            raise SubjectTaxonomyError(f"entry {index} verification_status must be a non-empty string")
        if not isinstance(notes, str):
            raise SubjectTaxonomyError(f"entry {index} notes must be a string")
        entry = dict(original)
        keys = [(canonical, "canonical")] + [(alias, "alias") for alias in aliases]
        for value, kind in keys:
            normalized_key = normalize_taxonomy_key(value)
            if not normalized_key:
                raise SubjectTaxonomyError(f"entry {index} has an empty normalized key")
            if normalized_key in normalized:
                raise SubjectTaxonomyError(
                    f"taxonomy normalized key collision: {value!r}"
                )
            normalized[normalized_key] = entry
            target = exact_canonical if kind == "canonical" else exact_alias
            if value in exact_canonical or value in exact_alias:
                raise SubjectTaxonomyError(f"taxonomy exact key collision: {value!r}")
            target[value] = entry
        validated.append(entry)
    return {
        "version": version, "entries": validated,
        "exact_canonical": exact_canonical, "exact_alias": exact_alias,
        "normalized": normalized,
    }


def match_subject_taxonomy(detected_label, taxonomy):
    if detected_label is None or taxonomy is None:
        return None, "none"
    if detected_label in taxonomy["exact_canonical"]:
        return taxonomy["exact_canonical"][detected_label], "canonical_exact"
    if detected_label in taxonomy["exact_alias"]:
        return taxonomy["exact_alias"][detected_label], "alias_exact"
    entry = taxonomy["normalized"].get(normalize_taxonomy_key(detected_label))
    return (entry, "normalized") if entry else (None, "none")


def classify_subject_type(detected_label, taxonomy):
    if detected_label is None:
        return "review", "no_detected_label", "low"
    if taxonomy is None:
        return "review", "taxonomy_unavailable", "low"
    entry, _ = match_subject_taxonomy(detected_label, taxonomy)
    if entry is None:
        return "review", "taxonomy_unmatched", "low"
    subject_type = entry["subject_type"]
    return subject_type, f"taxonomy_{subject_type}", "high"


def normalize_gallery_name(detected_label, subject_type="review", canonical_name=None):
    """将来用の gallery 名を作る。Phase 3A の production では未使用。"""
    if detected_label is None or subject_type != "mushroom":
        return None
    if "?" in detected_label or "？" in detected_label or "不明" in detected_label:
        return "不明"
    return canonical_name or detected_label


def has_category_conflict(item):
    return bool(item["has_explicit_non_mushroom_signal"] and (
        item["has_mushroom_context"] or item["has_explicit_mushroom_signal"]
    ))


def _shadow_confidence(detected_label, legacy_alt):
    if detected_label is None:
        return "low"
    if normalize_subject_comparison(detected_label) == normalize_subject_comparison(
        legacy_alt
    ):
        return "high"
    return "medium"


def extract_shadow_metadata(article_files, article_metadata=None, taxonomy="load"):
    """記事本文を DOM 順に走査し、画像単位の Phase 3B metadata を返す。"""
    if taxonomy == "load":
        try:
            taxonomy = load_subject_taxonomy()
        except SubjectTaxonomyError as error:
            taxonomy = None
            print(f"Phase 3B.2 taxonomy unavailable: {error}")
    if article_metadata is None:
        article_metadata = load_article_metadata()
    metadata = []
    for html_file in article_files:
        path = os.path.normpath(os.fspath(html_file))
        article = article_metadata.get(path, {})
        categories = article.get("categories") or []
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
        subject_source_block_text = None
        subject_source_candidate_reason = None
        subject_state_status = "no_subject"
        last_rejected_boundary_text = None
        last_rejected_boundary_reason = None
        rejected_boundaries = []
        article_rows = []
        elements = body.find_all((*SUBJECT_BLOCK_TAGS, "img"))
        blocks = [element for element in elements if element.name in SUBJECT_BLOCK_TAGS]
        block_positions = {id(element): index for index, element in enumerate(elements)}
        for element_index, element in enumerate(elements):
            if element.name in SUBJECT_BLOCK_TAGS:
                raw_text = normalize_subject_text(element.get_text(" ", strip=True))
                classification = classify_subject_block(raw_text)
                if classification["status"] == "accepted_subject":
                    current_subject = classification["label"]
                    subject_source_block_text = raw_text
                    subject_source_candidate_reason = classification["candidate_reason"]
                    subject_state_status = "accepted_subject"
                    last_rejected_boundary_text = None
                    last_rejected_boundary_reason = None
                elif classification["status"] == "rejected_subject_boundary":
                    current_subject = None
                    subject_source_block_text = None
                    subject_source_candidate_reason = None
                    subject_state_status = "reset_by_rejected_boundary"
                    last_rejected_boundary_text = raw_text
                    last_rejected_boundary_reason = classification["boundary_reason"]
                    rejected_boundaries.append({
                        "boundary_index": len(rejected_boundaries),
                        "article_path": os.fspath(html_file),
                        "article_title": article.get("title"),
                        "article_url": article.get("url"),
                        "raw_text": raw_text,
                        "diagnostic_reason": classification["candidate_reason"],
                        "boundary_reason": classification["boundary_reason"],
                        "following_image_count_before_next_accepted_subject": 0,
                    })
                continue

            src = element.get("src")
            if not src:
                continue
            legacy_alt = (element.get("alt") or "").strip()
            if any(
                re.search(pattern, legacy_alt) for pattern in SHADOW_EXCLUDE_PATTERNS
            ):
                continue
            taxonomy_entry, taxonomy_match_type = match_subject_taxonomy(
                current_subject, taxonomy
            )
            subject_type, reason, classification_confidence = classify_subject_type(
                current_subject, taxonomy
            )
            category_evidence = get_category_evidence(categories)
            matched_categories, category_match_type = match_label_to_categories(
                current_subject, categories
            )
            containing = element.find_parent(SUBJECT_BLOCK_TAGS)
            previous = [
                block for block in blocks if block_positions[id(block)] < element_index
            ]
            following = [
                block for block in blocks if block_positions[id(block)] > element_index
            ]
            if subject_state_status == "reset_by_rejected_boundary" and rejected_boundaries:
                rejected_boundaries[-1]["following_image_count_before_next_accepted_subject"] += 1
            row = {
                    "src": src,
                    "detected_label": current_subject,
                    "gallery_name": normalize_gallery_name(
                        current_subject, subject_type,
                        taxonomy_entry.get("canonical_name") if taxonomy_entry else None,
                    ),
                    "legacy_alt": legacy_alt,
                    "subject_type": subject_type,
                    "source": "standalone_text_state",
                    "confidence": _shadow_confidence(current_subject, legacy_alt),
                    "article_path": os.fspath(html_file),
                    "article_title": article.get("title"),
                    "article_categories": categories,
                    "article_id": article.get("article_id"),
                    "classification_reason": reason,
                    "classification_confidence": classification_confidence,
                    "subject_source_block_text": subject_source_block_text,
                    "subject_source_candidate_reason": subject_source_candidate_reason,
                    "subject_state_status": subject_state_status,
                    "last_rejected_boundary_text": last_rejected_boundary_text,
                    "last_rejected_boundary_reason": last_rejected_boundary_reason,
                    "dom_context": {
                        "containing_block": _audit_block(containing) if containing else None,
                        "previous_blocks": [_audit_block(block) for block in previous[-3:]],
                        "next_blocks": [_audit_block(block) for block in following[:3]],
                    },
                    "taxonomy_subject_type": taxonomy_entry.get("subject_type") if taxonomy_entry else None,
                    "taxonomy_canonical_name": taxonomy_entry.get("canonical_name") if taxonomy_entry else None,
                    "taxonomy_match_type": taxonomy_match_type,
                    "taxonomy_verification_status": taxonomy_entry.get("verification_status") if taxonomy_entry else None,
                    "taxonomy_sources": taxonomy_entry.get("sources", []) if taxonomy_entry else [],
                    "matched_categories": matched_categories,
                    "category_match_type": category_match_type,
                    **category_evidence,
                }
            metadata.append(row)
            article_rows.append(row)
        if article_rows:
            article_rows[0]["article_rejected_subject_boundaries"] = rejected_boundaries
    return metadata


def summarize_shadow_metadata(metadata, legacy_production_image_count=None, taxonomy=None):
    """Shadow metadata の監査用カウントを返す。"""
    detected = [item for item in metadata if item["detected_label"] is not None]
    matches = [item for item in detected if item["confidence"] == "high"]
    summary = {
        "total_images": len(metadata),
        "detected": len(detected),
        "undetected": len(metadata) - len(detected),
        "legacy_alt_match": len(matches),
        "legacy_alt_mismatch": len(detected) - len(matches),
        "unknown_mapped": sum(
            item["detected_label"] is not None and item["gallery_name"] == "不明"
            for item in metadata
        ),
        "subject_type_mushroom": sum(item["subject_type"] == "mushroom" for item in metadata),
        "subject_type_non_mushroom": sum(item["subject_type"] == "non_mushroom" for item in metadata),
        "subject_type_review": sum(item["subject_type"] == "review" for item in metadata),
        "classification_high": sum(item["classification_confidence"] == "high" for item in metadata),
        "classification_low": sum(item["classification_confidence"] == "low" for item in metadata),
        "shadow_images_with_empty_alt": sum(not item["legacy_alt"] for item in metadata),
        "images_with_mushroom_context": sum(item["has_mushroom_context"] for item in metadata),
        "images_with_category_match": sum(item["category_match_type"] != "none" for item in metadata),
        "images_without_category_match": sum(item["category_match_type"] == "none" for item in metadata),
        "images_with_exact_category_match": sum(item["category_match_type"] == "exact" for item in metadata),
        "images_with_normalized_category_match": sum(item["category_match_type"] == "normalized" for item in metadata),
        "detected_empty_alt": sum(item["detected_label"] is not None and not item["legacy_alt"] for item in metadata),
        "unique_detected_labels": len({item["detected_label"] for item in detected}),
        "mushroom_context_only_review": sum(
            item["subject_type"] == "review"
            and item["taxonomy_match_type"] == "none"
            and item["has_mushroom_context"]
            and not item["has_explicit_mushroom_signal"]
            and not item["has_explicit_non_mushroom_signal"]
            for item in metadata
        ),
        "category_conflicts": sum(has_category_conflict(item) for item in metadata),
        "taxonomy_matched_images": sum(item["taxonomy_match_type"] != "none" for item in metadata),
        "taxonomy_unmatched_images": sum(item["detected_label"] is not None and item["taxonomy_match_type"] == "none" for item in metadata),
        "taxonomy_matched_unique_labels": len({item["detected_label"] for item in detected if item["taxonomy_match_type"] != "none"}),
        "taxonomy_unmatched_unique_labels": len({item["detected_label"] for item in detected if item["taxonomy_match_type"] == "none"}),
        "taxonomy_mushroom_images": sum(item["taxonomy_subject_type"] == "mushroom" for item in metadata),
        "taxonomy_non_mushroom_images": sum(item["taxonomy_subject_type"] == "non_mushroom" for item in metadata),
        "taxonomy_canonical_exact_images": sum(item["taxonomy_match_type"] == "canonical_exact" for item in metadata),
        "taxonomy_alias_exact_images": sum(item["taxonomy_match_type"] == "alias_exact" for item in metadata),
        "taxonomy_normalized_images": sum(item["taxonomy_match_type"] == "normalized" for item in metadata),
    }
    taxonomy_entries = (
        {(entry["canonical_name"], entry["subject_type"]) for entry in taxonomy["entries"]}
        if taxonomy else set()
    )
    summary["taxonomy_master_entries"] = len(taxonomy_entries)
    summary["taxonomy_master_mushroom_entries"] = sum(kind == "mushroom" for _, kind in taxonomy_entries)
    summary["taxonomy_master_non_mushroom_entries"] = sum(kind == "non_mushroom" for _, kind in taxonomy_entries)
    if legacy_production_image_count is not None:
        summary["legacy_production_image_count"] = legacy_production_image_count
    return summary


def summarize_detected_labels(metadata):
    """Aggregate every detected label; callers may bound only its log rendering."""
    labels = {}
    for item in metadata:
        label = item["detected_label"]
        if label is None:
            continue
        row = labels.setdefault(label, {
            "detected_label": label, "image_count": 0, "article_paths": set(),
            "categories": set(), "category_match_count": 0, "empty_alt_count": 0,
            "subject_type_counts": {},
            "mushroom_context_count": 0,
            "category_exact_count": 0, "category_normalized_count": 0,
        })
        row["image_count"] += 1
        row["article_paths"].add(item["article_path"])
        row["categories"].update(item["article_categories"])
        row["category_match_count"] += item["category_match_type"] != "none"
        row["category_exact_count"] += item["category_match_type"] == "exact"
        row["category_normalized_count"] += item["category_match_type"] == "normalized"
        row["empty_alt_count"] += not item["legacy_alt"]
        row["mushroom_context_count"] += item["has_mushroom_context"]
        subject_type = item["subject_type"]
        row["subject_type_counts"][subject_type] = row["subject_type_counts"].get(subject_type, 0) + 1
    result = []
    for row in labels.values():
        result.append({
            "detected_label": row["detected_label"],
            "image_count": row["image_count"],
            "article_count": len(row["article_paths"]),
            "categories": sorted(row["categories"]),
            "category_match_count": row["category_match_count"],
            "category_exact_count": row["category_exact_count"],
            "category_normalized_count": row["category_normalized_count"],
            "empty_alt_count": row["empty_alt_count"],
            "subject_type_counts": row["subject_type_counts"],
            "mushroom_context_count": row["mushroom_context_count"],
            "current_taxonomy_match": next(
                item["taxonomy_match_type"] for item in metadata
                if item["detected_label"] == row["detected_label"]
            ),
            "current_subject_type": next(
                item["subject_type"] for item in metadata
                if item["detected_label"] == row["detected_label"]
            ),
        })
    return result


def _audit_row(prefix, item):
    print(
        f"{prefix}: {item['article_path']} | title={item['article_title']} | "
        f"categories={item['article_categories']} | detected={item['detected_label']} | "
        f"matched_categories={item['matched_categories']} | match={item['category_match_type']} | "
        f"subject_type={item['subject_type']} | reason={item['classification_reason']} | "
        f"src={item['src']}"
    )


def report_shadow_metadata(metadata, audit_limit=30, legacy_production_image_count=None, taxonomy=None):
    """集計と要確認レコードを Actions で読める量に制限して表示する。"""
    summary = summarize_shadow_metadata(metadata, legacy_production_image_count, taxonomy)
    print("Phase 3B.2 metadata shadow summary:")
    for key, value in summary.items():
        print(f"{key}={value}")

    priority = lambda item: (
        item["detected_label"] is not None,
        item["confidence"] != "medium",
        item["subject_type"] != "review",
        not has_category_conflict(item),
        item["subject_type"] != "non_mushroom",
        not (item["detected_label"] and not item["legacy_alt"]),
    )
    audit_entries = sorted(metadata, key=priority)
    for item in audit_entries[:audit_limit]:
        _audit_row("Phase 3B.1 shadow audit", item)
    if len(audit_entries) > audit_limit:
        print(f"Phase 3B.1 shadow audit: {len(audit_entries) - audit_limit} more omitted")
    for item in [x for x in metadata if x["subject_type"] == "non_mushroom"][:20]:
        print(
            "Phase 3B non-mushroom audit: "
            f"{item['article_path']} | categories={item['article_categories']} | "
            f"detected={item['detected_label']} | src={item['src']}"
        )

    empty_alt = [item for item in metadata if item["detected_label"] is not None and not item["legacy_alt"]]
    for item in empty_alt[:50]:
        _audit_row("Phase 3B.1 empty-alt detected audit", item)

    mushroom_evidence = [item for item in metadata if item["detected_label"] is not None and (
        item["has_mushroom_context"] or item["has_explicit_mushroom_signal"]
    )]
    for item in mushroom_evidence[:40]:
        evidence_class = "A" if item["matched_categories"] else (
            "B" if item["has_mushroom_context"] else "C"
        )
        print(f"Phase 3B.1 mushroom-evidence audit: class={evidence_class}", end=" | ")
        _audit_row("record", item)

    distinct_labels = sorted(
        summarize_detected_labels(metadata),
        key=lambda row: (-row["image_count"], row["detected_label"]),
    )
    for row in distinct_labels[:150]:
        print(f"Phase 3B.1 distinct-label audit: {row}")

    suspicious = [item for item in metadata if item["detected_label"] is not None and (
        not item["legacy_alt"]
        or (item["has_mushroom_context"] and not item["matched_categories"])
        or (item["matched_categories"] and item["subject_type"] == "review")
        or has_category_conflict(item)
        or item["subject_type"] == "non_mushroom"
        or is_latin_scientific_label(item["detected_label"])
        or any(mark in item["detected_label"] for mark in ("?", "？", "不明", "(仮称)", "（仮称）", "(広義)", "（広義）"))
    )]
    for item in suspicious[:50]:
        _audit_row("Phase 3B.2 suspicious-label audit", item)

    for item in [item for item in metadata if item["taxonomy_match_type"] != "none"][:50]:
        print("Phase 3B.2 taxonomy-matched audit: " + json.dumps({
            key: item[key] for key in (
                "detected_label", "taxonomy_canonical_name", "taxonomy_subject_type",
                "taxonomy_match_type", "taxonomy_verification_status",
                "category_match_type", "article_path", "src",
            )
        }, ensure_ascii=False))
    unmatched = [row for row in distinct_labels if row["current_taxonomy_match"] == "none"]
    for row in unmatched[:300]:
        row = dict(row)
        label = row["detected_label"]
        row["flags"] = {
            "question": any(mark in label for mark in ("?", "？")),
            "unknown": "不明" in label,
            "provisional": any(mark in label for mark in ("(仮称)", "（仮称）")),
            "broad_sense": any(mark in label for mark in ("(広義)", "（広義）")),
            "latin": is_latin_scientific_label(label),
        }
        print("Phase 3B.2 taxonomy-unmatched distinct-label audit: " + json.dumps(row, ensure_ascii=False))
    return summary


def save_taxonomy_candidates(metadata):
    """Export every unmatched distinct label for offline verification."""
    candidates = [
        row for row in summarize_detected_labels(metadata)
        if row["current_taxonomy_match"] == "none"
    ]
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SUBJECT_TAXONOMY_CANDIDATES_FILE, "w", encoding="utf-8") as stream:
        json.dump(candidates, stream, ensure_ascii=False, indent=2)


def report_category_inventory(article_files, article_metadata=None, limit=50):
    if article_metadata is None:
        article_metadata = load_article_metadata()
    counts = {}
    without_categories = 0
    context_articles = non_mushroom_articles = conflict_articles = 0
    for article_file in article_files:
        categories = article_metadata.get(os.path.normpath(os.fspath(article_file)), {}).get("categories") or []
        if not categories:
            without_categories += 1
        evidence = get_category_evidence(categories)
        context_articles += evidence["has_mushroom_context"]
        non_mushroom_articles += evidence["has_explicit_non_mushroom_signal"]
        conflict_articles += (evidence["has_mushroom_context"] or evidence["has_explicit_mushroom_signal"]) and evidence["has_explicit_non_mushroom_signal"]
        for category in set(categories):
            counts[category] = counts.get(category, 0) + 1
    print("Phase 3B category inventory:")
    for category, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        print(f"{category}={count} articles")
    print(f"uncategorized={without_categories} articles")
    result = {"categories": counts, "total_unique_categories": len(counts), "articles_with_categories": len(article_files) - without_categories, "articles_without_categories": without_categories, "articles_with_mushroom_context": context_articles, "articles_with_explicit_non_mushroom_signal": non_mushroom_articles, "articles_with_conflicting_signals": conflict_articles}
    print("Phase 3B.1 category inventory summary:")
    for key, value in result.items():
        if key != "categories":
            print(f"{key}={value}")
    return result


def save_shadow_metadata(metadata):
    """ローカル監査用 JSON を cache 配下へ保存する。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SHADOW_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def _residual_label_flags(label):
    return {
        "question": any(mark in label for mark in ("?", "？")),
        "unknown": "不明" in label,
        "provisional": any(mark in label for mark in ("(仮称)", "（仮称）")),
        "broad_sense": any(mark in label for mark in ("(広義)", "（広義）")),
        "latin": is_latin_scientific_label(label),
    }


def _audit_block(block):
    text = normalize_subject_text(block.get_text(" ", strip=True))
    effective_label = extract_subject_candidate_label(text)
    return {
        "tag": block.name,
        "text": text,
        "contains_image": block.find("img") is not None,
        **diagnose_subject_label_candidate(text),
        "effective_candidate": effective_label is not None,
        "effective_label": effective_label,
    }


def _prepare_gap_article(html_file):
    with open(html_file, encoding="utf-8") as stream:
        soup = BeautifulSoup(stream, "html.parser")
    body = soup.find(class_="entry-body") or soup
    for iframe in body.find_all("iframe"):
        if any(re.search(pattern, iframe.get("title", "")) for pattern in SHADOW_EXCLUDE_PATTERNS):
            iframe.decompose()
    for link in body.find_all("a"):
        if any(re.search(pattern, link.get_text(strip=True)) for pattern in SHADOW_EXCLUDE_PATTERNS):
            link.decompose()
    elements = body.find_all((*SUBJECT_BLOCK_TAGS, "img"))
    images = [element for element in elements if element.name == "img" and element.get("src") and not any(
        re.search(pattern, (element.get("alt") or "").strip())
        for pattern in SHADOW_EXCLUDE_PATTERNS
    )]
    return elements, images


def build_residual_gap_audit(article_files, metadata, article_metadata=None):
    """Build a complete, occurrence-preserving Phase 3B.4 audit."""
    if article_metadata is None:
        article_metadata = load_article_metadata()
    by_path = {}
    for item in metadata:
        by_path.setdefault(os.path.normpath(item["article_path"]), []).append(item)
    undetected = []
    articles = []
    for html_file in article_files:
        path = os.path.normpath(os.fspath(html_file))
        rows = by_path.get(path, [])
        elements, images = _prepare_gap_article(html_file)
        if len(rows) != len(images):
            raise ValueError(
                f"shadow occurrence mismatch for {html_file}: "
                f"metadata={len(rows)} parsed={len(images)}"
            )
        valid_blocks = [element for element in elements if element.name in SUBJECT_BLOCK_TAGS
                        and extract_subject_candidate_label(element.get_text(" ", strip=True)) is not None]
        first_subject = valid_blocks[0] if valid_blocks else None
        article_rows = []
        for image_index, (image, row) in enumerate(zip(images, rows)):
            if row["detected_label"] is not None:
                continue
            element_index = elements.index(image)
            before = [element for element in elements[:element_index] if element.name in SUBJECT_BLOCK_TAGS
                      and normalize_subject_text(element.get_text(" ", strip=True))]
            after = [element for element in elements[element_index + 1:] if element.name in SUBJECT_BLOCK_TAGS
                     and normalize_subject_text(element.get_text(" ", strip=True))]
            if first_subject is None:
                position = "article_has_no_valid_subject"
            elif elements.index(first_subject) > element_index:
                position = "before_first_valid_subject"
            else:
                position = "after_first_valid_subject"
            next_subject = next((block for block in after
                                 if extract_subject_candidate_label(block.get_text(" ", strip=True)) is not None), None)
            containing = image.find_parent(SUBJECT_BLOCK_TAGS)
            matched, match_type = match_label_to_categories(row["legacy_alt"], row["article_categories"])
            record = {
                "src": row["src"], "legacy_alt": row["legacy_alt"],
                "article_path": row["article_path"], "article_title": row["article_title"],
                "article_id": row["article_id"], "article_categories": row["article_categories"],
                "article_image_index": image_index, "article_shadow_image_count": len(rows),
                "position_relative_to_first_subject": position,
                "containing_block": _audit_block(containing) if containing else None,
                "previous_blocks": [_audit_block(block) for block in before[-3:]],
                "next_blocks": [_audit_block(block) for block in after[:3]],
                "next_valid_subject": None,
                "legacy_alt_category_match": {"matched_categories": matched, "match_type": match_type},
            }
            if next_subject is not None:
                next_index = elements.index(next_subject)
                record["next_valid_subject"] = {
                    "text": extract_subject_candidate_label(next_subject.get_text(" ", strip=True)),
                    "tag": next_subject.name,
                    "blocks_ahead": sum(e.name in SUBJECT_BLOCK_TAGS for e in elements[element_index + 1:next_index + 1]),
                    "images_ahead": sum(e.name == "img" for e in elements[element_index + 1:next_index]),
                }
            undetected.append(record)
            article_rows.append(record)
        if article_rows:
            info = article_metadata.get(path, {})
            articles.append({
                "article_path": os.fspath(html_file), "article_title": info.get("title"),
                "article_id": info.get("article_id"), "article_categories": info.get("categories") or [],
                "total_shadow_images": len(rows), "undetected_image_count": len(article_rows),
                "legacy_alt_empty_count": sum(not row["legacy_alt"] for row in article_rows),
                "legacy_alt_nonempty_count": sum(bool(row["legacy_alt"]) for row in article_rows),
                "legacy_alt_category_match_count": sum(row["legacy_alt_category_match"]["match_type"] != "none" for row in article_rows),
                "first_valid_subject_label": extract_subject_candidate_label(first_subject.get_text(" ", strip=True)) if first_subject else None,
                "position_bucket_counts": {value: sum(row["position_relative_to_first_subject"] == value for row in article_rows)
                    for value in ("before_first_valid_subject", "after_first_valid_subject", "article_has_no_valid_subject")},
            })
    unmatched = []
    for row in summarize_detected_labels(metadata):
        if row["current_taxonomy_match"] == "none":
            item = dict(row)
            item["flags"] = _residual_label_flags(row["detected_label"])
            item["normalized_taxonomy_key"] = normalize_taxonomy_key(row["detected_label"])
            unmatched.append(item)
    unmatched.sort(key=lambda row: (-row["image_count"], row["detected_label"]))
    summary = {
        "total_shadow_images": len(metadata), "detected_images": len(metadata) - len(undetected),
        "undetected_images": len(undetected), "undetected_articles": len(articles),
        **{f"undetected_{value}": sum(row["position_relative_to_first_subject"] == value for row in undetected)
           for value in ("before_first_valid_subject", "after_first_valid_subject", "article_has_no_valid_subject")},
        "undetected_legacy_alt_empty": sum(not row["legacy_alt"] for row in undetected),
        "undetected_legacy_alt_nonempty": sum(bool(row["legacy_alt"]) for row in undetected),
        **{f"undetected_legacy_alt_category_{kind}": sum(row["legacy_alt_category_match"]["match_type"] == kind for row in undetected)
           for kind in ("exact", "normalized", "none")},
        "undetected_containing_block_present": sum(row["containing_block"] is not None for row in undetected),
        "undetected_containing_block_candidate": sum(bool(row["containing_block"] and row["containing_block"]["candidate"]) for row in undetected),
        "taxonomy_unmatched_images": sum(row["image_count"] for row in unmatched),
        "taxonomy_unmatched_unique_labels": len(unmatched),
    }
    for flag in ("question", "unknown", "provisional", "broad_sense", "latin"):
        summary[f"taxonomy_unmatched_{flag}_labels"] = sum(row["flags"][flag] for row in unmatched)
    return {"version": 1, "summary": summary, "undetected_images": undetected,
            "undetected_articles": articles, "taxonomy_unmatched_labels": unmatched}


def report_residual_gap_audit(audit):
    print("Phase 3B.4 residual gap summary:")
    for key, value in audit["summary"].items():
        print(f"{key}={value}")
    if audit["summary"]["undetected_after_first_valid_subject"]:
        print("Phase 3B.4 audit anomaly: undetected images occur after first valid subject")
    for row in audit["undetected_images"]:
        print("Phase 3B.4 undetected-image audit: " + json.dumps(row, ensure_ascii=False))


def save_residual_gap_audit(audit):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(RESIDUAL_GAP_AUDIT_FILE, "w", encoding="utf-8") as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2)


def _sample_unique(values, limit=3):
    """Return the first distinct non-null values without losing stable order."""
    return list(dict.fromkeys(value for value in values if value is not None))[:limit]


def _aggregate_readiness_labels(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["detected_label"]].append(row)
    result = []
    for label, items in groups.items():
        result.append({
            "detected_label": label,
            "image_count": len(items),
            "article_count": len({item["article_path"] for item in items}),
            "classification_reason": items[0]["classification_reason"],
            "sample_srcs": _sample_unique(item["src"] for item in items),
            "sample_articles": _sample_unique(item["article_path"] for item in items),
        })
    return sorted(result, key=lambda row: (-row["image_count"], row["detected_label"]))


def build_phase3c_readiness(legacy_entries, shadow_metadata):
    """Compare legacy production with the audit-only Phase 3C candidate."""
    candidates = [
        {"alt": row["gallery_name"], "src": row["src"], "shadow": row}
        for row in shadow_metadata
        if row["subject_type"] == "mushroom" and row["gallery_name"] is not None
    ]
    legacy_pairs = Counter((row["src"], row["alt"]) for row in legacy_entries)
    candidate_pairs = Counter((row["src"], row["alt"]) for row in candidates)
    exact_overlap = legacy_pairs & candidate_pairs
    legacy_remaining = legacy_pairs - candidate_pairs
    candidate_remaining = candidate_pairs - legacy_pairs

    shadow_by_pair = defaultdict(deque)
    shadow_by_src = defaultdict(list)
    for row in shadow_metadata:
        shadow_by_pair[(row["src"], row["legacy_alt"])].append(row)
        shadow_by_src[row["src"]].append(row)

    legacy_only = []
    remaining = legacy_remaining.copy()
    for entry in legacy_entries:
        pair = (entry["src"], entry["alt"])
        if not remaining[pair]:
            continue
        remaining[pair] -= 1
        shadow = shadow_by_pair[pair].popleft() if shadow_by_pair[pair] else None
        legacy_only.append({
            "src": entry["src"], "legacy_alt": entry["alt"],
            "detected_label": shadow.get("detected_label") if shadow else None,
            "subject_type": shadow.get("subject_type") if shadow else None,
            "gallery_name": shadow.get("gallery_name") if shadow else None,
            "classification_reason": shadow.get("classification_reason") if shadow else "shadow_metadata_missing",
            "taxonomy_match_type": shadow.get("taxonomy_match_type") if shadow else None,
            "article_title": shadow.get("article_title") if shadow else None,
            "article_path": shadow.get("article_path") if shadow else None,
            "shadow_metadata_present": shadow is not None,
        })

    candidate_only = []
    remaining = candidate_remaining.copy()
    for candidate in candidates:
        pair = (candidate["src"], candidate["alt"])
        if not remaining[pair]:
            continue
        remaining[pair] -= 1
        shadow = candidate["shadow"]
        candidate_only.append({
            "src": shadow["src"], "gallery_name": shadow["gallery_name"],
            "detected_label": shadow["detected_label"], "subject_type": shadow["subject_type"],
            "classification_reason": shadow["classification_reason"],
            "article_title": shadow["article_title"], "article_path": shadow["article_path"],
            "legacy_alt": shadow["legacy_alt"],
        })

    legacy_by_src = Counter(row["src"] for row in legacy_entries)
    candidate_by_src = Counter(row["src"] for row in candidates)
    shared_srcs = legacy_by_src.keys() & candidate_by_src.keys()
    name_changes = []
    for src in sorted(shared_srcs):
        legacy_names = [row["alt"] for row in legacy_entries if row["src"] == src]
        candidate_names = [row["alt"] for row in candidates if row["src"] == src]
        if Counter(legacy_names) == Counter(candidate_names):
            continue
        shadow = shadow_by_src[src][0]
        name_changes.append({
            "src": src, "legacy_names": legacy_names, "candidate_names": candidate_names,
            "detected_label": shadow["detected_label"], "gallery_name": shadow["gallery_name"],
            "taxonomy_match_type": shadow["taxonomy_match_type"],
            "article_title": shadow["article_title"],
        })

    blocked = _aggregate_readiness_labels([
        row for row in shadow_metadata
        if row["detected_label"] is not None
        and row["subject_type"] == "review"
        and row["classification_reason"] == "taxonomy_unmatched"
    ])
    non_mushroom = _aggregate_readiness_labels([
        row for row in shadow_metadata if row["subject_type"] == "non_mushroom"
    ])
    undetected = [{
        "src": row["src"], "legacy_alt": row["legacy_alt"],
        "article_title": row["article_title"], "article_path": row["article_path"],
        "classification_reason": row["classification_reason"],
    } for row in shadow_metadata if row["detected_label"] is None]

    legacy_count = len(legacy_entries)
    shadow_count = len(shadow_metadata)
    summary = {
        "legacy_production_image_count": legacy_count,
        "legacy_unique_names": len({row["alt"] for row in legacy_entries}),
        "shadow_total_images": shadow_count,
        "shadow_detected_images": sum(row["detected_label"] is not None for row in shadow_metadata),
        "shadow_undetected_images": len(undetected),
        "taxonomy_mushroom_images": sum(row["subject_type"] == "mushroom" for row in shadow_metadata),
        "taxonomy_non_mushroom_images": sum(row["subject_type"] == "non_mushroom" for row in shadow_metadata),
        "review_images": sum(row["subject_type"] == "review" for row in shadow_metadata),
        "taxonomy_unmatched_review_images": sum(row["classification_reason"] == "taxonomy_unmatched" for row in shadow_metadata),
        "no_detected_label_review_images": sum(row["classification_reason"] == "no_detected_label" for row in shadow_metadata),
        "taxonomy_unavailable_review_images": sum(row["classification_reason"] == "taxonomy_unavailable" for row in shadow_metadata),
        "candidate_production_image_count": len(candidates),
        "candidate_unique_gallery_names": len({row["alt"] for row in candidates}),
        "exact_occurrence_overlap_count": sum(exact_overlap.values()),
        "legacy_only_occurrence_count": sum(legacy_remaining.values()),
        "candidate_only_occurrence_count": sum(candidate_remaining.values()),
        "legacy_src_only_count": sum((legacy_by_src - candidate_by_src).values()),
        "candidate_src_only_count": sum((candidate_by_src - legacy_by_src).values()),
        "same_src_name_change_count": len(name_changes),
        "blocked_review_unique_labels": len(blocked),
        "candidate_vs_legacy_ratio": len(candidates) / legacy_count if legacy_count else None,
        "taxonomy_mushroom_share_of_shadow": sum(row["subject_type"] == "mushroom" for row in shadow_metadata) / shadow_count if shadow_count else None,
    }
    notes = []
    observations = (
        (summary["review_images"], "review images remain"),
        (summary["shadow_undetected_images"], "undetected images remain"),
        (len(candidates) < legacy_count, "candidate production would contain fewer images than legacy"),
        (summary["candidate_only_occurrence_count"], "candidate introduces images absent from legacy"),
        (name_changes, "name changes exist"),
        (non_mushroom, "non-mushroom exclusions exist"),
    )
    notes.extend(message for condition, message in observations if condition)
    return {"version": 1, "summary": summary, "blocked_review_labels": blocked,
            "legacy_only": legacy_only, "candidate_only": candidate_only,
            "name_changes": name_changes, "non_mushroom_exclusions": non_mushroom,
            "undetected": undetected, "readiness_notes": notes}


def report_phase3c_readiness(audit):
    print("Phase 3C.0 readiness summary:")
    for key, value in audit["summary"].items():
        print(f"{key}={value}")
    for row in audit["blocked_review_labels"]:
        print("Phase 3C.0 blocked review label: " + json.dumps(row, ensure_ascii=False))


def save_phase3c_readiness(audit):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(PHASE3C_READINESS_FILE, "w", encoding="utf-8") as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2)


def _phase3c_article_fields(shadow, article_metadata):
    """Return only observed article metadata; never synthesize a URL."""
    path = os.path.normpath(os.fspath(shadow.get("article_path", "")))
    article = article_metadata.get(path, {})
    return {
        "article_title": article.get("title", shadow.get("article_title")),
        "article_url": article.get("url"),
        "article_id": article.get("article_id", shadow.get("article_id")),
        "article_published": article.get("published"),
        "article_path": shadow.get("article_path"),
    }


def _phase3c_shadow_audit_row(shadow, article_metadata, **extra):
    row = {
        "src": shadow.get("src"),
        "subject_type": shadow.get("subject_type"),
        "detected_label": shadow.get("detected_label"),
        "gallery_name": shadow.get("gallery_name"),
        "taxonomy_match_type": shadow.get("taxonomy_match_type"),
        "taxonomy_canonical_name": shadow.get("taxonomy_canonical_name"),
        "classification_reason": shadow.get("classification_reason"),
        "subject_source_block_text": shadow.get("subject_source_block_text"),
        "subject_source_candidate_reason": shadow.get("subject_source_candidate_reason"),
        "subject_state_status": shadow.get("subject_state_status"),
        "last_rejected_boundary_text": shadow.get("last_rejected_boundary_text"),
        "last_rejected_boundary_reason": shadow.get("last_rejected_boundary_reason"),
        "dom_context": shadow.get("dom_context"),
        **_phase3c_article_fields(shadow, article_metadata),
    }
    row.update(extra)
    return row


def _phase3c_group(rows, key_fields, name_fields):
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[key] for key in key_fields)].append(row)
    result = []
    for key, items in grouped.items():
        group = dict(zip(name_fields, key))
        group.update({
            "image_count": len(items),
            "article_count": len({item["article_path"] for item in items}),
            "sample_srcs": _sample_unique(item["src"] for item in items),
            "sample_article_urls": _sample_unique(
                item["article_url"] for item in items
            ),
        })
        result.append(group)
    return sorted(result, key=lambda row: (
        -row["image_count"], *(str(row[field]) for field in name_fields)
    ))


def build_phase3c_hybrid_preview(
    legacy_entries, shadow_metadata, article_metadata=None
):
    """Build an audit-only hybrid candidate while preserving occurrences.

    Legacy and shadow extraction are expected to use the same article-file order
    and DOM order.  Per-src queues therefore match duplicate URLs one occurrence
    at a time, and unmatched shadow rows are reconsidered in original order.
    """
    article_metadata = article_metadata or {}
    article_metadata = {
        os.path.normpath(os.fspath(path)): value
        for path, value in article_metadata.items()
    }
    by_src = defaultdict(deque)
    for index, shadow in enumerate(shadow_metadata):
        by_src[shadow["src"]].append(index)
    consumed = set()
    hybrid = []
    audit = {key: [] for key in (
        "renamed_occurrences", "rename_conflicts", "added_occurrences", "removed_non_mushroom",
        "legacy_fallback_review", "legacy_fallback_undetected",
        "legacy_fallback_shadow_missing", "new_review_excluded",
        "new_undetected_excluded", "new_non_mushroom_excluded",
        "new_boundary_blocked_excluded",
    )}
    same_name = preserved_exact = 0

    for legacy in legacy_entries:
        queue = by_src[legacy["src"]]
        if not queue:
            hybrid.append({"alt": legacy["alt"], "src": legacy["src"]})
            preserved_exact += 1
            audit["legacy_fallback_shadow_missing"].append({
                "src": legacy["src"], "legacy_alt": legacy["alt"],
                "decision": "legacy_fallback_shadow_missing",
                "classification_reason": "shadow_metadata_missing",
                "article_title": None, "article_url": None, "article_id": None,
                "article_published": None, "article_path": None,
            })
            continue
        index = queue.popleft()
        consumed.add(index)
        shadow = shadow_metadata[index]
        subject_type = shadow.get("subject_type")
        if subject_type == "non_mushroom":
            audit["removed_non_mushroom"].append(_phase3c_shadow_audit_row(
                shadow, article_metadata, legacy_alt=legacy["alt"],
                decision="confirmed_non_mushroom_removed",
            ))
        elif shadow.get("detected_label") is None:
            hybrid.append({"alt": legacy["alt"], "src": legacy["src"]})
            preserved_exact += 1
            audit["legacy_fallback_undetected"].append(_phase3c_shadow_audit_row(
                shadow, article_metadata, legacy_alt=legacy["alt"],
                decision="legacy_fallback_undetected",
            ))
        elif subject_type == "mushroom" and shadow.get("gallery_name") is not None:
            name = shadow["gallery_name"]
            if name == legacy["alt"]:
                hybrid.append({"alt": name, "src": legacy["src"]})
                same_name += 1
                preserved_exact += 1
            elif normalize_taxonomy_key(legacy["alt"]) == normalize_taxonomy_key(
                    shadow["detected_label"]):
                hybrid.append({"alt": name, "src": legacy["src"]})
                audit["renamed_occurrences"].append(_phase3c_shadow_audit_row(
                    shadow, article_metadata, legacy_alt=legacy["alt"],
                    hybrid_alt=name, proposed_hybrid_alt=name,
                    decision="compatible_rename",
                ))
            else:
                hybrid.append({"alt": legacy["alt"], "src": legacy["src"]})
                preserved_exact += 1
                audit["rename_conflicts"].append(_phase3c_shadow_audit_row(
                    shadow, article_metadata, legacy_alt=legacy["alt"],
                    hybrid_alt=legacy["alt"], proposed_hybrid_alt=name,
                    decision="rename_conflict_manual_review",
                ))
        else:
            hybrid.append({"alt": legacy["alt"], "src": legacy["src"]})
            preserved_exact += 1
            audit["legacy_fallback_review"].append(_phase3c_shadow_audit_row(
                shadow, article_metadata, legacy_alt=legacy["alt"],
                decision="legacy_fallback_review",
            ))

    for index, shadow in enumerate(shadow_metadata):
        if index in consumed:
            continue
        common = _phase3c_shadow_audit_row(
            shadow, article_metadata, legacy_alt=None
        )
        if shadow.get("subject_state_status") == "reset_by_rejected_boundary":
            audit["new_boundary_blocked_excluded"].append({
                **common, "decision": "new_boundary_blocked_excluded",
            })
        elif (shadow.get("subject_type") == "mushroom"
                and shadow.get("subject_state_status") == "accepted_subject"
                and shadow.get("gallery_name") is not None):
            hybrid.append({"alt": shadow["gallery_name"], "src": shadow["src"]})
            audit["added_occurrences"].append({
                **common, "hybrid_alt": shadow["gallery_name"],
                "decision": "confirmed_new_mushroom_added",
            })
        elif shadow.get("detected_label") is None:
            audit["new_undetected_excluded"].append({
                **common, "decision": "new_undetected_excluded",
            })
        elif shadow.get("subject_type") == "non_mushroom":
            audit["new_non_mushroom_excluded"].append({
                **common, "decision": "new_non_mushroom_excluded",
            })
        else:
            audit["new_review_excluded"].append({
                **common, "decision": "new_review_excluded",
            })

    rename_groups = _phase3c_group(
        audit["renamed_occurrences"], ("legacy_alt", "hybrid_alt"),
        ("legacy_alt", "hybrid_alt"),
    )
    added_groups = _phase3c_group(
        audit["added_occurrences"], ("gallery_name",), ("gallery_name",)
    )
    rename_conflict_groups = _phase3c_group(
        audit["rename_conflicts"], ("legacy_alt", "proposed_hybrid_alt"),
        ("legacy_alt", "proposed_hybrid_alt"),
    )
    rejected_boundaries = []
    boundary_keys = set()
    for shadow in shadow_metadata:
        for boundary in shadow.get("article_rejected_subject_boundaries", []):
            key = (boundary.get("article_path"), boundary.get("boundary_index"))
            if key not in boundary_keys:
                boundary_keys.add(key)
                rejected_boundaries.append(dict(boundary))
    rejected_boundaries.sort(key=lambda row: (
        str(row.get("article_path")), str(row.get("raw_text"))
    ))
    summary = {
        "legacy_image_count": len(legacy_entries),
        "hybrid_image_count": len(hybrid),
        "net_image_delta": len(hybrid) - len(legacy_entries),
        "legacy_preserved_exact_count": preserved_exact,
        "confirmed_mushroom_same_name_count": same_name,
        "confirmed_mushroom_renamed_count": len(audit["renamed_occurrences"]),
        "compatible_rename_count": len(audit["renamed_occurrences"]),
        "rename_conflict_count": len(audit["rename_conflicts"]),
        "rename_conflict_group_count": len(rename_conflict_groups),
        "review_legacy_fallback_count": len(audit["legacy_fallback_review"]),
        "undetected_legacy_fallback_count": len(audit["legacy_fallback_undetected"]),
        "shadow_missing_legacy_fallback_count": len(audit["legacy_fallback_shadow_missing"]),
        "confirmed_non_mushroom_removed_count": len(audit["removed_non_mushroom"]),
        "confirmed_new_mushroom_added_count": len(audit["added_occurrences"]),
        "new_review_excluded_count": len(audit["new_review_excluded"]),
        "new_undetected_excluded_count": len(audit["new_undetected_excluded"]),
        "new_non_mushroom_excluded_count": len(audit["new_non_mushroom_excluded"]),
        "new_boundary_blocked_excluded_count": len(audit["new_boundary_blocked_excluded"]),
        "rejected_subject_boundary_count": len(rejected_boundaries),
        "images_blocked_by_rejected_boundary_count": sum(
            row.get("following_image_count_before_next_accepted_subject", 0)
            for row in rejected_boundaries
        ),
        "hybrid_unique_names": len({row["alt"] for row in hybrid}),
        "rename_group_count": len(rename_groups),
        "added_gallery_name_count": len(added_groups),
    }
    notes = [
        "This report describes the guarded hybrid candidate; actual production "
        "selection is recorded in phase3c-production-status.json.",
        "Review fallbacks retain taxonomy review classification.",
        "New review, undetected, and non-mushroom occurrences are not added.",
    ]
    report = {
        "version": 2, "summary": summary, "rename_groups": rename_groups,
        "rename_conflict_groups": rename_conflict_groups,
        "added_groups": added_groups, **audit,
        "rejected_subject_boundaries": rejected_boundaries,
        "readiness_notes": notes,
    }
    return hybrid, report


def report_phase3c_hybrid_preview(report):
    print("Phase 3C.2 guarded hybrid summary:")
    for key, value in report["summary"].items():
        print(f"{key}={value}")
    for row in report["rename_groups"]:
        print("Phase 3C.2 rename group: " + json.dumps(row, ensure_ascii=False))
    for row in report["added_groups"]:
        print("Phase 3C.2 added group: " + json.dumps(row, ensure_ascii=False))
    for row in report["rename_conflicts"]:
        print("Phase 3C.2 rename conflict: " + json.dumps(row, ensure_ascii=False))
    for row in report["rejected_subject_boundaries"]:
        print("Phase 3C.2 rejected subject boundary: " + json.dumps(row, ensure_ascii=False))


def save_phase3c_hybrid_preview(report):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(PHASE3C_HYBRID_PREVIEW_FILE, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)


class Phase3CCutoverValidationError(ValueError):
    """Raised when a Phase 3C candidate is unsafe for production."""


def _require_cutover(condition, message):
    if not condition:
        raise Phase3CCutoverValidationError(message)


def validate_phase3c_hybrid_cutover(legacy_entries, hybrid_entries, hybrid_report):
    """Validate all occurrence accounting before selecting the hybrid list."""
    _require_cutover(isinstance(legacy_entries, list), "legacy_entries must be a list")
    _require_cutover(isinstance(hybrid_entries, list), "hybrid_entries must be a list")
    _require_cutover(isinstance(hybrid_report, dict), "hybrid_report must be a dict")
    _require_cutover(hybrid_report.get("version") == 2, "hybrid report version must be 2")
    summary = hybrid_report.get("summary")
    _require_cutover(isinstance(summary, dict), "hybrid report summary must be a dict")

    for index, entry in enumerate(hybrid_entries):
        _require_cutover(isinstance(entry, dict), f"hybrid entry {index} must be a dict")
        for field in ("alt", "src"):
            _require_cutover(
                isinstance(entry.get(field), str) and bool(entry[field].strip()),
                f"hybrid entry {index} has invalid {field}",
            )

    count_fields = (
        "legacy_image_count", "hybrid_image_count",
        "confirmed_non_mushroom_removed_count",
        "confirmed_new_mushroom_added_count",
        "confirmed_mushroom_renamed_count", "compatible_rename_count",
    )
    for field in count_fields:
        _require_cutover(
            isinstance(summary.get(field), int) and not isinstance(summary[field], bool)
            and summary[field] >= 0,
            f"summary {field} must be a non-negative integer",
        )
    _require_cutover(summary["legacy_image_count"] == len(legacy_entries),
                     "legacy image count mismatch")
    _require_cutover(summary["hybrid_image_count"] == len(hybrid_entries),
                     "hybrid image count mismatch")
    expected_count = (len(legacy_entries)
                      - summary["confirmed_non_mushroom_removed_count"]
                      + summary["confirmed_new_mushroom_added_count"])
    _require_cutover(len(hybrid_entries) == expected_count,
                     "hybrid count accounting mismatch")

    removed = hybrid_report.get("removed_non_mushroom")
    added = hybrid_report.get("added_occurrences")
    renamed = hybrid_report.get("renamed_occurrences")
    conflicts = hybrid_report.get("rename_conflicts")
    for name, rows in (("removed_non_mushroom", removed), ("added_occurrences", added),
                       ("renamed_occurrences", renamed), ("rename_conflicts", conflicts)):
        _require_cutover(isinstance(rows, list), f"{name} must be a list")
        _require_cutover(all(isinstance(row, dict) for row in rows),
                         f"{name} rows must be dicts")
    _require_cutover(len(removed) == summary["confirmed_non_mushroom_removed_count"],
                     "removed occurrence count mismatch")
    _require_cutover(len(added) == summary["confirmed_new_mushroom_added_count"],
                     "added occurrence count mismatch")
    expected_srcs = Counter(entry.get("src") for entry in legacy_entries)
    removed_srcs = Counter(row.get("src") for row in removed)
    _require_cutover(not (removed_srcs - expected_srcs),
                     "removed src occurrences exceed legacy occurrences")
    expected_srcs.subtract(removed_srcs)
    expected_srcs += Counter(row.get("src") for row in added)
    _require_cutover(expected_srcs == Counter(entry["src"] for entry in hybrid_entries),
                     "hybrid src multiset accounting mismatch")

    _require_cutover(summary["confirmed_mushroom_renamed_count"]
                     == summary["compatible_rename_count"],
                     "rename summary counts disagree")
    _require_cutover(len(renamed) == summary["confirmed_mushroom_renamed_count"],
                     "renamed occurrence count mismatch")
    for row in renamed:
        _require_cutover(row.get("decision") == "compatible_rename",
                         "renamed occurrence has an incompatible decision")
        _require_cutover(isinstance(row.get("legacy_alt"), str)
                         and isinstance(row.get("detected_label"), str),
                         "renamed occurrence has invalid names")
        _require_cutover(normalize_taxonomy_key(row["legacy_alt"])
                         == normalize_taxonomy_key(row.get("detected_label")),
                         "renamed occurrence is taxonomy-incompatible")

    conflict_pairs = Counter()
    for row in conflicts:
        _require_cutover(row.get("decision") == "rename_conflict_manual_review",
                         "rename conflict has an unsafe decision")
        _require_cutover(isinstance(row.get("legacy_alt"), str),
                         "rename conflict has no legacy alt")
        conflict_pairs[(row.get("src"), row["legacy_alt"])] += 1
    hybrid_pairs = Counter((entry["src"], entry["alt"]) for entry in hybrid_entries)
    _require_cutover(not (conflict_pairs - hybrid_pairs),
                     "rename conflict did not preserve the legacy alt occurrence")

    for row in added:
        _require_cutover(row.get("subject_type") == "mushroom",
                         "added occurrence is not a mushroom")
        _require_cutover(isinstance(row.get("gallery_name"), str)
                         and bool(row["gallery_name"].strip()),
                         "added occurrence has no gallery name")
        _require_cutover(row.get("subject_state_status") == "accepted_subject",
                         "added occurrence is not from an accepted subject")
        _require_cutover(row.get("decision") == "confirmed_new_mushroom_added",
                         "added occurrence has an unsafe decision")

    # Reconcile names as an occurrence multiset too.  This prevents one of two
    # duplicate-src conflicts from being renamed while the other masks it.
    expected_pairs = Counter((entry.get("src"), entry.get("alt"))
                             for entry in legacy_entries)
    for row in removed:
        pair = (row.get("src"), row.get("legacy_alt"))
        _require_cutover(expected_pairs[pair] > 0,
                         "removed occurrence is not present in legacy entries")
        expected_pairs.subtract({pair: 1})
    for row in renamed:
        old_pair = (row.get("src"), row.get("legacy_alt"))
        new_pair = (row.get("src"), row.get("hybrid_alt"))
        _require_cutover(expected_pairs[old_pair] > 0,
                         "renamed occurrence is not present in legacy entries")
        expected_pairs.subtract({old_pair: 1})
        expected_pairs.update({new_pair: 1})
    for row in added:
        expected_pairs.update({(row.get("src"), row.get("gallery_name")): 1})
    expected_pairs += Counter()
    _require_cutover(expected_pairs == hybrid_pairs,
                     "hybrid alt occurrence accounting mismatch")

    return {"valid": True, "checks": {
        "report_version": True, "entry_schema": True,
        "count_accounting": True, "src_multiset_accounting": True,
        "rename_compatibility": True, "rename_conflict_preservation": True,
        "new_image_safety": True,
    }}


def save_phase3c_production_status(status):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(PHASE3C_PRODUCTION_STATUS_FILE, "w", encoding="utf-8") as stream:
        json.dump(status, stream, ensure_ascii=False, indent=2)

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
def generate_gallery(entries, exif_cache, detail_views=None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    copy_shared_assets()
    detail_views = detail_views or {}

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

        # Evidence-backed knowledge and article links follow the primary photo gallery.
        html_parts.append(render_detail_sections(detail_views.get(alt)))

        # 五十音タイル
        html_parts.append(group_links_html)

        # スタイル・LG・JS
        html_parts.append(STYLE_TAG)
        html_parts.append('<link rel="stylesheet" href="assets/detail.css">')
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
def generate_index(grouped, exif_cache, observation_records=None):
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
{'<link rel="stylesheet" href="assets/records.css">' if observation_records else ''}
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
    # EXIF撮影月による季節ポータル
    # ==========================================================
    index_parts.append("""
    <div class="section">
    <div class="feature-block">
      <h2 class="section-title">🗓️ 季節から探す</h2>
      <p class="section-desc">写真の撮影月から探せます</p>
      <a class="aiuo-link feature-action-link" href="season.html">春・夏・秋・冬から見る</a>
    </div>
    </div>
    """)


    if observation_records:
        index_parts.append(f"""
    <div class="section">
    <div class="feature-block">
      <h2 class="section-title">📔 観察記録</h2>
      <p class="section-desc">キノコ探索のブログ記事を新しい順に見られます</p>
      <div class="record-list record-list-preview">{render_record_cards(observation_records, limit=1)}</div>
      <a class="aiuo-link feature-action-link record-more-link record-external-link" href="https://exsudoporus-ruber.hatenablog.jp/" target="_top">観察記録をもっと見る</a>
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
    
      <a class="aiuo-link note-link feature-action-link" href="favorite.html">
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

    legacy_entries = fetch_images(article_files)
    if not legacy_entries:
        raise RuntimeError(
            "記事から画像を1件も抽出できなかったため、"
            "空のギャラリーで上書きしないよう生成を中止します。"
        )

    production_entries = legacy_entries
    production_mode = "legacy_fallback"
    fallback_reason = None
    hybrid_entries = None
    hybrid_report = None
    validation = None
    taxonomy = None
    shadow_metadata = None
    cutover_eligible = True
    try:
        try:
            taxonomy = load_subject_taxonomy()
        except Exception as error:
            fallback_reason = f"taxonomy load failed: {error}"
            cutover_eligible = False
            print(f"Phase 3B.2 taxonomy unavailable: {error}")
        shadow_metadata = extract_shadow_metadata(article_files, taxonomy=taxonomy)
        report_category_inventory(article_files)
        try:
            report_shadow_metadata(
                shadow_metadata, legacy_production_image_count=len(legacy_entries), taxonomy=taxonomy
            )
        except Exception as error:
            print(f"Phase 3B.2 taxonomy audit failed: {error}")
            cutover_eligible = False
            fallback_reason = f"shadow metadata audit failed: {error}"
        if taxonomy is not None:
            try:
                save_taxonomy_candidates(shadow_metadata)
            except (OSError, TypeError, ValueError) as error:
                print(f"Phase 3B.2 taxonomy candidate export failed: {error}")
        save_shadow_metadata(shadow_metadata)
        try:
            readiness_audit = build_phase3c_readiness(legacy_entries, shadow_metadata)
            report_phase3c_readiness(readiness_audit)
            save_phase3c_readiness(readiness_audit)
        except Exception as error:
            print(f"Phase 3C.0 readiness audit failed: {error}")
        if taxonomy is not None and cutover_eligible:
            try:
                hybrid_entries, hybrid_report = build_phase3c_hybrid_preview(
                    legacy_entries, shadow_metadata, load_article_metadata()
                )
            except Exception as error:
                fallback_reason = f"hybrid build failed: {error}"
                print(f"Phase 3C.2 guarded hybrid preview failed: {error}")
                print(f"Phase 3C.3 production fallback: {fallback_reason}")
            else:
                try:
                    report_phase3c_hybrid_preview(hybrid_report)
                except Exception as error:
                    print(f"Phase 3C.2 guarded hybrid preview report failed: {error}")
                try:
                    save_phase3c_hybrid_preview(hybrid_report)
                except Exception as error:
                    print(f"Phase 3C.2 guarded hybrid preview save failed: {error}")
                try:
                    validation = validate_phase3c_hybrid_cutover(
                        legacy_entries, hybrid_entries, hybrid_report
                    )
                except Exception as error:
                    fallback_reason = f"hybrid validation failed: {error}"
                    print(f"Phase 3C.3 production fallback: {fallback_reason}")
                else:
                    production_entries = hybrid_entries
                    production_mode = "phase3c_hybrid"
                    fallback_reason = None
        try:
            residual_audit = build_residual_gap_audit(article_files, shadow_metadata)
        except Exception as error:
            print(f"Phase 3B.4 residual gap audit failed: {error}")
        else:
            try:
                report_residual_gap_audit(residual_audit)
            except Exception as error:
                print(f"Phase 3B.4 residual gap audit failed: {error}")
            try:
                save_residual_gap_audit(residual_audit)
            except (OSError, TypeError, ValueError) as error:
                print(f"Phase 3B.4 residual gap audit export failed: {error}")
    except Exception as error:
        print(f"Phase 3B.2 shadow audit failed: {error}")
        fallback_reason = f"shadow metadata extraction failed: {error}"
        print(f"Phase 3C.3 production fallback: {fallback_reason}")

    status = {
        "version": 1, "production_mode": production_mode,
        "cutover_active": production_mode == "phase3c_hybrid",
        "fallback_reason": fallback_reason,
        "legacy_image_count": len(legacy_entries),
        "production_image_count": len(production_entries),
        "hybrid_candidate_image_count": (
            len(hybrid_entries) if hybrid_entries is not None else None
        ),
        "net_image_delta_vs_legacy": len(production_entries) - len(legacy_entries),
        "validation": validation,
        "hybrid_report_version": (
            hybrid_report.get("version") if isinstance(hybrid_report, dict) else None
        ),
    }
    print("Phase 3C.3 production mode:")
    print(f"production_mode={production_mode}")
    print(f"legacy_image_count={len(legacy_entries)}")
    print(f"production_image_count={len(production_entries)}")
    print(f"net_image_delta={len(production_entries) - len(legacy_entries)}")
    if fallback_reason is not None:
        print(f"fallback_reason={fallback_reason}")
    try:
        save_phase3c_production_status(status)
    except Exception as error:
        print(f"Phase 3C.3 production status save failed: {error}")

    exif_cache = load_exif_cache()
    exif_cache = build_exif_cache(production_entries, exif_cache)
    save_exif_cache(exif_cache)

    portal_status = export_portal_data(
        production_entries=production_entries,
        shadow_metadata=shadow_metadata or [],
        exif_cache=exif_cache,
        taxonomy=taxonomy,
        production_mode=production_mode,
    )
    generate_season_page_if_fresh(portal_status)
    observation_records = generate_records_page_if_fresh(portal_status)
    detail_views = build_detail_views_if_fresh(portal_status)

    # Keep test/extension callables with the historical two-argument signature usable.
    if "detail_views" in inspect.signature(generate_gallery).parameters:
        grouped = generate_gallery(production_entries, exif_cache, detail_views=detail_views)
    else:
        grouped = generate_gallery(production_entries, exif_cache)
    if observation_records:
        generate_index(grouped, exif_cache, observation_records=observation_records)
    else:
        generate_index(grouped, exif_cache)
    generate_favorite_page(grouped)


def generate_season_page_if_fresh(portal_status):
    """Best-effort UI output, gated on this run's successful portal export."""
    if not isinstance(portal_status, dict) or portal_status.get("build_ok") is not True:
        return False
    try:
        portal = load_fresh_portal_data(PORTAL_DATA_FILE)
        generate_season_page(portal, OUTPUT_DIR, ASSETS_DIR, safe_filename)
    except Exception as error:
        print(f"Phase 4A.1 season page generation failed: {error}")
        return False
    return True


def generate_records_page_if_fresh(portal_status):
    """Best-effort records output, gated on this run's successful export."""
    if not isinstance(portal_status, dict) or portal_status.get("build_ok") is not True:
        return []
    try:
        portal = load_fresh_portal_data(PORTAL_DATA_FILE)
        return generate_records_page(portal, OUTPUT_DIR, ASSETS_DIR)
    except Exception as error:
        print(f"Phase 4A.2 records page generation failed: {error}")
        return []


def build_detail_views_if_fresh(portal_status):
    """Best-effort detail models, gated on this run's successful export."""
    if not isinstance(portal_status, dict) or portal_status.get("build_ok") is not True:
        return {}
    try:
        return build_detail_views(load_fresh_portal_data(PORTAL_DATA_FILE))
    except Exception as error:
        print(f"Phase 4A.3 detail view generation failed: {error}")
        return {}


def export_portal_data(*, production_entries, shadow_metadata, article_metadata=None,
                       exif_cache, taxonomy, production_mode):
    """Best-effort supplemental export; no error may stop gallery generation."""
    try:
        if taxonomy is None:
            raise ValueError("subject taxonomy is unavailable")
        if article_metadata is None:
            article_metadata = load_article_metadata()
        data = build_portal_data(
            production_entries=production_entries,
            shadow_metadata=shadow_metadata,
            article_metadata=article_metadata,
            exif_cache=exif_cache,
            taxonomy=taxonomy,
            mushroom_master=load_mushroom_master(),
            sources=load_sources(),
            production_mode=production_mode,
            cutover_active=production_mode == "phase3c_hybrid",
        )
        save_json(PORTAL_DATA_FILE, data)
        status = success_status(data)
    except Exception as error:
        print(f"Phase 4A.0 portal data export failed: {error}")
        status = failure_status(error, production_mode, len(production_entries))
    try:
        save_json(PORTAL_DATA_STATUS_FILE, status)
    except Exception as error:
        print(f"Phase 4A.0 portal status save failed: {error}")
    return status


if __name__ == "__main__":
    build_gallery()
