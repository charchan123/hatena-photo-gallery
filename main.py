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

if not all([HATENA_USER, HATENA_BLOG_ID, HATENA_API_KEY]):
    raise EnvironmentError("環境変数 HATENA_USER / HATENA_BLOG_ID / HATENA_API_KEY が未設定です。")

ARTICLES_DIR = "articles"
OUTPUT_DIR = "output"

# ====== EXIF キャッシュ設定 ======
CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "exif-cache.json")

# ====== API ======
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

# ====== 共通スタイル（EXIF gap レイアウト採用版） ======
STYLE_TAG = """<style>
html, body {
  margin: 0;
  padding: 0;
  overflow-y: auto;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background:#fafafa;
  color:#333;
  padding:16px;
  box-sizing:border-box;
  opacity: 0;
  transition: opacity .25s ease;
}

/* ======== ギャラリー本体（PC4列・スマホ3列） ======== */
.gallery {
  column-count: 4;
  column-gap: 4px;
  max-width: 900px;
  margin: 0 auto;
  visibility: hidden;
}

.gallery a.gallery-item{
  display: block;
  break-inside: avoid;
  margin-bottom: 4px;
  border-radius: 0;
  overflow: hidden;
  position: relative;
}

/* ===== 画像基本 ===== */
.gallery img {
  width: 100%;
  height: auto;
  display: block;
  cursor: zoom-in;
  opacity: 0;
  transform: translateY(10px);
  transition: opacity 0.6s ease, transform 0.6s ease;
}

.gallery img.visible {
  opacity: 1;
  transform: translateY(0);
}

/* ===== hover：微ズーム ===== */
.gallery a.gallery-item img {
  transition:
    transform 0.5s cubic-bezier(.2,.8,.2,1),
    filter 0.4s ease;
  will-change: transform;
}

.gallery a.gallery-item:hover img {
  transform: scale(1.06);
  filter: brightness(1.08);
}

/* ===== hover：暗幕 ===== */
.gallery a.gallery-item::after {
  content: "";
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.08);
  opacity: 0;
  transition: opacity 0.35s ease;
  pointer-events: none;
}

.gallery a.gallery-item:hover::after {
  opacity: 1;
}

/* =====================================================
   ★ 胞子エフェクト（hover時にふわっ）
===================================================== */
.gallery a.gallery-item .spores {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.gallery a.gallery-item .spores::before,
.gallery a.gallery-item .spores::after {
  content: "";
  position: absolute;
  width: 6px;
  height: 6px;
  background: rgba(255,255,255,0.8);
  border-radius: 50%;
  opacity: 0;
  filter: blur(0.5px);
}

.gallery a.gallery-item:hover .spores::before {
  left: 30%;
  top: 70%;
  animation: sporeFloat 1.6s ease-out forwards;
}

.gallery a.gallery-item:hover .spores::after {
  left: 60%;
  top: 80%;
  animation: sporeFloat 1.9s ease-out forwards;
}

@keyframes sporeFloat {
  0% {
    transform: translateY(0) scale(0.6);
    opacity: 0;
  }
  30% {
    opacity: 0.9;
  }
  100% {
    transform: translateY(-40px) scale(1.4);
    opacity: 0;
  }
}

/* =====================================================
   ★ タップ時 波紋エフェクト（スマホ）
===================================================== */
.gallery a.gallery-item::before {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  width: 120%;
  padding-top: 120%;
  background: rgba(255,255,255,0.35);
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(0);
  opacity: 0;
  pointer-events: none;
}

.gallery a.gallery-item:active::before {
  animation: rippleTap 0.45s ease-out;
}

@keyframes rippleTap {
  0% {
    transform: translate(-50%, -50%) scale(0);
    opacity: 0.5;
  }
  70% {
    opacity: 0.25;
  }
  100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0;
  }
}

/* =====================================================
   ★ LightGallery：フルスクリーン時
   フェード＋微ズーム
===================================================== */
.lg-current .lg-object {
  animation: lgFadeZoom 0.45s ease;
}

@keyframes lgFadeZoom {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* ===== スマホ〜タブレット ===== */
@media (max-width: 580px) {
  .gallery {
    column-count: 3;
    column-gap: 3px;
  }
  .gallery a.gallery-item{
    margin-bottom: 3px;
  }
}

/* ===== 五十音タイル・カードUI ===== */
.kana-grid {
  max-width: 900px;
  margin: 0 auto 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}
.kana-btn {
  min-width: 32px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid #d0d0d0;
  background: #fff;
  font-size: 14px;
  cursor: pointer;
  line-height: 1;
  transition: background .15s ease, box-shadow .15s ease, transform .15s ease, border-color .15s ease;
}
.kana-btn:hover {
  background: #f5f5f7;
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
  transform: translateY(-1px);
}
.kana-btn.active {
  background: #0f62fe;
  color: #fff;
  border-color: #0f62fe;
}

/* 検索バー */
.search-wrap {
  max-width: 900px;
  margin: 0 auto 16px;
}
.search-input {
  width: 100%;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid #ccc;
  font-size: 14px;
  box-sizing: border-box;
  background: #fff;
}

/* カード一覧 */
.mushroom-list {
  max-width: 900px;
  margin: 0 auto 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.mushroom-card {
  display: block;
  text-decoration: none;
  color: #333;
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
}
.mushroom-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.16);
  filter: brightness(1.05);
}
.mushroom-card-thumb {
  position: relative;
  padding-top: 65%;
  overflow: hidden;
  background: #eee;
}
.mushroom-card-thumb img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.mushroom-card-name {
  padding: 8px 10px 10px;
  font-size: 14px;
  font-weight: 600;
  text-align: center;
}

/* ===== index.html 専用：全キノコ横断検索 ===== */
.section {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 8px;
}
.section-title {
  text-align: center;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 12px;   /* ← タイトルとカードの距離 */
  letter-spacing: 0.04em;
}
/* 検索ボックスはフラットに */
.index-search-box {
  background: transparent;
  box-shadow: none;
  padding: 0;
}
.index-search-input {
  width: 100%;
  padding: 10px 16px;
  border-radius: 999px;
  border: 2px solid #007acc;
  font-size: 15px;
  box-sizing: border-box;
  background: #fdfefe;
}
.index-search-results {
  max-width: 900px;
  margin: 20px auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.index-pagination {
  max-width: 900px;
  margin: 16px auto;
  text-align: center;
}
.index-page-btn {
  display: inline-block;
  margin: 0 6px;
  padding: 6px 16px;
  border-radius: 999px;
  background: #333;
  color: #fff;
  font-size: 14px;
  text-decoration: none;
  cursor: pointer;
  transition: background .15s ease, transform .15s ease, box-shadow .15s ease;
}
.index-page-btn:hover:not(.disabled) {
  background: #555;
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(0,0,0,0.16);
}
.index-page-btn.disabled {
  opacity: 0.4;
  pointer-events: none;
}

/* =========================
   セクション共通カード
========================= */
.section-card {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;   /* ← カードの下余白（ここで統一） */
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.25s ease;
}

/* PC */
/*
@media (min-width: 768px) {
  .section-card {
    padding: 18px 16px;
  }
}
*/

/* ==== おすすめ3キノコカード ==== */
.recommend-grid {
  max-width: 900px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
}
.recommend-card {
  background: #fff;
  padding: 16px;
  border-radius: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.recommend-card h3 {
  font-size: 18px;
  margin-bottom: 12px;
  text-align: center;
}
.rec-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rec-item {
  display: flex;
  gap: 8px;
  align-items: center;
  text-decoration: none;
  color: #333;
  transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
  border-radius: 14px;
  padding: 4px 6px;
}
.rec-item:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 18px rgba(0,0,0,0.16);
  filter: brightness(1.04);
}
.rec-item img {
  width: 70px;
  height: 70px;
  border-radius: 12px;
  object-fit: cover;
}

/* index.html & キノコページ共通：五十音リンクタイル */
.aiuo-links {
  max-width: 900px;
  margin: 0 auto 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}
.aiuo-link {
  display: inline-block;
  padding: 8px 14px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e0e0e0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  text-decoration: none;
  color: #333;
  font-size: 14px;
  transition: transform .15s ease, box-shadow .15s ease, background .15s ease, border-color .15s ease;
}
.aiuo-link:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0,0,0,0.14);
  background: #e8f2ff;
  border-color: #c5dafe;
}

/* ===== 戻るボタン（楕円ボタン） ===== */
.back-btn {
  display: inline-block;
  padding: 10px 22px;
  background: #ffffffc9;
  border: 2px solid #ddd;
  border-radius: 999px;
  font-size: 15px;
  text-decoration: none;
  color: #333;
  font-weight: 600;
  transition: all 0.2s ease;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  backdrop-filter: blur(4px);
  cursor: pointer;
}
.back-btn:hover {
  background: #f0f0f0;
  border-color: #bbb;
  transform: translateY(-1px);
}
.back-btn:active {
  transform: translateY(1px);
  background: #e5e5e5;
}

/* ===== LightGallery EXIF（gap レイアウト） ===== */

/* 全体キャプション領域 */
.exif-wrap {
  width: 95%;
  max-width: 720px;
  margin: 0 auto;
  padding-top: 10px;
  text-align: center;
  color: #fff;
}

/* 1行目：キノコ名 */
.exif-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 6px;
  color: #fff;
}

/* 2行目：カメラ名 / レンズ名 */
.exif-middle {
  font-size: 15px;
  font-weight: 400;
  opacity: 0.9;
  color: #fff;
  margin-bottom: 6px;
}

/* 3行目：焦点距離 / F値 / SS / ISO / 日付（gap方式） */
.exif-bottom-row {
  display: inline-flex;
  gap: 8px;                   /* 半角スペース2個分くらいの距離 */
  justify-content: center;
  align-items: center;
  font-size: 14px;
  font-weight: 300;
  color: #ddd;
  opacity: 0.8;
  margin-bottom: 4px;
  flex-wrap: wrap;            /* スマホで自然に折り返す */
}
.exif-bottom-row span {
  white-space: nowrap;        /* 個々の項目は分割しない */
}

/* 右下固定の撮影日表示は廃止（スマホで重なるため） */
/* .exif-date-fixed { ... } は使わない */

.lg-sub-html {
  position: relative;
}

/* ===== 検索結果が空のときの余白除去 ===== */
.index-search-results:empty,
.index-pagination:empty {
  margin: 0;
  padding: 0;
}

/* ===== 検索結果アニメーション ===== */
.search-result-item {
  opacity: 0;
  transform: translateY(8px);
  animation: fadeUp 0.35s ease forwards;
}

@keyframes fadeUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===== 検索0件表示 ===== */
.search-empty {
  text-align: center;
  color: #777;
  font-size: 14px;
  padding: 16px 0;
  line-height: 1.6;
}
.search-empty small {
  font-size: 12px;
  color: #999;
}

/* 押した瞬間 */
.aiuo-link:active {
  transform: scale(0.94);
  box-shadow: 0 1px 2px rgba(0,0,0,0.12);
  background: #e0ebff;
}

/* 選択中（今見ている行） */
.aiuo-link.current {
  background: #0f62fe;
  color: #fff;
  border-color: #0f62fe;
  box-shadow: 0 4px 12px rgba(15,98,254,0.35);
}

mark {
  background: #ffe58f;
  padding: 0 2px;
  border-radius: 4px;
}

/* お気に入りボタン（LightGallery toolbar） */
.lg-fav-btn {
  font-size: 22px;
  line-height: 1;
  color: #ffd54f;
  cursor: pointer;
}

.lg-fav-btn:hover {
  transform: scale(1.15);
}

/* =========================
   ★ お気に入り：白固定（最重要）
========================= */

/* ☆ 状態だけグレー */
.lg-fav-btn:not(.is-fav) {
  color: #b5b5b5;
}

/* hoverしても★は白を維持 */
.lg-fav-btn.is-fav:hover {
  color: #ffffff !important;
}

/* =========================
   ★ お気に入り：白固定（最終確定版）
========================= */

/* 未お気に入り（☆） */
.lg-toolbar .lg-fav-btn:not(.is-fav) {
  color: #b5b5b5 !important;
}

/* お気に入り（★）は常に白 */
.lg-toolbar .lg-fav-btn.is-fav,
.lg-toolbar .lg-fav-btn.is-fav:hover,
.lg-toolbar .lg-fav-btn.is-fav:focus,
.lg-toolbar .lg-fav-btn.is-fav:active {
  color: #ffffff !important;
}

/* =========================
   サムネイル用 ★ オーバーレイ
========================= */
.gallery-item {
  position: relative;
}

/* ★ 本体 */
.thumb-fav {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 3;

  font-size: 18px;
  line-height: 1;
  color: #b5b5b5;

  background: rgba(0,0,0,0.35);
  backdrop-filter: blur(4px);
  border-radius: 999px;
  padding: 4px 6px;

  cursor: pointer;
  user-select: none;
}

/* お気に入り状態 */
.thumb-fav.is-fav {
  color: #ffffff;
}

/* hover演出（軽め） */
.thumb-fav:hover {
  transform: scale(1.1);
}

/* =========================
   カード用 ★（五十音 / index）
========================= */
.mushroom-card-thumb {
  position: relative;
}

.card-fav {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 3;

  font-size: 16px;
  line-height: 1;
  color: #b5b5b5;

  background: rgba(0,0,0,0.35);
  backdrop-filter: blur(4px);
  border-radius: 999px;
  padding: 4px 6px;

  user-select: none;
  cursor: default;
}

.card-fav.is-fav {
  color: #ffffff;
}

.card-fav:hover {
  transform: scale(1.1);
}

/* =========================
   観察ノート通知（トースト）
========================= */
.fav-toast {
  position: fixed;
  left: 50%;
  bottom: 30px;
  transform: translateX(-50%);
  background: rgba(30,30,30,0.9);
  color: #fff;
  padding: 10px 18px;
  border-radius: 999px;
  font-size: 14px;
  box-shadow: 0 8px 20px rgba(0,0,0,0.3);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease, transform 0.3s ease;
  z-index: 9999;
}

.fav-toast.show {
  opacity: 1;
  transform: translateX(-50%) translateY(-6px);
}
</style>"""

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
<script>
document.addEventListener("DOMContentLoaded", () => {

  // =========================
// ⭐ お気に入り保存キー
// =========================
  const LG_FAVORITES_KEY = "lg_favorites";

  // ページ全体フェードイン
  requestAnimationFrame(() => {
    document.body.style.opacity = "1";
  });

  function escapeRegExp(str) {
    return str.replace(/[-\\/\\^$*+?.()|[\\]{}]/g, "\\\\$&");
  }

// =========================
// ★ お気に入り機能
// =========================

  function getCurrentSlideSrc() {
  const img = document.querySelector(".lg-current .lg-object");
  return img ? normalizeSrc(img.getAttribute("src")) : null;
}

function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem(LG_FAVORITES_KEY)) || {};
  } catch (e) {
    return {};
  }
}

