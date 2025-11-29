import os
import re
import glob
import json
from bs4 import BeautifulSoup

# ========== 初期設定 ==========
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)
DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")


def extract_description(html_text):
    """
    圧縮HTML / タグが詰まったHTML / 改行なし でも強制的に抽出できる版
    """

    soup = BeautifulSoup(html_text, "html.parser")

    # info-card をそのまま探す（通常版）
    card = soup.find("div", class_="info-card")

    # 見つからない場合：正規表現で強制抽出
    if card is None:
        m = re.search(
            r'<div class="info-card">(.*?)</div>',
            html_text,
            re.DOTALL | re.IGNORECASE
        )
        if not m:
            return None, None
        raw = m.group(1)
        card = BeautifulSoup(raw, "html.parser")

    # ---- タイトル抽出 ----
    h3 = card.find("h3")
    if not h3:
        return None, None
    name = h3.get_text(strip=True)

    # ---- 説明文抽出（pタグ）----
    ps = card.find_all("p")
    if not ps:
        # fallback: <div class="info-card"> 内の全文から p を抽出
        raw = re.sub(r"<h3>.*?</h3>", "", card.text, flags=re.DOTALL)
        desc = raw.strip()
    else:
        desc = "\n".join([p.get_text(strip=True) for p in ps])

    # 万が一説明文が空なら None 扱い
    if not desc.strip():
        return None, None

    return name, desc


# ========== main ==========
desc_cache = {}

# output/*.html を全部走査
for html_file in glob.glob("output/*.html"):
    with open(html_file, encoding="utf-8") as f:
        text = f.read()

    name, desc = extract_description(text)
    if name and desc:
        desc_cache[name] = desc
        print(f"✔ {name} 説明文抽出")

# JSON 保存
with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(desc_cache, f, ensure_ascii=False, indent=2)

print(f"\n=== 完了: {DESC_CACHE_FILE} に {len(desc_cache)} 件保存 ===")
