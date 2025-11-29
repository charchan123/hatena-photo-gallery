import os
import re
import json
from bs4 import BeautifulSoup

OUTPUT_DIR = "output"
CACHE_DIR = "cache"
DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")

os.makedirs(CACHE_DIR, exist_ok=True)

cache = {}

for fname in os.listdir(OUTPUT_DIR):
    if not fname.endswith(".html"):
        continue

    path = os.path.join(OUTPUT_DIR, fname)
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    card = soup.find("div", class_="info-card")
    if not card:
        continue

    title = card.find("h3")
    if not title:
        continue
    name = title.get_text(strip=True)

    ps = card.find_all("p")
    text = "\n".join(p.get_text(strip=True) for p in ps)

    if text:
        cache[name] = text

with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"✔️ 記述復元完了: {len(cache)} entries")