function saveFavorites(data) {
  localStorage.setItem(LG_FAVORITES_KEY, JSON.stringify(data));
}

// =========================
// ★ お気に入りボタンを toolbar に後付け
// =========================
function attachFavoriteButton() {
  const toolbar = document.querySelector(".lg-toolbar");
  if (!toolbar) return;

  // 二重追加防止
  if (toolbar.querySelector(".lg-fav-btn")) return;

  const btn = document.createElement("button");
  btn.className = "lg-icon lg-fav-btn";
  btn.title = "お気に入り";
  btn.textContent = "☆";

  btn.addEventListener("click", () => {
    const src = getCurrentSlideSrc();
    if (!src) return;

    const favs = loadFavorites();
    favs[src] = !favs[src];
    saveFavorites(favs);

    updateFavoriteIcon();

    showFavToast(
      favs[src]
        ? "📓 観察ノートに追加しました"
        : "📓 観察ノートから外しました"
    );
  });

  toolbar.appendChild(btn);
}

// =========================
// ★ お気に入り状態更新（スライドごと）
// =========================
function updateFavoriteIcon() {
  const btn = document.querySelector(".lg-fav-btn");
  if (!btn) return;

  const src = getCurrentSlideSrc();
  const favs = loadFavorites();

  if (favs[src]) {
    btn.textContent = "★";
    btn.classList.add("is-fav");
  } else {
    btn.textContent = "☆";
    btn.classList.remove("is-fav");
  }
}

