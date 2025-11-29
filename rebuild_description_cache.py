import os
import re
import glob
import json
from bs4 import BeautifulSoup

# 1. cache フォルダが無ければ作成
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")

def extract_description(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    card = soup.find("div", class_="info-card")
    if not card:
        return None, None

    title_tag = card.find("h3")
    if not title_tag:
        return None, None

    name = title_tag.get_text(strip=True)

    ps = [p.get_text(strip=True) for p in card.find_all("p")]
    desc = "\n".join(ps)

    return name, desc


desc_cache = {}

# output/*.html から抽出
for html_file in glob.glob("output/*.html"):
    with open(html_file, encoding="utf-8") as f:
        text = f.read()

    name, desc = extract_description(text)
    if name and desc:
        desc_cache[name] = desc
        print(f"✔ {name} 説明文抽出")

# JSON に保存
with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(desc_cache, f, ensure_ascii=False, indent=2)

print(f"\n=== 完了: {DESC_CACHE_FILE} に {len(desc_cache)} 件保存 ===")
