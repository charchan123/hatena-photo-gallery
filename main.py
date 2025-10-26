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

# ====== ギャラリー用スタイル + Masonry + Lightbox ======
SCRIPT_STYLE_TAG = """<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css" />
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:#fafafa; color:#333; padding:16px; min-height:0; box-sizing:border-box; }
.gallery-wrapper { width:100%; }
.gallery { position:relative; margin:0 auto; }
.gallery img { display:block; border-radius:8px; transition:opacity 0.5s ease-out; opacity:0; margin-bottom:10px; }
.gallery img.visible { opacity:1; }
@media (max-width:400px) { .gallery { width:100% !important; } }
a.back-link { display:inline-block; margin-top:16px; color:#333; text-decoration:none; }
</style>

<script src="https://unpkg.com/masonry-layout@4/dist/masonry.pkgd.min.js"></script>
<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js"></script>

<script>
document.addEventListener("DOMContentLoaded", () => {
  const imgs = document.querySelectorAll(".gallery img");
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if(e.isIntersecting){ e.target.classList.add("visible"); obs.unobserve(e.target); }
    });
  }, {threshold:0.1});
  imgs.forEach(i => obs.observe(i));

  const gallery = document.querySelector('.gallery');
  if(gallery){
    const gutter = 10;
    const defaultColumnWidth = 160;
    const setMasonryLayout = () => {
      const isMobile = window.innerWidth <= 400;
      const columns = isMobile ? 1 : 2;
      const columnWidth = isMobile ? window.innerWidth-32 : defaultColumnWidth;
      const galleryWidth = columnWidth*columns + gutter*(columns-1);
      gallery.style.width = galleryWidth + "px";
      gallery.querySelectorAll("img").forEach(img => img.style.width = columnWidth+"px");
      if(gallery.msnry){ gallery.msnry.options.columnWidth=columnWidth; gallery.msnry.layout(); }
      else{ gallery.msnry = new Masonry(gallery,{ itemSelector:'img', columnWidth:columnWidth, gutter:gutter, fitWidth:true }); }
    };
    imagesLoaded(gallery, () => { setMasonryLayout(); });
    window.addEventListener('resize', ()=>{ setMasonryLayout(); });
  }
  GLightbox({ selector: '.glightbox' });
});
</script>
"""

# ====== API取得 ======
def fetch_hatena_articles_api():
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    print("📡 はてなブログAPIから全記事取得中…")
    url = ATOM_ENDPOINT
    count = 0
    while url:
        r = requests.get(url, auth=AUTH, headers=HEADERS)
        if r.status_code != 200: raise RuntimeError(f"API取得失敗: {r.status_code}")
        root = ET.fromstring(r.text)
        ns = {"atom":"http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        for i, entry in enumerate(entries,1):
            content = entry.find("atom:content", ns)
            if content is None: continue
            html_content = content.text or ""
            filename = os.path.join(ARTICLES_DIR,f"article_{count+i}.html")
            with open(filename,"w",encoding="utf-8") as f: f.write(html_content)
        count += len(entries)
        next_link = root.find("atom:link[@rel='next']", ns)
        url = next_link.attrib["href"] if next_link is not None else None
    print(f"📦 合計 {count} 件の記事を保存しました。")

# ====== 画像抽出 ======
def fetch_images():
    print("📂 HTMLから画像抽出中…")
    entries=[]
    exclude_patterns=[r'はてなブックマーク',r'^\d{4}年',r'^この記事をはてなブックマークに追加$',r'^ワ行$',r'キノコと田舎遊び']
    for html_file in glob.glob(os.path.join(ARTICLES_DIR,"*.html")):
        with open(html_file,encoding="utf-8",errors="ignore") as f:
            soup = BeautifulSoup(f,"html.parser")
            body_div = soup.find(class_="entry-body") or soup
            for iframe in body_div.find_all("iframe"):
                title = iframe.get("title","")
                if any(re.search(p,title) for p in exclude_patterns): iframe.decompose()
            for a in body_div.find_all("a"):
                text = a.get_text(strip=True)
                if any(re.search(p,text) for p in exclude_patterns): a.decompose()
            for img in body_div.find_all("img"):
                alt = img.get("alt","").strip()
                src = img.get("src")
                if not alt or not src: continue
                if any(re.search(p,alt) for p in exclude_patterns): continue
                # 元記事URLも追加
                entries.append({"alt":alt,"src":src,"article_url":html_file})
    print(f"🧩 画像検出数: {len(entries)} 枚")
    return entries

# ====== 五十音分類 ======
def get_aiuo_group(name):
    if not name: return "その他"
    first = name[0]
    for group, chars in AIUO_GROUPS.items():
        if first in chars: return group
    return "その他"

# ====== ギャラリー生成 ======
def generate_gallery(entries):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    grouped = {}
    for e in entries: grouped.setdefault(e["alt"],[]).append(e)

    def safe_filename(name):
        return re.sub(r'[:<>\"|*?\\/\r\n]','_',name).strip() or "unnamed"

    group_links = " | ".join([f'<a href="{safe_filename(g)}.html">{g}</a>' for g in AIUO_GROUPS.keys()])
    group_links_html = f"<div style='margin-top:40px;text-align:center;'>{group_links}</div>"

    for alt, imgs in grouped.items():
        html = f"<h2>{alt}</h2><div class='gallery'>"
        for img in imgs:
            html += f'<a href="{img["src"]}" class="glightbox" data-title="{alt}" data-description="元記事: {img["article_url"]}"><img src="{img["src"]}" alt="{alt}" loading="lazy"></a>'
        html += "</div>"
        html += "<div style='margin-top:40px;text-align:center;'><a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a></div>"
        html += SCRIPT_STYLE_TAG
        with open(os.path.join(OUTPUT_DIR,safe_filename(alt)+".html"),"w",encoding="utf-8") as f: f.write(html)

    # 五十音ページ
    aiuo_dict={k:[] for k in AIUO_GROUPS.keys()}
    for alt in grouped.keys(): g=get_aiuo_group(alt); aiuo_dict.get(g,[]).append(alt)

    for g,names in aiuo_dict.items():
        html=f"<h2>{g}のキノコ</h2><ul>"
        for n in sorted(names): html+=f'<li><a href="{safe_filename(n)}.html">{n}</a></li>'
        html+="</ul>"+group_links_html+SCRIPT_STYLE_TAG
        with open(os.path.join(OUTPUT_DIR,safe_filename(g)+".html"),"w",encoding="utf-8") as f: f.write(html)

    index="<h2>五十音別分類</h2><ul>"
    for g in AIUO_GROUPS.keys(): index+=f'<li><a href="{safe_filename(g)}.html">{g}</a></li>'
    index+="</ul>"+SCRIPT_STYLE_TAG
    with open(os.path.join(OUTPUT_DIR,"index.html"),"w",encoding="utf-8") as f: f.write(index)
    print("✅ ギャラリーページ生成完了")

# ====== メイン ======
if __name__=="__main__":
    fetch_hatena_articles_api()
    entries=fetch_images()
    if entries: generate_gallery(entries)
    else: print("⚠️ 画像が見つかりませんでした。")
