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

# ====== iframe 高さ調整 + スタイル（完全版） ======
SCRIPT_STYLE_TAG = """<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:#fafafa; color:#333; padding:16px; }
.gallery { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }
.gallery img { width:100%; border-radius:8px; transition:opacity 0.5s ease-out; opacity:0; }
.gallery img.visible { opacity:1; }
</style>
<script>
(function() {
  // iframe外で二重実行防止
  if (window === window.parent) return;

  // ===== 高さ送信 =====
  const sendHeight = () => {
    const height = document.documentElement.scrollHeight;
    window.parent.postMessage({ type: "setHeight", height }, "*");
    console.log("[iframe] sendHeight ->", height);
  };

  // ページロード時
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

  // リサイズ時
  window.addEventListener("resize", sendHeight);

  // DOM変化監視
  const observer = new MutationObserver(sendHeight);
  observer.observe(document.body, { childList: true, subtree: true });

  // 低くなるケース用：1秒ごとに送信
  setInterval(sendHeight, 1000);

  // ===== ギャラリー画像フェードイン =====
  document.addEventListener("DOMContentLoaded", () => {
    const imgs = document.querySelectorAll(".gallery img");
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if(e.isIntersecting){
          e.target.classList.add("visible");
          obs.unobserve(e.target);
        }
      });
    }, {threshold:0.1});
    imgs.forEach(i => obs.observe(i));
  });

  // ===== リンククリックでトップに戻す =====
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
</script>"""

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

    # 各キノコページ
    for alt, imgs in grouped.items():
        html = f"<h2>{alt}</h2><div class='gallery'>"
        for src in imgs:
            html += f'<img src="{src}" alt="{alt}" loading="lazy">'
        html += "</div>"
        html += """
        <div style='margin-top:40px; text-align:center;'>
          <a href='javascript:history.back()' style='text-decoration:none;color:#007acc;'>← 戻る</a>
        </div>
        """
        html += SCRIPT_STYLE_TAG
        safe = alt.replace("/", "_").replace(" ", "_")
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
            safe = n.replace("/", "_").replace(" ", "_")
            html += f'<li><a href="{safe}.html">{n}</a></li>'
        html += "</ul>"
        html += group_links_html
        html += SCRIPT_STYLE_TAG
        with open(f"{OUTPUT_DIR}/{g}.html", "w", encoding="utf-8") as f:
            f.write(html)

    # index.html
    index = "<h2>五十音別分類</h2><ul>"
    for g in AIUO_GROUPS.keys():
        index += f'<li><a href="{g}.html">{g}</a></li>'
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
