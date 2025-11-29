import os
import json
from bs4 import BeautifulSoup
import html

OUTPUT_DIR = "output"
CACHE_DIR = "cache"
DESC_CACHE_FILE = os.path.join(CACHE_DIR, "description-cache.json")

def rebuild_description_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = {}

    # output/ ディレクトリのすべての .html を走査
    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith(".html"):
            continue

        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        # info-card → <h3> がキノコ名
        card = soup.find("div", class_="info-card")
        if not card:
            continue

        h3 = card.find("h3")
        if not h3:
            continue
        name = h3.get_text(strip=True)

        # <p> 全部つなげて説明文
        paragraphs = [p.get_text("\n", strip=True) for p in card.find_all("p")]
        desc = "\n".join(paragraphs).strip()

        if name and desc:
            cache[name] = desc
            print(f"✔ 追加: {name}")

    # JSON に保存
    with open(DESC_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 完了！ {len(cache)} 件の説明文をキャッシュ化しました")
    print(f"→ {DESC_CACHE_FILE}")

if __name__ == "__main__":
    rebuild_description_cache()
