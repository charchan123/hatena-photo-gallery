import os
import glob
import json
from bs4 import BeautifulSoup

OUTPUT_DIR = "output"
CACHE_DIR = "cache"
DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")

def extract_description_from_html(filepath):
    """
    output/*.html の info-card から説明文を抽出する。
    戻り値: (name, text) または None
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
    except Exception as e:
        print(f"❌ 読み込み失敗: {filepath}: {e}")
        return None

    card = soup.find("div", class_="info-card")
    if not card:
        print(f"⚠️ info-card が見つかりません: {filepath}")
        return None

    # ---- タイトル抽出 ----
    h3 = card.find("h3")
    if not h3:
        print(f"⚠️ h3 キノコ名が見つかりません: {filepath}")
        return None
    name = h3.get_text(strip=True)

    # ---- 段落抽出 ----
    paragraphs = []
    for p in card.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)

    if not paragraphs:
        print(f"⚠️ 説明文段落がゼロ: {filepath}")
        return None

    # 段落を結合 → 改行区切り
    full_text = "\n\n".join(paragraphs)

    return name, full_text


def rebuild_description_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)

    desc_cache = {}

    html_files = sorted(glob.glob(f"{OUTPUT_DIR}/*.html"))
    print(f"🔍 HTMLファイル検出: {len(html_files)} 件")

    for fpath in html_files:
        print(f"📄 処理中: {fpath}")
        result = extract_description_from_html(fpath)
        if not result:
            continue

        name, text = result
        desc_cache[name] = text
        print(f"  → 抽出成功: {name}（{len(text)}文字）")

    # 保存
    with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(desc_cache, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 完了: {DESC_CACHE_FILE} に {len(desc_cache)} 件保存しました。")


if __name__ == "__main__":
    rebuild_description_cache()
