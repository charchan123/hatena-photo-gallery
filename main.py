import os
import glob
from pathlib import Path

# === 設定 ===
OUTPUT_DIR = "."  # GitHub Pages用ディレクトリ
IMG_DIR = "images"   # 画像ディレクトリ
BASE_URL = "https://charchan123.github.io/hatena-photo-gallery/"


def generate_gallery():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # トップページHTML
    index_html = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>はてなフォトギャラリー</title>
<link rel="stylesheet" href="gallery.css">
<style>
body {
  margin: 0;
  font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
  background: #fff;
}
h1 {
  text-align: center;
  margin: 1em 0;
}
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
  padding: 10px;
}
.gallery img {
  width: 100%;
  height: auto;
  cursor: pointer;
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.6s ease;
}
.gallery img.visible {
  opacity: 1;
  transform: translateY(0);
}
#lb-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background: rgba(0,0,0,0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  visibility: hidden;
  opacity: 0;
  transition: opacity 0.3s ease;
  z-index: 9999;
}
#lb-overlay.show {
  visibility: visible;
  opacity: 1;
}
#lb-overlay img {
  max-width: 90%;
  max-height: 80vh;
  margin-bottom: 10px;
}
.lb-close {
  position: absolute;
  top: 20px;
  right: 30px;
  font-size: 40px;
  color: #fff;
  cursor: pointer;
}
.lb-caption {
  color: #fff;
  text-align: center;
  font-size: 18px;
}
</style>
</head>
<body>
<h1>はてなフォトギャラリー</h1>
<div class="gallery">
"""

    # 画像一覧取得
    images = sorted(glob.glob(f"{IMG_DIR}/*.jpg")) + sorted(glob.glob(f"{IMG_DIR}/*.png"))

    for img_path in images:
        alt = Path(img_path).stem
        index_html += f'<img src="{BASE_URL}{img_path}" alt="{alt}" data-url="#">\n'

    # ====== Lightboxと高さ送信用JSを追加 ======
    index_html += """
</div>
<script src="https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js"></script>
<script>
function sendHeight() {
  const h = document.body.scrollHeight;
  parent.postMessage({ type: "galleryHeight", height: h }, "*");
}
window.addEventListener("load", sendHeight);
window.addEventListener("resize", sendHeight);

const gallery = document.querySelector(".gallery");
imagesLoaded(gallery, () => {
  gallery.querySelectorAll("img").forEach((img, i) => {
    setTimeout(() => img.classList.add("visible"), i * 100);
  });
  sendHeight();
});

const lb = document.createElement("div");
lb.id = "lb-overlay";
lb.innerHTML = `
  <span class="lb-close">&times;</span>
  <img src="" alt="">
  <div class="lb-caption"></div>
`;
document.body.appendChild(lb);

const lbImg = lb.querySelector("img");
const lbCap = lb.querySelector(".lb-caption");
const lbClose = lb.querySelector(".lb-close");

document.querySelectorAll(".gallery img").forEach(img => {
  img.addEventListener("click", () => {
    lb.classList.add("show");
    lbImg.src = img.src;
    lbCap.textContent = img.alt;
  });
});
lbClose.addEventListener("click", () => lb.classList.remove("show"));
lb.addEventListener("click", e => {
  if (e.target === lb) lb.classList.remove("show");
});
</script>
</body>
</html>
"""

    # === HTML出力 ===
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    print("✅ gallery HTMLを生成しました:", os.path.join(OUTPUT_DIR, "index.html"))


if __name__ == "__main__":
    generate_gallery()
