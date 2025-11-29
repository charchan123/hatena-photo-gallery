// gallery.js
(async function() {
  const container = document.getElementById("mushroomGallery");
  if (!container) return;

  // CSS読み込み
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "https://charchan123.github.io/hatena-photo-gallery/gallery.css";
  document.head.appendChild(css);

  // ギャラリーHTML読み込み
  try {
    const res = await fetch("https://charchan123.github.io/hatena-photo-gallery/index.html");
    if (!res.ok) throw new Error("HTML取得失敗");
    const html = await res.text();
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = "<p>ギャラリーの読み込みに失敗しました。</p>";
    console.error(e);
    return;
  }

  // imagesLoaded 読み込み
  const script = document.createElement("script");
  script.src = "https://unpkg.com/imagesloaded@5/imagesloaded.pkgd.min.js";
  document.body.appendChild(script);
  await new Promise(res => script.onload = res);

  const gallery = container.querySelector(".gallery");
  if (!gallery) return;

  // ====== Fade-in Animation ======
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

  // ====== Lightbox ======
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
})();