// =========================
// ★ お気に入り状態反映関数（サムネ）
// =========================
function updateThumbnailFavorites() {
  const favs = loadFavorites();

  document.querySelectorAll(".gallery-item").forEach(a => {
    const img = a.querySelector("img");
    const star = a.querySelector(".thumb-fav");
    if (!img || !star) return;

    const src = normalizeSrc(img.getAttribute("src"));
    if (favs[src]) {
      star.textContent = "★";
      star.classList.add("is-fav");
    } else {
      star.textContent = "☆";
      star.classList.remove("is-fav");
    }
  });
}

// =========================
// ★ お気に入りクリック処理時ギャラリー起動キャンセル（サムネ）
// =========================
function bindThumbnailStarEvents() {
  document.querySelectorAll(".thumb-fav").forEach(star => {
    if (star.__favBound) return;
    star.__favBound = true;

    star.addEventListener("click", e => {
      e.preventDefault();
      e.stopPropagation();

      const item = star.closest(".gallery-item");
      const img = item?.querySelector("img");
      if (!img) return;

      const src = normalizeSrc(img.getAttribute("src"));
      const favs = loadFavorites();

      favs[src] = !favs[src];
      saveFavorites(favs);

      updateThumbnailFavorites();

      showFavToast(
        favs[src]
          ? "📓 観察ノートに追加しました"
          : "📓 観察ノートから外しました"
      );
    });
  });
}

