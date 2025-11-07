// gallery.js（はてなブログ対応版ラッパーJS）
(function() {
  // CSS読み込み
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "https://charchan123.github.io/hatena-photo-gallery/gallery.css";
  document.head.appendChild(css);

  // DOMが読み込まれたらギャラリー生成
  document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("mushroomGallery");
    if (!container) return;

    // ===== ギャラリーHTML =====
    container.innerHTML = `
      <div class="gallery">
        <img src="https://charchan123.github.io/hatena-photo-gallery/images/sample1.jpg" alt="キノコ1" loading="lazy" data-url="#">
        <img src="https://charchan123.github.io/hatena-photo-gallery/images/sample2.jpg" alt="キノコ2" loading="lazy" data-url="#">
        <img src="https://charchan123.github.io/hatena-photo-gallery/images/sample3.jpg" alt="キノコ3" loading="lazy" data-url="#">
        <!-- 他の画像もここに追加 -->
      </div>
    `;

    // ===== imagesLoaded 読み込み =====
    const script = document.createElement("script");
    script.src = "https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js";
    document.body.appendChild(script);
    script.onload = () => {
      const gallery = container.querySelector(".gallery");
      if (!gallery) return;

      // ===== Fade-in Animation =====
      const fadeObs = new IntersectionObserver(entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            fadeObs.unobserve(e.target);
          }
        });
      }, { threshold: 0.1 });

      const imgs = gallery.querySelectorAll("img");
      imgs.forEach(img => fadeObs.observe(img));

      imagesLoaded(gallery, () => {
        gallery.style.visibility = "visible";
      });

      // ===== Lightbox =====
      const lb = document.createElement("div");
      lb.id = "lb-overlay";
      lb.innerHTML = `
        <span class="lb-close">&times;</span>
        <img src="" alt="">
        <div class="lb-caption"></div>
        <a class="lb-link" href="#" target="_blank">元記事を見る</a>
      `;
      document.body.appendChild(lb);

      const lbImg = lb.querySelector("img");
      const lbCaption = lb.querySelector(".lb-caption");
      const lbLink = lb.querySelector(".lb-link");
      const lbClose = lb.querySelector(".lb-close");

      imgs.forEach(img => {
        img.addEventListener("click", () => {
          lb.classList.add("show");
          lbImg.src = img.src;
          lbCaption.textContent = img.alt || "";
          lbLink.href = img.dataset.url || "#";
        });
      });

      lbClose.addEventListener("click", () => lb.classList.remove("show"));
      lb.addEventListener("click", e => {
        if (e.target === lb) lb.classList.remove("show");
      });
    };
  });
})();
