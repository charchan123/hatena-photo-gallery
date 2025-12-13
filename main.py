# ============================================================
# main.py  [Mushroom Photo Gallery]
# 完成版：UI①〜⑦ + 検索UX進化（C）
# ============================================================

import os
import json
import re
import html
import requests
import piexif
from collections import defaultdict

# ---------------------------
# 設定
# ---------------------------
OUTPUT_DIR = "output"
CACHE_DIR = "cache"
EXIF_CACHE_FILE = os.path.join(CACHE_DIR, "exif-cache.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ---------------------------
# 表示用リスト
# ---------------------------
RARITY_LIST = ["センニンタケ"]
POPULAR_LIST = ["ベニテングタケ", "タマゴタケ", "シイタケ"]

AIUO_GROUPS = {
    "あ行": list("あいうえおアイウエオ"),
    "か行": list("かきくけこカキクケコがぎぐげご"),
    "さ行": list("さしすせそサシスセソざじずぜぞ"),
    "た行": list("たちつてとタチツテトだぢづでど"),
    "な行": list("なにぬねの"),
    "は行": list("はひふへほばびぶべぼぱぴぷぺぽ"),
    "ま行": list("まみむめも"),
    "や行": list("やゆよ"),
    "ら行": list("らりるれろ"),
    "わ行": list("わをん"),
}

# ---------------------------
# util
# ---------------------------
def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip() or "unnamed"

def load_exif_cache():
    if os.path.exists(EXIF_CACHE_FILE):
        with open(EXIF_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_exif_cache(cache):
    with open(EXIF_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# ============================================================
# STYLE_TAG（UI①〜⑦統一）
# ============================================================
STYLE_TAG = """
<style>
/* ---------- Base ---------- */
body {
  margin:0;
  padding:0;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Sans",sans-serif;
  background:#fafafa;
  color:#333;
}
a { text-decoration:none; color:inherit; }

/* ---------- Section ---------- */
.section {
  max-width:1100px;
  margin:40px auto;
  padding:0 16px;
}
.section-title {
  font-size:22px;
  font-weight:700;
  text-align:center;
  margin-bottom:20px;
}

/* ---------- Search UX (C) ---------- */
.search-box {
  max-width:520px;
  margin:0 auto 16px;
  position:relative;
}
.search-input {
  width:100%;
  padding:12px 14px;
  font-size:16px;
  border-radius:10px;
  border:1px solid #ccc;
}
.search-results {
  position:absolute;
  top:100%;
  left:0;
  right:0;
  background:#fff;
  border-radius:10px;
  box-shadow:0 6px 20px rgba(0,0,0,.15);
  overflow:hidden;
  z-index:10;
}
.search-item {
  display:flex;
  gap:10px;
  padding:10px;
  align-items:center;
  cursor:pointer;
}
.search-item:hover { background:#f3f3f3; }
.search-item img {
  width:48px;
  height:48px;
  object-fit:cover;
  border-radius:6px;
}
.search-name b { color:#e53935; }

/* ---------- Grid ---------- */
.grid {
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
  gap:16px;
}
.card {
  background:#fff;
  border-radius:12px;
  box-shadow:0 2px 10px rgba(0,0,0,.1);
  overflow:hidden;
  text-align:center;
}
.card img {
  width:100%;
  aspect-ratio:1/1;
  object-fit:cover;
}
.card-name {
  padding:10px;
  font-weight:600;
}

/* ---------- Footer ---------- */
.footer {
  text-align:center;
  font-size:13px;
  color:#888;
  margin:40px 0;
}
</style>
"""

# ============================================================
# EXIF：文字整形
# ============================================================
def clean_exif_str(s):
    if not s:
        return ""
    s = s.replace("\x00", "")
    s = re.sub(r"[�]+", "", s)
    return s.strip()

def normalize_model(model: str) -> str:
    if not model:
        return ""
    m = model.strip()
    if m.startswith("Canon "):
        m = m[len("Canon "):]
    return m

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

# ============================================================
# EXIF 抽出（URL画像の bytes -> dict）
# ============================================================
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

# ============================================================
# EXIFキャッシュ構築（entries: [{alt,src}]）
# ============================================================
def build_exif_cache(entries, cache: dict):
    all_srcs = sorted({e["src"] for e in entries})
    for src in all_srcs:
        if src in cache:
            continue

        print(f"🔍 EXIF取得: {src}")
        exif_data = {}
        try:
            r = requests.get(src, timeout=15)
            if r.status_code == 200:
                exif_data = extract_exif_from_bytes(r.content) or {}
                print(f"  ↪ OK: {exif_data}")
            else:
                print(f"  ↪ HTTP {r.status_code} → 空保存")
        except Exception as e:
            print(f"  ↪ 取得エラー: {e} → 空保存")

        cache[src] = exif_data

    return cache

# ============================================================
# LightGallery 読み込みタグ
# ============================================================
LIGHTGALLERY_TAGS = """
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/css/lightgallery-bundle.min.css">
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/lightgallery.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/zoom/lg-zoom.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/thumbnail/lg-thumbnail.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/autoplay/lg-autoplay.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/share/lg-share.min.js"></script>
"""

# ============================================================
# SCRIPT_TAG
# ============================================================
SCRIPT_TAG = """
<script>
document.addEventListener("DOMContentLoaded", () => {

  /* ============================
     index.html 検索UX（進化C）
  ============================ */
  const input = document.querySelector(".index-search-input");
  const suggest = document.querySelector(".search-suggest");
  const ALL = window.ALL_MUSHROOMS || [];

  if (input && suggest) {
    function highlight(name, q) {
      const i = name.toLowerCase().indexOf(q);
      if (i === -1) return name;
      return name.slice(0, i) +
        "<mark>" + name.slice(i, i + q.length) + "</mark>" +
        name.slice(i + q.length);
    }

    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      if (!q) {
        suggest.innerHTML = "";
        return;
      }

      const hits = ALL
        .filter(m => m.name_norm.includes(q))
        .slice(0, 7);

      suggest.innerHTML = hits.map(m => `
        <a href="${m.href}" class="suggest-item">
          <img src="${m.thumb}">
          <span>${highlight(m.name, q)}</span>
        </a>
      `).join("");
    });
  }

});
</script>
"""

# ============================================================
# caption（EXIF行は「溶け込む」& 重ならない前提）
# ※ ここでは exif-bottom-row を使う
# ============================================================
def build_caption_html(alt, exif: dict):
    title = html.escape(alt)

    model = exif.get("model") or ""
    lens = exif.get("lens") or ""
    iso = exif.get("iso") or ""
    f = exif.get("f") or ""
    exposure = exif.get("exposure") or ""
    focal = exif.get("focal") or ""
    date = exif.get("date") or ""

    # 2行目
    middle_parts = []
    if model:
        middle_parts.append(model)
    if lens:
        middle_parts.append(lens)
    middle_text = " / ".join(middle_parts)

    # 3行目：gap方式（dateもここに溶け込ませる）
    spans = []
    if focal:
        spans.append(f"<span>{html.escape(focal)}</span>")
    if f:
        spans.append(f"<span>{html.escape(f)}</span>")
    if exposure:
        exp_str = exposure if exposure.endswith("s") else f"{exposure}s"
        spans.append(f"<span>{html.escape(exp_str)}</span>")
    if iso:
        spans.append(f"<span>ISO{html.escape(iso)}</span>")
    if date:
        spans.append(f"<span>{html.escape(date)}</span>")

    bottom_html = ""
    if spans:
        # indexページ/個別ページのSTYLE_TAGに exif-bottom-row が無い場合でも崩れないように
        bottom_html = f"<div class='exif-bottom-row'>{''.join(spans)}</div>"

    html_block = "<div class='exif-wrap'>"
    html_block += f"<div class='exif-title'>{title}</div>"
    if middle_text:
        html_block += f"<div class='exif-middle'>{html.escape(middle_text)}</div>"
    if bottom_html:
        html_block += bottom_html
    html_block += "</div>"

    return html.escape(html_block, quote=True)

# ============================================================
# 五十音分類
# ============================================================
def get_aiuo_group(name: str) -> str:
    if not name:
        return "その他"
    first = name[0]
    for group, chars in AIUO_GROUPS.items():
        if first in chars:
            return group
    return "その他"

# ============================================================
# キノコ個別ページ生成
# entries: [{alt, src}]
# grouped: alt -> [src...]
# ============================================================
def generate_mushroom_pages(grouped, exif_cache, SCRIPT_TAG):
    for alt, imgs in grouped.items():
        parts = []

        # タイトル（キノコ名 + 枚数）
        parts.append(
            f"<div class='section'>"
            f"<div class='section-title'>{html.escape(alt)} "
            f"<span style='font-size:14px;font-weight:400;color:#666;'>— {len(imgs)} photos</span>"
            f"</div>"
            f"</div>"
        )

        # ギャラリー（カードではなく LightGallery 用リンク）
        parts.append("<div class='section'>")
        parts.append("<div class='grid gallery'>")
        for src in imgs:
            thumb = src + "?width=400"
            exif = exif_cache.get(src, {}) or {}
            caption_attr = build_caption_html(alt, exif)

            parts.append(
                f'<a class="gallery-item card" href="{src}" '
                f'data-exthumbimage="{thumb}" '
                f'data-sub-html="{caption_attr}">'
                f'<img src="{thumb}" alt="{html.escape(alt)}" loading="lazy">'
                f'<div class="card-name">{html.escape(alt)}</div>'
                f'</a>'
            )
        parts.append("</div></div>")

        # 戻る
        parts.append("<div class='footer'><a href='javascript:history.back()'>← 戻る</a></div>")

        # CSS / LG / JS
        parts.append(STYLE_TAG)
        parts.append(LIGHTGALLERY_TAGS)
        parts.append(SCRIPT_TAG)

        out = "".join(parts)
        with open(os.path.join(OUTPUT_DIR, f"{safe_filename(alt)}.html"), "w", encoding="utf-8") as f:
            f.write(out)

        print(f"✅ 個別ページ生成: {alt}")

# ============================================================
# index.html 生成（UI統一 + 検索UX進化 C）
# ============================================================
def generate_index(grouped, exif_cache, SCRIPT_TAG):
    index = []

    # ----------------------------
    # セクション①：全キノコ横断検索
    # ----------------------------
    index.append("""
<div class="section">
  <div class="section-title">🔍 全キノコ横断検索</div>
  <div class="search-wrap">
    <input type="text"
           class="index-search-input"
           placeholder="キノコ名で検索（例：ベニテングタケ）">
    <div class="search-suggest"></div>
  </div>
</div>
""")

    # JS 用データ
    all_items = []
    for alt, srcs in grouped.items():
        if not srcs:
            continue
        all_items.append({
            "name": alt,
            "name_norm": alt.lower(),
            "href": f"{safe_filename(alt)}.html",
            "thumb": srcs[0] + "?width=300"
        })

    index.append(f"""
<script>
window.ALL_MUSHROOMS = {json.dumps(all_items, ensure_ascii=False)};
</script>
""")

    # ----------------------------
    # セクション②：五十音別分類
    # ----------------------------
    index.append("""
<div class="section">
  <div class="section-title">五十音別分類</div>
  <div class="aiuo-links">
""")

    for g in AIUO_GROUPS.keys():
        index.append(
            f'<a class="aiuo-link" href="{safe_filename(g)}.html">{g}</a>'
        )

    index.append("""
  </div>
</div>
""")

    # ----------------------------
    # セクション③：おすすめキノコ
    # ----------------------------
    def pick(names):
        cards = []
        for n in names:
            if n in grouped and grouped[n]:
                cards.append({
                    "name": n,
                    "thumb": grouped[n][0] + "?width=400",
                    "href": f"{safe_filename(n)}.html"
                })
        return cards[:3]

    # 最新順（撮影日）
    latest = {}
    for alt, srcs in grouped.items():
        best = ""
        for s in srcs:
            d = (exif_cache.get(s, {}) or {}).get("date") or ""
            k = d.replace("/", "")
            if len(k) == 8 and k > best:
                best = k
        if best:
            latest[alt] = best

    new_names = [k for k, _ in sorted(latest.items(), key=lambda x: x[1], reverse=True)]
    rec_new = pick(new_names)
    rec_rare = pick(RARITY_LIST)
    rec_pop = pick(POPULAR_LIST)

    index.append("""
<div class="section">
  <div class="section-title">おすすめキノコ</div>
  <div class="recommend-grid">
""")

    def render_block(title, items):
        index.append(f"<div class='recommend-block'><h3>{title}</h3>")
        for it in items:
            index.append(f"""
<a class="card" href="{it['href']}">
  <img src="{it['thumb']}" alt="{it['name']}">
  <div class="card-name">{it['name']}</div>
</a>
""")
        index.append("</div>")

    render_block("新着キノコ", rec_new)
    render_block("珍しいキノコ", rec_rare)
    render_block("人気キノコ", rec_pop)

    index.append("</div></div>")

    # ----------------------------
    # CSS / LightGallery / JS
    # ----------------------------
    index.append(STYLE_TAG)
    index.append(LIGHTGALLERY_TAGS)
    index.append(SCRIPT_TAG)

    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write("".join(index))

    print("✅ index.html 生成完了")