// =========================
// ★ indexカードお気に入り更新関数
// =========================
function updateCardFavorites() {
  const favs = loadFavorites();

  document.querySelectorAll(".mushroom-card").forEach(card => {
    const img = card.querySelector("img");
    const star = card.querySelector(".card-fav");
    if (!img || !star) return;

    const src = normalizeSrc(img.getAttribute("src"));
    if (favs[src]) {
      star.textContent = "★";
      star.classList.add("is-fav");
    } else {
      star.textContent = "☆";
      star.classList.remove("is-fav");
    }
  });
}

// =========================
// 「観察ノートに追加しました」メッセージ表示
// =========================
function showFavToast(message) {
  let toast = document.querySelector(".fav-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "fav-toast";
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.classList.add("show");

  // ★ ここを追加
  toast.scrollIntoView({ block: "center", behavior: "smooth" });

  clearTimeout(toast.__timer);
  toast.__timer = setTimeout(() => {
    toast.classList.remove("show");
  }, 1500);
}

// =========================
// src 正規化関数
// =========================
function normalizeSrc(src) {
  return src ? src.replace(/\?.*$/, "") : "";
}

// =========================
// ★ 文脈リンク：五十音 → 詳細ページ（安全追加・最終形）
// =========================
  (function () {
    const params = new URLSearchParams(location.search);
    const from = params.get("from");
    const kana = params.get("kana");

    if (from !== "aiuo" || !kana) return;

    // 既存の「← 戻る」ボタンがあれば削除（保険）
    document.querySelectorAll(".back-btn").forEach(b => b.remove());

    const nav = document.createElement("div");
    nav.style.textAlign = "center";
    nav.style.marginTop = "40px";

    nav.innerHTML = `
      <a href="${kana}.html" class="back-btn">
        ◀ ${kana}の一覧に戻る
      </a>
    `;

    /**
     * 差し込み位置は「ギャラリー直後」
     * → UX的にも、scrollToTitle 的にも一番安全
     */
    const gallery = document.querySelector(".gallery");
    if (gallery) {
      gallery.after(nav);
    } else {
      // フォールバック（ほぼ起きない）
      document.body.appendChild(nav);
    }

    // iframe 高さを即再計算（既存ロジックを壊さない）
    if (typeof sendHeight === "function") {
      sendHeight();
    }
  })();

// =========================
// ★ パンくずリスト（完全統合・1系統）
// =========================
(function () {
  const params = new URLSearchParams(location.search);
  const from = params.get("from");
  const kana = params.get("kana");

  const title = document.querySelector("h2");
  if (!title) return;

  let crumbHTML = "";

  // =========================
  // ① 〇行のキノコページ（あ行.html など）
  // =========================
  const pathMatch = location.pathname.match(/\/([^\/]+行)\.html$/);
  if (pathMatch && !from) {
    const k = pathMatch[1];
    crumbHTML = `
      <a href="index.html">トップ</a>
      <span> › </span>
      <span>五十音</span>
      <span> › </span>
      <span style="color:#999;">${k}</span>
    `;
  }

  // =========================
  // ② キノコ詳細ページ
  // =========================
  else if (from === "aiuo" && kana) {
    crumbHTML = `
      <a href="index.html">トップ</a>
      <span> › </span>
      <a href="${kana}.html">五十音 › ${kana}</a>
      <span> › </span>
      <span style="color:#999;">${title.textContent}</span>
    `;
  }
  else if (from === "index") {
    crumbHTML = `
      <a href="index.html">トップ</a>
      <span> › </span>
      <a href="index.html">全キノコ検索</a>
      <span> › </span>
      <span style="color:#999;">${title.textContent}</span>
    `;
  }
  else if (from === "recommend") {
    crumbHTML = `
      <a href="index.html">トップ</a>
      <span> › </span>
      <a href="index.html#recommend">おすすめキノコ</a>
      <span> › </span>
      <span style="color:#999;">${title.textContent}</span>
    `;
  }
  else {
    return; // 直アクセスは出さない
  }

  const nav = document.createElement("nav");
  nav.style.textAlign = "center";
  nav.style.fontSize = "13px";
  nav.style.margin = "8px 0 16px";
  nav.style.color = "#666";
  nav.innerHTML = crumbHTML;

  title.before(nav);

  if (typeof sendHeight === "function") sendHeight();
})();

  function highlight(text, q) {
    if (!q) return text;
    const escaped = escapeRegExp(q);
    return text.replace(
      new RegExp("(" + escaped + ")", "ig"),
      "<mark>$1</mark>"
    );
  }

  function sendHeight() {
    const height = Math.max(
      document.body.scrollHeight,
      document.body.offsetHeight,
      document.documentElement.scrollHeight,
      document.documentElement.offsetHeight
    );
    window.parent.postMessage({ type: "setHeight", height }, "*");
  }

  // =========================
  // ギャラリー処理（既存）
  // =========================
  const gallery = document.querySelector(".gallery");
  if (gallery && !gallery.classList.contains("favorite-gallery")) {
    const fadeObs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add("visible");
          fadeObs.unobserve(e.target);
        }
      });
    }, { threshold: 0.1 });

    gallery.querySelectorAll("img").forEach(img => fadeObs.observe(img));

    imagesLoaded(gallery, () => {
      gallery.style.visibility = "visible";
      updateThumbnailFavorites(); // ← 追加
      updateCardFavorites();
      bindThumbnailStarEvents(); // ← 追加
      sendHeight();
      
    const lg = lightGallery(gallery, {
      selector: "a.gallery-item",
      plugins: [lgZoom, lgThumbnail, lgShare, lgAutoplay],
    
      speed: 400,
    
      thumbnail: true,
      showThumbByDefault: true,   // ← これが超重要
      toggleThumb: true,          // ← これも重要
    
      thumbWidth: 80,
      thumbMargin: 6,
    
      download: false,
      zoom: true,
      autoplay: true,
      pause: 3000,
      progressBar: true,
    });

  // =========================
  // お気に入り機能をLightGalleryイベントに接続
  // =========================

    gallery.addEventListener("lgAfterOpen", () => {
      attachFavoriteButton();
      updateFavoriteIcon();
      updateThumbnailFavorites(); // ← 追加
      document.querySelector(".lg-fav-btn")?.classList.toggle(
        "is-fav",
        !!loadFavorites()[getCurrentSlideSrc()]
      );
    });
    
    gallery.addEventListener("lgAfterSlide", () => {
      updateFavoriteIcon();
      updateThumbnailFavorites(); // ← 追加
    });

      gallery.querySelectorAll("a.gallery-item").forEach(a => {
        a.addEventListener("click", () => {
          const el = document.documentElement;
          if (el.requestFullscreen) el.requestFullscreen();
          else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
          else if (el.msRequestFullscreen) el.msRequestFullscreen();
        });
      });

    gallery.addEventListener("lgBeforeClose", () => {
      updateThumbnailFavorites(); // ← 即同期
      updateCardFavorites();
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
      window.parent.postMessage({ type: "lgClosed" }, "*");
    });

    gallery.addEventListener("lgAfterClose", () => {
      updateThumbnailFavorites();
    });

      document.addEventListener("fullscreenchange", () => {
        if (!document.fullscreenElement) {
          try {
            lg.closeGallery();
            window.parent.postMessage({ type: "lgClosed" }, "*");
          } catch (e) {}
        }
      });
    });
  }

  // =========================
  // scrollToTitle 判定（既存）
  // =========================
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;

    const txt = a.textContent || "";
    const href = a.getAttribute("href") || "";
    
    if (/\.html(\?|$)/.test(href)) {
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }

    if (/^(あ行|か行|さ行|た行|な行|は行|ま行|や行|ら行|わ行)$/.test(txt)) {
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }

    if (/戻る/.test(txt)) {
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }
  });

  // =========================
  // 五十音ページ 検索＋かなフィルタ（既存）
  // =========================
  const searchInput = document.querySelector(".search-input");
  const kanaButtons = document.querySelectorAll(".kana-btn");
  const cards = document.querySelectorAll(".mushroom-card");

  if (searchInput && cards.length) {
    let currentKana = "all";

    function applyFilter() {
      const q = searchInput.value.trim();
      const keyword = q ? q.normalize("NFKC").toLowerCase() : "";

      cards.forEach(card => {
        const rawName = card.getAttribute("data-name") || "";
        const name = rawName.normalize("NFKC").toLowerCase();
        const kana = card.getAttribute("data-kana") || "";

        const matchText = !keyword || name.includes(keyword);
        const matchKana = currentKana === "all" || kana === currentKana;
        const show = matchText && matchKana;

        card.style.display = show ? "" : "none";

        const nameEl = card.querySelector(".mushroom-card-name");
        if (nameEl) {
          nameEl.innerHTML = keyword
            ? highlight(rawName, searchInput.value.trim())
            : rawName;
        }
      });

      updateEmptyState();
      sendHeight();
    }

    function updateEmptyState() {
      const hasQuery = searchInput.value.trim() !== "" || currentKana !== "all";
      if (!hasQuery) {
        const empty = document.querySelector(".search-empty");
        if (empty) empty.style.display = "none";
        return;
      }

      const visible = Array.from(cards).some(c => c.style.display !== "none");

      let empty = document.querySelector(".search-empty");
      if (!empty) {
        empty = document.createElement("div");
        empty.className = "search-empty";
        empty.innerHTML = `
          🔍 該当するキノコが見つかりませんでした<br>
          <small>別の文字で試してみてください</small>
        `;
        document.querySelector(".mushroom-list")?.after(empty);
      }
      empty.style.display = visible ? "none" : "block";
    }

    searchInput.addEventListener("input", applyFilter);

    kanaButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        kanaButtons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        document.querySelectorAll(".aiuo-link")
          .forEach(l => l.classList.remove("current"));

        const kana = btn.getAttribute("data-kana") || "all";
        document.querySelector(`.aiuo-link[data-kana="${kana}"]`)
          ?.classList.add("current");

        currentKana = kana;
        applyFilter();
      });
    });
  }

  // =========================
