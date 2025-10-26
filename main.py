import os, glob, time, requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re

# ====== 設定 ======
HATENA_USER = os.getenv("HATENA_USER")
HATENA_BLOG_ID = os.getenv("HATENA_BLOG_ID")
HATENA_API_KEY = os.getenv("HATENA_API_KEY")

if not all([HATENA_USER, HATENA_BLOG_ID, HATENA_API_KEY]):
    raise EnvironmentError("環境変数が未設定です。HATENA_USER, HATENA_BLOG_ID, HATENA_API_KEY を確認してください。")

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

# ====== iframe 高さ調整 + Masonry縦2列＋レスポンシブ1列版 完全修正版2 ======
SCRIPT_STYLE_TAG = """<style>
body { 
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
  background:#fafafa; 
  color:#333; 
  padding:16px; 
  min-height: 0; 
  box-sizing: border-box;
}
.gallery-wrapper {
  width: 100%;
}
.gallery {
  position: relative; /* Masonryの位置計算用 */
  margin: 0 auto;
}
.gallery img { 
  display: block;
  border-radius:8px; 
  transition:opacity 0.5s ease-out; 
  opacity:0; 
  margin-bottom:10px; 
}
.gallery img.visible { 
  opacity:1; 
}
@media (max-width: 400px) {
  .gallery {
    width: 100% !important;
  }
}
a.back-link {
  display: inline-block;
  margin-top: 16px;
  color: #333;
  text-decoration: none;
}
.glightbox-desc a {
  color: #ddd !important;
  text-decoration: underline;
}
.glightbox-desc a:hover {
  color: #fff !important;
}
</style>

<!-- Masonry.js と imagesLoaded -->
<script src="https://unpkg.com/masonry-layout@4/dist/masonry.pkgd.min.js"></script>
<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>

<script>
(function() {
  if (window === window.parent) return;

  const sendHeight = () => {
    const height = document.documentElement.scrollHeight;
    window.parent.postMessage({ type: "setHeight", height }, "*");
  };

  window.addEventListener("load", () => {
    sendHeight(); 
    setTimeout(sendHeight, 500); 
    setTimeout(sendHeight, 1000);
    window.scrollTo(0,0); 
    setTimeout(() => window.scrollTo(0,0), 200);
    try { 
      window.parent.postMessage({ type: "scrollTopRequest", pathname: location.pathname }, "*"); 
    } catch(e) { console.warn(e); }
  });

  window.addEventListener("resize", sendHeight);
  const observer = new MutationObserver(sendHeight);
  observer.observe(document.body, { childList: true, subtree: true });
  setInterval(sendHeight, 1000);

  document.addEventListener("DOMContentLoaded", () => {
    const imgs = document.querySelectorAll(".gallery img");

    // 画像フェードイン
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if(e.isIntersecting){ 
          e.target.classList.add("visible"); 
          obs.unobserve(e.target); 
        }
      });
    }, {threshold:0.1});
    imgs.forEach(i => obs.observe(i));

    const gallery = document.querySelector('.gallery');
    if (gallery) {
      const gutter = 10;
      const defaultColumnWidth = 160;

      const setMasonryLayout = () => {
        const isMobile = window.innerWidth <= 400;
        const columns = isMobile ? 1 : 2;
        const columnWidth = isMobile ? window.innerWidth - 32 : defaultColumnWidth;
        const galleryWidth = columnWidth * columns + gutter * (columns - 1);

        gallery.style.width = galleryWidth + "px";

        // 画像幅を Masonry の列幅に合わせる
        gallery.querySelectorAll("img").forEach(img => {
          img.style.width = columnWidth + "px";
        });

        if (gallery.msnry) {
          gallery.msnry.options.columnWidth = columnWidth;
          gallery.msnry.layout();
        } else {
          gallery.msnry = new Masonry(gallery, {
            itemSelector: 'img',
            columnWidth: columnWidth,
            gutter: gutter,
            fitWidth: true
          });
        }
      };

      imagesLoaded(gallery, () => { setMasonryLayout(); sendHeight(); });
      window.addEventListener('resize', () => { setMasonryLayout(); sendHeight(); });
    }
  });

  function scrollToTopBoth() {
    window.scrollTo({ top: 0, behavior: "smooth" });
    try { 
      window.parent.postMessage({ type: "scrollTopRequest", pathname: location.pathname }, "*"); 
    } catch(e) { console.warn(e); }
  }

  document.addEventListener("click", e => {
    const a = e.target.closest("a");
    if (!a) return;
    const href = a.getAttribute("href") || "";
    if (href.startsWith("javascript:history.back") || href.startsWith("#") || href.endsWith(".html") || href.includes("index")) {
      setTimeout(scrollToTopBoth, 150);
    }
  });
})();
</script>

<!-- ▼ アニメーション＆ナビ付き Lightboxに差し替え ▼ -->
<style>
/* Lightbox 背景 */
.lightbox {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background: rgba(0,0,0,0.9);
  display: none;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  opacity: 0;
  transition: opacity 0.3s ease;
}

/* 表示時 */
.lightbox.show {
  display: flex;
  opacity: 1;
}

/* コンテンツ */
.lightbox-content {
  position: relative;
  background: transparent;
  border-radius: 8px;
  text-align: center;
  max-width: 95%;
  max-height: 95%;
}

/* 画像 */
.lightbox-content img {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 80vh;
  border-radius: 8px;
  transition: opacity 0.3s ease;
}

/* フェード切り替え */
.lightbox-content img.fade-out {
  opacity: 0;
}

/* ボタン共通 */
.lb-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(0,0,0,0.5);
  color: #fff;
  font-size: 28px;
  font-weight: bold;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  text-align: center;
  line-height: 40px;
  cursor: pointer;
  user-select: none;
}
.lb-btn:hover {
  background: rgba(255,255,255,0.3);
}

/* 左右ボタン */
.lb-prev { left: -60px; }
.lb-next { right: -60px; }

/* 閉じるボタン */
.lightbox-close {
  position: absolute;
  top: -50px;
  right: 0;
  font-size: 28px;
  background: rgba(0,0,0,0.5);
  color: #fff;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  text-align: center;
  line-height: 40px;
  cursor: pointer;
}
.lightbox-close:hover {
  background: rgba(255,255,255,0.3);
}

/* 元記事リンク */
.lightbox-link {
  display: block;
  text-align: center;
  color: #ddd;
  font-size: 14px;
  margin-top: 8px;
  text-decoration: none;
}
.lightbox-link:hover {
  color: #fff;
  text-decoration: underline;
}
</style>

<script>
document.addEventListener("DOMContentLoaded", function() {
  // Lightbox要素を作成
  const lb = document.createElement("div");
  lb.className = "lightbox";
  lb.innerHTML = `
    <div class="lightbox-content">
      <span class="lightbox-close">&times;</span>
      <span class="lb-btn lb-prev">←</span>
      <img id="lightbox-img" src="" alt="">
      <span class="lb-btn lb-next">→</span>
      <a id="lightbox-link" class="lightbox-link" href="#" target="_blank">元記事を見る</a>
    </div>
  `;
  document.body.appendChild(lb);

  const lbImg = lb.querySelector("#lightbox-img");
  const lbLink = lb.querySelector("#lightbox-link");
  const closeBtn = lb.querySelector(".lightbox-close");
  const prevBtn = lb.querySelector(".lb-prev");
  const nextBtn = lb.querySelector(".lb-next");

  const imgs = Array.from(document.querySelectorAll(".gallery img"));
  let currentIndex = 0;

  function showLightbox(index) {
    const img = imgs[index];
    if (!img) return;
    currentIndex = index;

    lb.style.display = "flex";
    requestAnimationFrame(() => lb.classList.add("show"));

    lbImg.classList.add("fade-out");
    setTimeout(() => {
      lbImg.src = img.src;
      lbLink.href = img.dataset.url || "#";
      lbImg.classList.remove("fade-out");
    }, 200);

    // スクロール位置調整（縦中央へ）
    setTimeout(() => {
      window.scrollTo({
        top: (document.body.scrollHeight / 2) - (window.innerHeight / 2),
        behavior: "smooth"
      });
    }, 100);
  }

  function hideLightbox() {
    lb.classList.remove("show");
    setTimeout(() => lb.style.display = "none", 300);
  }

  imgs.forEach((img, i) => {
    img.addEventListener("click", () => showLightbox(i));
  });

  closeBtn.addEventListener("click", hideLightbox);
  lb.addEventListener("click", e => {
    if (e.target === lb) hideLightbox();
  });

  // 前後ボタン
  prevBtn.addEventListener("click", e => {
    e.stopPropagation();
    showLightbox((currentIndex - 1 + imgs.length) % imgs.length);
  });
  nextBtn.addEventListener("click", e => {
    e.stopPropagation();
    showLightbox((currentIndex + 1) % imgs.length);
  });

  // キーボード操作
  document.addEventListener("keydown", e => {
    if (lb.style.display === "flex") {
      if (e.key === "ArrowLeft") showLightbox((currentIndex - 1 + imgs.length) % imgs.length);
      if (e.key === "ArrowRight") showLightbox((currentIndex + 1) % imgs.length);
      if (e.key === "Escape") hideLightbox();
    }
  });
});
</script>
<!-- ▲ Lightboxここまで ▲ -->

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
            if content is None: continue
            html_content = content.text or ""
            filename = f"{ARTICLES_DIR}/article_{count+i}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"✅ 保存完了: {filename}")
        count += len(entries)
        next_link = root.find("atom:link[@rel='next']", ns)
        url = next_link.attrib["href"] if next_link is not None else None

    print(f"📦 合計 {count} 件の記事を保存しました。")

# ====== HTMLから画像とaltを抽出（本文限定 + altフィルタ + iframe/a除外） ======
def fetch_images():
    import re

    print("📂 HTMLから画像抽出中…")
    entries = []

    # 除外したい alt/text パターンのリスト
    exclude_patterns = [
        r'はてなブックマーク',                  # 部分一致
        r'^\d{4}年',                             # 年付きテキスト
        r'^この記事をはてなブックマークに追加$', # 完全一致
        r'^ワ行$',                               # 完全一致
        r'キノコと田舎遊び',  # 部分一致
        # 追加する場合はここにパターンを追記
    ]

    for html_file in glob.glob(f"{ARTICLES_DIR}/*.html"):
        with open(html_file, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            # 本文に限定（entry-body クラス内）
            body_div = soup.find(class_="entry-body")
            if not body_div:
                body_div = soup  # 本文限定が見つからなければ全体

            # ===== iframe / a タグで除外対象を削除 =====
            for iframe in body_div.find_all("iframe"):
                title = iframe.get("title", "")
                if any(re.search(p, title) for p in exclude_patterns):
                    iframe.decompose()
            for a in body_div.find_all("a"):
                text = a.get_text(strip=True)
                if any(re.search(p, text) for p in exclude_patterns):
                    a.decompose()

            # ===== img タグを抽出 =====
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

    # 共通リンク
    group_links = " | ".join([f'<a href="{g}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px; text-align:center;'>{group_links}</div>"

    # 安全なファイル名生成関数
    def safe_filename(name):
        import re
        name = re.sub(r'[:<>\"|*?\\/\r\n]', '_', name)
        name = name.strip()
        if not name:
            name = "unnamed"
        return name

    # 各キノコページ
    for alt, imgs in grouped.items():
        html = f"<h2>{alt}</h2><div class='gallery'>"
        for src in imgs:
            article_url = f"https://{HATENA_BLOG_ID}.hatena.blog/"  # 仮リンク
            html += f'''
<img src="{src}" alt="{alt}" loading="lazy" data-url="{article_url}">
'''
        html += "</div>"
        html += """
        <div style='margin-top:40px; text-align:center;'>
          <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """
        html += SCRIPT_STYLE_TAG
        safe = safe_filename(alt)
        with open(f"{OUTPUT_DIR}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # 五十音ページ
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
        html += SCRIPT_STYLE_TAG
        with open(f"{OUTPUT_DIR}/{safe_filename(g)}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # index.html
    index = "<h2>五十音別分類</h2><ul>"
    for g in AIUO_GROUPS.keys():
        index += f'<li><a href="{safe_filename(g)}.html">{g}</a></li>'
    index += "</ul>" + SCRIPT_STYLE_TAG
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
