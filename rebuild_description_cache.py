import os
import re
import json
from bs4 import BeautifulSoup

OUTPUT_DIR = "output"
CACHE_DIR = "cache"
DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")

os.makedirs(CACHE_DIR, exist_ok=True)

desc_cache = {}

# info-card を抜き出す正規表現（圧縮 HTML に対応）
CARD_PATTERN = re.compile(
    r'<div class="info-card"><h3>(.*?)</h3>(.*?)</div><div class=[\'"]gallery',
    re.DOTALL
)

for html_file in os.listdir(OUTPUT_DIR):
    if not html_file.endswith(".html"):
        continue

    path = os.path.join(OUTPUT_DIR, html_file)
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # 正規表現で info-card ブロックをマッチ
    match = CARD_PATTERN.search(content)
    if not match:
        continue

    name = match.group(1).strip()
    raw_html = match.group(2)

    # BeautifulSoup で <p>からテキストを抽出
    soup = BeautifulSoup(raw_html, "html.parser")
    ps = [p.get_text(strip=True) for p in soup.find_all("p")]

    text = "\n".join(ps).strip()
    if text:
        desc_cache[name] = text
        print(f"✔ {html_file} → {name} 説明文抽出 OK")

# 保存
with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(desc_cache, f, ensure_ascii=False, indent=2)

print(f"\n=== 完了: {DESC_CACHE_FILE} に {len(desc_cache)} 件保存 ===")