// ⭐ お気に入り専用ページ描画
// =========================
    function renderFavoritePage() {
      const favs = loadFavorites();
      let count = 0;
    
      document.querySelectorAll(".favorite-gallery .gallery-item").forEach(item => {
        const img = item.querySelector("img");
        const star = item.querySelector(".thumb-fav");
        if (!img || !star) return;
    
        const src = normalizeSrc(img.getAttribute("src"));
    
        if (favs[src]) {
          item.style.display = "";
          star.textContent = "★";
          star.classList.add("is-fav");
          count++;
        } else {
          item.style.display = "none";
        }
      });
    
      const empty = document.querySelector(".favorite-empty");
      if (empty) {
        empty.style.display = count === 0 ? "block" : "none";
      }
    }

  // =========================
  // index 横断検索（既存：ページネーション含む）
  // =========================
  const indexSearchInput = document.querySelector(".index-search-input");
  const indexResults = document.querySelector(".index-search-results");
  const emptyEl = document.querySelector(".section .search-empty");

  if (indexSearchInput && indexResults) {
    const ALL_MUSHROOMS = window.ALL_MUSHROOMS || [];
    let page = 1;
    const PER_PAGE = 30;

    function renderResults(list, q = "") {
      if (!q) {
        indexResults.innerHTML = "";
        emptyEl && (emptyEl.style.display = "none");
        return;
      }

      if (list.length === 0) {
        indexResults.innerHTML = "";
        emptyEl && (emptyEl.style.display = "block");
        return;
      }

      emptyEl && (emptyEl.style.display = "none");

      indexResults.innerHTML = list.map(item => `
        <a href="${item.href}?from=index&q=${encodeURIComponent(q)}"
           class="mushroom-card search-result-item">
          <div class="mushroom-card-thumb">
            <span class="card-fav">☆</span>
            <img src="${item.thumb}" alt="${item.name}">
          </div>
          <div class="mushroom-card-name">
            ${highlight(item.name, q)}
          </div>
        </a>
      `).join("");
      updateCardFavorites();
    }

    function updateURL(q, page) {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (page > 1) params.set("page", page);
      history.replaceState(null, "", "?" + params.toString());
    }

    function loadFromURL() {
      const params = new URLSearchParams(location.search);
      return {
        q: params.get("q") || "",
        p: Number(params.get("page") || 1)
      };
    }

    function renderPagination(totalPages) {
      const wrap = document.querySelector(".index-pagination");
      if (!wrap) return;

      if (totalPages <= 1) {
        wrap.innerHTML = "";
        return;
      }

      wrap.innerHTML = `
        <span class="index-page-btn ${page <= 1 ? "disabled" : ""}" data-move="-1">前へ</span>
        <span style="margin:0 10px;">${page} / ${totalPages}</span>
        <span class="index-page-btn ${page >= totalPages ? "disabled" : ""}" data-move="1">次へ</span>
      `;

      wrap.querySelectorAll(".index-page-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          page += Number(btn.dataset.move);
          doSearch();
          window.parent.postMessage({ type: "scrollToTitle" }, "*");
        });
      });
    }

    function doSearch() {
      const rawQ = indexSearchInput.value.trim().normalize("NFKC");
      const q = rawQ.toLowerCase();

      const filtered = rawQ
        ? ALL_MUSHROOMS.filter(m => m.name_norm.includes(q))
        : [];

      const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
      page = Math.min(Math.max(1, page), totalPages);

      const start = (page - 1) * PER_PAGE;
      renderResults(filtered.slice(start, start + PER_PAGE), rawQ);

      renderPagination(rawQ ? totalPages : 0);
      updateURL(rawQ, page);
      sendHeight();
    }

    const { q, p } = loadFromURL();
    indexSearchInput.value = q;
    page = p;
    doSearch();

    indexSearchInput.addEventListener("input", () => {
      page = 1;
      doSearch();
    });
  }

  // =========================
