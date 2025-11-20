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

    // ⭐ static 初期化を削除（ここが競合の原因だった）
    imagesLoaded(gallery, () => {
      gallery.style.visibility="visible";
      sendHeight();
    });
  }

  sendHeight();
  window.addEventListener("load", ()=>{ 
      sendHeight(); 
      setTimeout(sendHeight,800); 
      setTimeout(sendHeight,2000); 
      setTimeout(sendHeight,4000); 
  });

  window.addEventListener("message", e=>{
    if(e.data?.type==="requestHeight") sendHeight();
  });

  window.addEventListener("resize", sendHeight);
  new MutationObserver(sendHeight).observe(document.body,{childList:true,subtree:true});

  document.addEventListener("click", e=>{
    const a = e.target.closest("a");
    if(!a) return;
    const href = a.getAttribute("href")||"";
    if(href.startsWith("javascript:history.back") || 
       href.endsWith(".html") || href.includes("index")){
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
<script src="./lightgallery/lightgallery.min.js"></script>
<script src="./lightgallery/lg-zoom.min.js"></script>
<script src="./lightgallery/lg-thumbnail.min.js"></script>

<script>
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('.gallery').forEach(gallery => {
    const imgs = Array.from(gallery.querySelectorAll('img'));
    if (imgs.length === 0) return;

    const items = imgs.map(img => {
      const thumb = img.src + "?width=300";
      return {
        src: img.src,
        thumb: thumb,
        subHtml: `<h4>${(img.alt || '').replace(/"/g,'&quot;')}</h4>`
      };
    });

    window.__lgDebugItems = items;

    imgs.forEach((img, idx) => {
      img.addEventListener('click', () => {

        const el = document.documentElement;
        if (el.requestFullscreen) el.requestFullscreen();
        else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
        else if (el.msRequestFullscreen) el.msRequestFullscreen();

        const galleryInstance = lightGallery(document.body, {
          dynamic: true,
          dynamicEl: items,
          index: idx,
          plugins: [lgZoom, lgThumbnail],
          speed: 400,
          thumbnail: true,
          download: false,
          zoom: true,
          fullScreen: true,
          actualSize: false
        });

        setTimeout(() => {
          const thumbs = Array.from(document.querySelectorAll(".lg-thumb-item img"))
            .map(img => img.getAttribute("src"));
          console.log("🖼 サムネイル = ", thumbs);
        }, 800);

        galleryInstance.on('lgAfterClose', () => {
          if (document.fullscreenElement) document.exitFullscreen().catch(()=>{});
        });

        document.addEventListener('fullscreenchange', () => {
          if (!document.fullscreenElement) {
            try { galleryInstance.closeGallery(); } catch(e){}
          }
        });

      });
    });
  });
});
</script>
"""

# ====== 以降はあなたの元コードのまま（省略） ======
# ====== HTML抽出・ギャラリー生成・メインはそのまま ======
