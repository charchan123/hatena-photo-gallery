from bs4 import BeautifulSoup
import glob
import os

output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

html_files = glob.glob("articles/*.html")  # ← HTMLファイルを保存したフォルダ

images = []

for file_path in html_files:
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    for img in soup.find_all("img"):
        src = img.get("src")
        alt = img.get("alt", "（altなし）")
        if src:
            images.append({"src": src, "alt": alt})

# HTMLギャラリー生成
gallery_html = "<h1>画像ギャラリー</h1><div style='display:flex;flex-wrap:wrap;gap:10px;'>"

for img in images:
    gallery_html += f"<div style='width:200px;text-align:center;'><img src='{img['src']}' alt='{img['alt']}' style='width:100%;'><p>{img['alt']}</p></div>"

gallery_html += "</div>"

with open(os.path.join(output_dir, "gallery.html"), "w", encoding="utf-8") as f:
    f.write(gallery_html)

print(f"✅ {len(images)}枚の画像をギャラリーに追加しました！")