// カード★ 初期同期（index / 五十音ページ用）
// =========================
    updateCardFavorites();

// =========================
// ⭐ お気に入り専用ページ描画（正）
// =========================
    if (document.querySelector(".favorite-gallery")) {
      renderFavoritePage();
      sendHeight();
    }
  // =========================
  // 高さ監視（既存）
  // =========================
  sendHeight();
  window.addEventListener("load", () => {
    sendHeight();
    setTimeout(sendHeight, 800);
    setTimeout(sendHeight, 2000);
  });
  window.addEventListener("message", e => {
    if (e.data?.type === "requestHeight") sendHeight();
  });
  window.addEventListener("resize", sendHeight);
  new MutationObserver(sendHeight)
    .observe(document.body, { childList: true, subtree: true });

  let lastHeight = 0;
  setInterval(() => {
    const height = Math.max(
      document.body.scrollHeight,
      document.body.offsetHeight,
      document.documentElement.scrollHeight,
      document.documentElement.offsetHeight
    );
    if (height !== lastHeight) {
      lastHeight = height;
      window.parent.postMessage({ type: "setHeight", height }, "*");
    }
  }, 300);
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
# ギャラリー生成（キノコページ & 五十音ページ）
# ===========================
def generate_gallery(entries, exif_cache):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

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

    # ② 五十音ページ
    aiuo_dict = {k: [] for k in AIUO_GROUPS.keys()}
    for alt in grouped.keys():
        g = get_aiuo_group(alt)
        if g in aiuo_dict:
            aiuo_dict[g].append(alt)

    for g, names in aiuo_dict.items():
        html_parts = []

        html_parts.append(f"<h2>{g}のキノコ</h2>")

        initials = sorted({ n[0] for n in names if n })

        html_parts.append("<div class='kana-grid'>")
        html_parts.append("<button class='kana-btn active' data-kana='all'>すべて</button>")
        for ch in initials:
            esc_ch = html.escape(ch)
            html_parts.append(
                f"<button class='kana-btn' data-kana='{esc_ch}'>{esc_ch}</button>"
            )
        html_parts.append("</div>")

        html_parts.append("""
        <div class="search-wrap">
          <input type="text" class="search-input" placeholder="キノコ名で絞り込み">
        </div>
        """)

        html_parts.append("<div class='mushroom-list'>")

        for n in sorted(names):
            safe = safe_filename(n)
            first_char = n[0] if n else ""
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

        html_parts.append("""
        <div style="text-align:center; margin:40px 0 20px;">
          <a href="index.html" class="back-btn">
            ◀ トップに戻る
          </a>
        </div>
        """)
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
            "name_norm": alt.lower(),
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
  <h2 class="section-title">🔍 全キノコ横断検索</h2>

  <div class="section-card">
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
    # 五十音別分類 + ⭐お気に入り導線
    # ==========================================================
    index_parts.append("""
<div class="section">
  <h2 class="section-title">五十音別分類</h2>

  <div class="section-card">
    <div class="aiuo-links">
""")

    for g in AIUO_GROUPS.keys():
        index_parts.append(
            f'<a class="aiuo-link" href="{safe_filename(g)}.html">{g}</a>'
        )

    # ⭐ お気に入り導線（1行追加）
    index_parts.append(
        '<a class="aiuo-link" href="favorite.html">⭐ 観察ノートを見る</a>'
    )

    index_parts.append("""
    </div>
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
  <h2 class="section-title">おすすめキノコ</h2>

  <div class="section-card">
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
    parts = []

    parts.append("""
<h2 class="section-title">⭐ 観察ノート</h2>

<div class="section-card">
  <p style="text-align:center; color:#666; margin-bottom:16px; line-height:1.6;">
    このギャラリーを見て、気になったキノコの写真を集められるページです。<br>
    写真を見比べながら、姿や形の違いを観察してみてください。
  </p>

  <div class="favorite-empty" style="display:none; text-align:center; color:#777; line-height:1.8;">
    まだ観察ノートはありません<br>
    <small>写真の★を押して、観察ノートを作ってみてください</small>
  </div>

  <div class="gallery favorite-gallery">
""")

    # ★ 写真単位ですべて出力（表示制御はJS）
    for alt, srcs in grouped.items():
        esc_alt = html.escape(alt)
        for src in srcs:
            thumb = src + "?width=300"
            parts.append(f"""
    <a class="gallery-item"
       href="{src}"
       data-alt="{esc_alt}"
       data-exthumbimage="{thumb}"
       style="display:none;">
      <span class="thumb-fav">☆</span>
      <span class="spores"></span>
      <img src="{src}" alt="{esc_alt}" loading="lazy">
    </a>
            """)

    parts.append("""
  </div>

  <div style="text-align:center; margin-top:30px;">
    <a href="index.html" class="back-btn">
      ◀ トップに戻る
    </a>
  </div>
</div>
""")

    parts.append(STYLE_TAG)
    parts.append(LIGHTGALLERY_TAGS)
    parts.append(SCRIPT_TAG)

    with open(f"{OUTPUT_DIR}/favorite.html", "w", encoding="utf-8") as f:
        f.write("".join(parts))

    print("⭐ favorite.html（写真単位）生成完了")

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

        grouped = generate_gallery(entries, exif_cache)
        generate_index(grouped, exif_cache)
        generate_favorite_page(grouped)
    else:
        print("⚠️ 画像が見つかりませんでした。")
