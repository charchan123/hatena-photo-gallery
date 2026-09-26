
let lastHeight = 0;

function calculateIframeContentHeight(rootHeight, paddingTop, paddingBottom) {
  return Math.ceil(rootHeight + paddingTop + paddingBottom);
}

document.addEventListener("DOMContentLoaded", () => {

  // Measure normal page content independently from the iframe viewport. Nodes
  // appended to body later (LightGallery and toast UI) intentionally stay out.
  let contentRoot = document.getElementById("gallery-content-root");
  if (!contentRoot) {
    contentRoot = document.createElement("div");
    contentRoot.id = "gallery-content-root";
    const existingContent = Array.from(document.body.childNodes);
    document.body.appendChild(contentRoot);
    existingContent.forEach(node => contentRoot.appendChild(node));
  }

  // favorite.html 専用「遅延削除」
  let pendingRemove = null;

  // =========================
  // ⭐ お気に入り保存キー
  // =========================
  const LG_FAVORITES_KEY = "lg_favorites";

  // ページ全体フェードイン
  requestAnimationFrame(() => {
    document.body.style.opacity = "1";
  });

  // =========================
  // utility
  // =========================
  function normalizeSrc(src) {
    return src ? src.replace(/\?.*$/, "") : "";
  }

  function normalizeJapaneseSearch(value) {
    return (value || "")
      .normalize("NFKC")
      .toLowerCase()
      .replace(/[ァ-ヶ]/g, char =>
        String.fromCodePoint(char.codePointAt(0) - 0x60)
      );
  }

  function normalizeJapaneseSearchWithMap(value) {
    const source = value || "";
    let normalized = "";
    const sourceRanges = [];

    for (let start = 0; start < source.length;) {
      const first = source.codePointAt(start);
      let end = start + (first > 0xFFFF ? 2 : 1);

      // Keep combining and half-width voicing marks with the character they modify.
      while (end < source.length && /[\u3099\u309A\uFF9E\uFF9F]/.test(source[end])) {
        end++;
      }

      const part = normalizeJapaneseSearch(source.slice(start, end));
      normalized += part;
      for (let i = 0; i < part.length; i++) {
        sourceRanges.push({ start, end });
      }
      start = end;
    }

    return { normalized, sourceRanges };
  }

  function highlight(text, q) {
    const keyword = normalizeJapaneseSearch(q);
    if (!keyword) return text;

    const { normalized, sourceRanges } = normalizeJapaneseSearchWithMap(text);
    const ranges = [];
    let searchFrom = 0;
    let matchAt;

    while ((matchAt = normalized.indexOf(keyword, searchFrom)) !== -1) {
      const first = sourceRanges[matchAt];
      const last = sourceRanges[matchAt + keyword.length - 1];
      if (first && last) ranges.push({ start: first.start, end: last.end });
      searchFrom = matchAt + keyword.length;
    }

    if (!ranges.length) return text;

    let result = "";
    let sourceFrom = 0;
    ranges.forEach(range => {
      result += text.slice(sourceFrom, range.start);
      result += `<mark>${text.slice(range.start, range.end)}</mark>`;
      sourceFrom = range.end;
    });
    return result + text.slice(sourceFrom);
  }

    // =========================
    // ★ 閉じる統合：LGを閉じてフルスクリーンも抜ける（端末差分吸収）
    // =========================
    async function closeLGAndExitFullscreen(lgInstance) {
      // ① まず LightGallery を閉じる
      try {
        lgInstance?.closeGallery();
      } catch (e) {}

      // ② フルスクリーン解除（Android Chromeで残りがち）
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else if (document.webkitFullscreenElement) {
          await document.webkitExitFullscreen();
        }
      } catch (e) {}

      // ③ 順序逆が効く端末対策：もう一度 close
      try {
        lgInstance?.closeGallery();
      } catch (e) {}

      // ④ 親iframe側へ「閉じた」を通知（あなたの既存仕様と整合）
      try {
        window.parent.postMessage({ type: "lgClosed" }, "*");
      } catch (e) {}
    }

    // =========================
    // “見つかるまで探す” 強制表示関数を追加
    // =========================
    function forceMobileBuiltinClose(lg) {
      const isMobile = window.matchMedia("(max-width: 768px)").matches;
      if (!isMobile) return;

      let tries = 0;
      const timer = setInterval(() => {
        tries++;

        const outer = document.querySelector(".lg-outer");
        const toolbar = document.querySelector(".lg-toolbar");
        const closeBtn = document.querySelector(".lg-toolbar .lg-close");

        // ツールバーを隠すクラスが付いてる端末対策
        if (outer) outer.classList.remove("lg-hide-items");

        if (toolbar) {
          toolbar.style.opacity = "1";
          toolbar.style.pointerEvents = "auto";
          toolbar.classList.remove("lg-hide");
        }

        if (closeBtn) {
          // 表示を強制
          closeBtn.style.display = "inline-flex";
          closeBtn.style.opacity = "1";
          closeBtn.style.pointerEvents = "auto";

          // クリックを “LG閉じる + フルスクリーン解除” に統合
          if (!closeBtn.__fsBound) {
            closeBtn.__fsBound = true;
            closeBtn.addEventListener(
              "click",
              (e) => {
                e.preventDefault();
                e.stopPropagation();
                closeLGAndExitFullscreen(lg);
              },
              true
            );
          }

          clearInterval(timer);
        }

        // 2秒くらい探して無ければ諦める（暴走防止）
        if (tries > 40) clearInterval(timer);
      }, 50);
    }

  // =========================
  // 件数を返す「純ロジック関数」
  // =========================
  function getFavoriteCount() {
  // 新構造（lg_items）があれば優先
  const itemsRaw = localStorage.getItem("lg_items");
  if (itemsRaw) {
    try {
      const items = JSON.parse(itemsRaw);
      return Object.values(items).filter(
        item => item && item.favorite
      ).length;
    } catch (e) {}
  }

  // 旧構造（lg_favorites）
  const favsRaw = localStorage.getItem(LG_FAVORITES_KEY);
  if (favsRaw) {
    try {
      const favs = JSON.parse(favsRaw);
      return Object.values(favs).filter(Boolean).length;
    } catch (e) {}
  }

  return 0;
}

  // =========================
  // 件数を「外に出す」ためのフック（UI未実装）
  // =========================
    function updateFavoriteCountHook() {
      const count = getFavoriteCount();

      // 将来UI用（今は使わない）
    document.documentElement.dataset.favoriteCount = count;

    const el = document.getElementById("favorite-count");
    if (el) el.textContent = count > 0 ? `（${count}）` : "";

      // デバッグ確認用
      // console.log("⭐ 観察ノート件数:", count);
    }

    // =========================
    // iframe 高さ同期（最終・統合版）
    // =========================
    let __lastSentHeight = -1;
    let __heightScheduled = false;
    let __heightForceRequested = false;
    let __heightReason = "";

    function sendHeight(reason = "", force = false) {
      __heightForceRequested = __heightForceRequested || force;
      if (reason) __heightReason = reason;
      if (__heightScheduled) return;
      __heightScheduled = true;

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          __heightScheduled = false;
          const forceSend = __heightForceRequested;
          const messageReason = __heightReason;
          __heightForceRequested = false;
          __heightReason = "";

          const bodyStyle = window.getComputedStyle(document.body);
          const paddingTop = parseFloat(bodyStyle.paddingTop) || 0;
          const paddingBottom = parseFloat(bodyStyle.paddingBottom) || 0;
          const h = calculateIframeContentHeight(
            contentRoot.getBoundingClientRect().height,
            paddingTop,
            paddingBottom
          );

          if (!forceSend && h === __lastSentHeight) return;
          __lastSentHeight = h;

          window.parent.postMessage(
            { type: "setHeight", height: h, reason: messageReason },
            "*"
          );
        });
      });
    }

  // =========================
  // ★ お気に入り機能（localStorage）
  // =========================
  function loadFavorites() {
    try {
      return JSON.parse(localStorage.getItem(LG_FAVORITES_KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  function saveFavorites(data) {
    localStorage.setItem(LG_FAVORITES_KEY, JSON.stringify(data));
    updateFavoriteCountHook();
  }

  function getCurrentSlideSrc() {
    const img = document.querySelector(".lg-current .lg-object");
    return img ? normalizeSrc(img.getAttribute("src")) : null;
  }

  // =========================
  // Toast
  // =========================
    function showFavToast(message, anchorEl) {
      if (!anchorEl) return;

      let toast = document.querySelector(".fav-toast");
      if (!toast) {
        toast = document.createElement("div");
        toast.className = "fav-toast";
        document.body.appendChild(toast);
      }

      toast.textContent = message;

      // --- 位置計算 ---
      const rect = anchorEl.getBoundingClientRect();
      const scrollX = window.scrollX || window.pageXOffset;
      const scrollY = window.scrollY || window.pageYOffset;

      // いったん表示して幅を取得
      toast.style.left = "0px";
      toast.style.top = "0px";
      toast.classList.add("show");

      const toastRect = toast.getBoundingClientRect();

      // 基本位置：サムネの真下中央
      let left =
        scrollX +
        rect.left +
        rect.width / 2 -
        toastRect.width / 2;

      let top =
        scrollY +
        rect.bottom +
        8; // サムネ下 8px

      // =========================
      // ★ 画面端ガード（超重要）
      // =========================
      const margin = 8;
      const viewportLeft = scrollX + margin;
      const viewportRight =
        scrollX + document.documentElement.clientWidth - toastRect.width - margin;

      if (left < viewportLeft) left = viewportLeft;
      if (left > viewportRight) left = viewportRight;

      toast.style.left = left + "px";
      toast.style.top = top + "px";

      clearTimeout(toast.__timer);
      toast.__timer = setTimeout(() => {
        toast.classList.remove("show");
      }, 1400);
    }

  // =========================
  // ★ サムネ（ギャラリー）お気に入り同期
  // =========================
    function updateThumbnailFavorites() {
      document.querySelectorAll(".gallery-item").forEach(a => {
        const img = a.querySelector("img");
        const star = a.querySelector(".thumb-fav");
        if (!img || !star) return;

        const src = normalizeSrc(img.getAttribute("src"));

        if (isFavorite(src)) {
          star.textContent = "★";
          star.classList.add("is-fav");
        } else {
          star.textContent = "☆";
          star.classList.remove("is-fav");
        }
      });
    }

  // ★ サムネの★を押したらギャラリー起動を止める & お気に入り切替
    function bindThumbnailStarEvents() {
      document.querySelectorAll(".thumb-fav").forEach(star => {
        if (star.__favBound) return;
        star.__favBound = true;

        star.addEventListener("click", e => {
          e.preventDefault();
          e.stopPropagation();

          const item = star.closest(".gallery-item");
          const img = item?.querySelector("img");
          if (!img) return;

          const src = normalizeSrc(img.getAttribute("src"));

          // ⭐ 観察ノートページの場合：遅延削除
          if (document.querySelector(".favorite-gallery")) {
            scheduleRemoveFromFavorite(item, src, star);
            return;
          }

          // ---- 通常ページ（今まで通り） ----
          const favs = loadFavorites();
          favs[src] = !favs[src];
          saveFavorites(favs);

          updateThumbnailFavorites();
          updateCardFavorites();

          const count = getFavoriteCount();

          showFavToast(
            favs[src]
              ? `📓 観察ノートに追加（いま ${count}件）`
              : "📓 観察ノートから外しました",
            star
          );
        });
      });
    }

   // =========================
  // scheduleRemoveFromFavorite（UNDO付き）
  // =========================
    function scheduleRemoveFromFavorite(item, src, star) {

      // ★ ここでフェードアウトさせる
      item.style.transition = "opacity 0.25s ease";
      item.style.opacity = "0";

      // 既存の pending があれば確定
      if (pendingRemove?.timer) {
        clearTimeout(pendingRemove.timer);
        finalizeRemove(pendingRemove.src);
        pendingRemove.item?.remove();
        pendingRemove = null;
      }

      item.classList.add("removing");

      const timer = setTimeout(() => {
        finalizeRemove(src);
        updateFavoriteCountHook();
        item.remove();
        pendingRemove = null;

        requestAnimationFrame(() => {
          sendHeight("remove-final");
        })
      }, 3000);

      pendingRemove = { src, item, timer };

      showUndoToastNear(star, "観察ノートから外しました", () => {
        clearTimeout(timer);
        item.classList.remove("removing");
        item.style.opacity = "1";
        pendingRemove = null;

        requestAnimationFrame(() => sendHeight("remove-undo"));
        item.addEventListener("transitionend", () => {
          item.style.removeProperty("opacity");
          item.style.removeProperty("transition");
        }, { once: true });
      });
    }

  // =========================
  // 実削除（localStorage確定）
  // =========================
    function finalizeRemove(src) {
      const favs = loadFavorites();
      delete favs[src];
      saveFavorites(favs);

      updateCardFavorites();
    }

  // =========================
  // UNDOトースト（再利用・下固定）
  // =========================
    function showUndoToastNear(targetEl, message, onUndo) {
      let toast = document.querySelector(".fav-undo-toast");
      if (!toast) {
        toast = document.createElement("div");
        toast.className = "fav-undo-toast";
        document.body.appendChild(toast);
      }

      toast.innerHTML = `
        <span>${message}</span>
        <button class="undo-btn">元に戻す</button>
      `;

      const btn = toast.querySelector(".undo-btn");

      // 既存タイマーがあればクリア（重要）
      if (toast._hideTimer) {
        clearTimeout(toast._hideTimer);
      }

      btn.onclick = () => {
        clearTimeout(toast._hideTimer);
        toast.classList.remove("show");
        onUndo();
      };

      // ---- 位置計算 ----
      const rect = targetEl.getBoundingClientRect();
      const toastRect = toast.getBoundingClientRect();

      let left = rect.left + rect.width / 2 - toastRect.width / 2;
      const top = rect.bottom + 8 + window.scrollY;

      const margin = 8;
      left = Math.max(margin, Math.min(left, window.innerWidth - toastRect.width - margin));

      toast.style.position = "absolute";
      toast.style.left = `${left + window.scrollX}px`;
      toast.style.top = `${top}px`;

      toast.classList.add("show");

      // ★ 自動で消す（これが無かった）
      toast._hideTimer = setTimeout(() => {
        toast.classList.remove("show");
      }, 3000);
    }

  // =========================
  // ★ index/五十音カードのお気に入り同期
  // =========================
    function updateCardFavorites() {
      document.querySelectorAll(".mushroom-card").forEach(card => {
        const img = card.querySelector("img");
        const star = card.querySelector(".card-fav");
        if (!img || !star) return;

        const src = normalizeSrc(img.getAttribute("src"));

        if (isFavorite(src)) {
          star.textContent = "★";
          star.classList.add("is-fav");
        } else {
          star.textContent = "☆";
          star.classList.remove("is-fav");
        }
      });
    }

  // =========================
  // ★ LightGallery toolbar にお気に入りボタンを後付け
  // =========================
    function updateFavoriteIcon() {
      const btn = document.querySelector(".lg-fav-btn");
      if (!btn) return;

      const src = getCurrentSlideSrc();

      if (src && isFavorite(src)) {
        btn.textContent = "★";

        // ★ アニメーションを毎回確実に発火させる
        btn.classList.remove("is-fav");
        void btn.offsetWidth; // 再描画トリガ
        btn.classList.add("is-fav");

      } else {
        btn.textContent = "☆";
        btn.classList.remove("is-fav");
      }
    }

  function attachFavoriteButton() {
    const toolbar = document.querySelector(".lg-toolbar");
    if (!toolbar) return false;

    if (toolbar.querySelector(".lg-fav-btn")) return true;

    const btn = document.createElement("button");
    btn.className = "lg-icon lg-fav-btn";
    btn.title = "お気に入り";
    btn.textContent = "☆";

    btn.addEventListener("click", () => {
      const src = getCurrentSlideSrc();
      if (!src) return;

      const favs = loadFavorites();
      favs[src] = !favs[src];
      saveFavorites(favs);

      updateFavoriteIcon();
      updateThumbnailFavorites();
      updateCardFavorites();

      const count = getFavoriteCount();

      showFavToast(
        isFavorite(src)
          ? `📓 観察ノートに追加（いま ${count}件）`
          : "📓 観察ノートから外しました",
        btn
      );
    });

    toolbar.appendChild(btn);
    return true;
  }

  // toolbar がまだ無いタイミング対策（lgAfterOpen直後に遅延生成されることがある）
  function attachFavoriteButtonWithRetry() {
    let tries = 0;
    const timer = setInterval(() => {
      tries++;
      const ok = attachFavoriteButton();
      if (ok || tries > 30) {
        clearInterval(timer);
        updateFavoriteIcon();
      }
    }, 50);
  }

  // =========================
  // ★ 文脈リンク：五十音 → 詳細ページ（戻るボタン）
  // =========================
  (function () {
    const params = new URLSearchParams(location.search);
    const from = params.get("from");
    const kana = params.get("kana");

    if (from !== "aiuo" || !kana) return;

    // 既存の「← 戻る」ボタンがあれば削除（保険）
    document.querySelectorAll(".back-btn").forEach(b => b.remove());

    const nav = document.createElement("div");
    nav.style.textAlign = "center";
    nav.style.marginTop = "40px";

    nav.innerHTML = `
      <a href="${kana}.html" class="back-btn">
        ◀ ${kana}の一覧に戻る
      </a>
    `;

    const gallery = document.querySelector(".gallery");
    if (gallery) {
      gallery.after(nav);
    } else {
      document.body.appendChild(nav);
    }

    if (typeof sendHeight === "function") {
      sendHeight();
    }
  })();

  // =========================
  // ★ パンくずリスト（完全統合・1系統）
  // =========================
  (function () {
    const params = new URLSearchParams(location.search);
    const from = params.get("from");
    const kana = params.get("kana");

    const title = document.querySelector("h2");
    if (!title) return;

    let crumbHTML = "";

    // ① 〇行のキノコページ（あ行.html など）
    const pathMatch = location.pathname.match(/\/([^\/]+行)\.html$/);
    if (pathMatch && !from) {
      const k = pathMatch[1];
      crumbHTML = `
        <a href="index.html">トップ</a>
        <span> › </span>
        <span>五十音</span>
        <span> › </span>
        <span style="color:#999;">${k}</span>
      `;
    }
    // ② キノコ詳細ページ
    else if (from === "aiuo" && kana) {
      crumbHTML = `
        <a href="index.html">トップ</a>
        <span> › </span>
        <a href="${kana}.html">五十音 › ${kana}</a>
        <span> › </span>
        <span style="color:#999;">${title.textContent}</span>
      `;
    }
    else if (from === "index") {
      crumbHTML = `
        <a href="index.html">トップ</a>
        <span> › </span>
        <a href="index.html">全キノコ検索</a>
        <span> › </span>
        <span style="color:#999;">${title.textContent}</span>
      `;
    }
    else if (from === "recommend") {
      crumbHTML = `
        <a href="index.html">トップ</a>
        <span> › </span>
        <a href="index.html#recommend">おすすめキノコ</a>
        <span> › </span>
        <span style="color:#999;">${title.textContent}</span>
      `;
    } else {
      return; // 直アクセスは出さない
    }

    const nav = document.createElement("nav");
    nav.style.textAlign = "center";
    nav.style.fontSize = "13px";
    nav.style.margin = "8px 0 16px";
    nav.style.color = "#666";
    nav.innerHTML = crumbHTML;

    title.before(nav);

    if (typeof sendHeight === "function") sendHeight();
  })();

// =========================
// ギャラリー処理（LightGallery）
// .gallery / .favorite-gallery 両対応
// =========================
const galleries = document.querySelectorAll(
  ".gallery, .favorite-gallery"
);

galleries.forEach(gallery => {

  // =========================
  // 通常ギャラリーのみ：画像フェードイン
  // （観察ノートでは使わない）
  // =========================
  if (gallery.classList.contains("gallery")) {
    const fadeObs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add("visible");
          fadeObs.unobserve(e.target);
        }
      });
    }, { threshold: 0.1 });

    gallery.querySelectorAll("img").forEach(img => fadeObs.observe(img));
  }

  imagesLoaded(gallery, () => {
    gallery.style.visibility = "visible";

    // 初期同期
    updateThumbnailFavorites();
    updateCardFavorites();
    bindThumbnailStarEvents();
    sendHeight();

    // =========================
    // LightGallery 起動
    // =========================
    const lg = lightGallery(gallery, {
      selector: "a.gallery-item",
      plugins: [lgZoom, lgThumbnail, lgShare, lgAutoplay],
      speed: 400,
      thumbnail: true,
      showThumbByDefault: true,
      toggleThumb: true,
      thumbWidth: 80,
      thumbMargin: 6,
      download: false,
      zoom: true,
      autoplay: true,
      pause: 3000,
      progressBar: true,
    });

    // Wrapped captions can settle after LightGallery's initial measurement.
    // Re-reserve the measured caption and thumbnail height for the image area.
    function reserveCaptionSpace() {
      requestAnimationFrame(() => {
        const position = lg.getMediaContainerPosition();
        lg.mediaContainerPosition = position;
        lg.setMediaContainerPosition(position.top, position.bottom);
      });
    }

    // =========================
    // LightGalleryイベント：お気に入り連携
    // =========================
    gallery.addEventListener("lgAfterOpen", () => {
      reserveCaptionSpace();
      attachFavoriteButtonWithRetry();
      updateFavoriteIcon();
      updateThumbnailFavorites();
      updateCardFavorites();

      showLGHintOnce();

      forceMobileBuiltinClose(lg);

      const btn = document.querySelector(".lg-fav-btn");
      if (btn) {
        btn.classList.toggle("is-fav", !!loadFavorites()[getCurrentSlideSrc()]);
      }

      // =========================
      // ★ スマホだけ：標準×を強制表示 + 統合クローズ
      // =========================
      const isMobile = window.matchMedia("(max-width: 768px)").matches;
      if (!isMobile) return;

      const builtInClose = document.querySelector(".lg-toolbar .lg-close");
      if (!builtInClose) return;

      // 表示強制（スマホで隠れる端末対策）
      builtInClose.style.display = "inline-flex";
      builtInClose.style.opacity = "1";
      builtInClose.style.pointerEvents = "auto";

      // クリックを「LG閉じる + フルスクリーン解除」に差し替え
      if (!builtInClose.__fsBound) {
        builtInClose.__fsBound = true;
        builtInClose.addEventListener(
          "click",
          (e) => {
            e.preventDefault();
            e.stopPropagation();
            closeLGAndExitFullscreen(lg);
          },
          true
        );
      }
    });

    gallery.addEventListener("lgAfterSlide", () => {
      reserveCaptionSpace();
      updateFavoriteIcon();
      updateThumbnailFavorites();
      updateCardFavorites();
    });

    // =========================
    // クリックでフルスクリーン
    // =========================
    gallery.querySelectorAll("a.gallery-item").forEach(a => {
      a.addEventListener("click", () => {
        const el = document.documentElement;
        if (el.requestFullscreen) el.requestFullscreen();
        else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
        else if (el.msRequestFullscreen) el.msRequestFullscreen();
      });
    });

    gallery.addEventListener("lgBeforeClose", () => {
      updateThumbnailFavorites();
      updateCardFavorites();

      // ★ ここでもフルスクリーン解除（保険）
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }

      // ★ 親へ通知（既存仕様）
      window.parent.postMessage({ type: "lgClosed" }, "*");
    });

    gallery.addEventListener("lgAfterClose", () => {
      updateThumbnailFavorites();
      updateCardFavorites();
    });

    document.addEventListener("fullscreenchange", () => {
      // フルスクリーンが解除されたら、LGも閉じる（逆方向の整合）
      if (!document.fullscreenElement) {
        closeLGAndExitFullscreen(lg);
      }
    });
  });
});

  // =========================
  // scrollToTitle 判定（既存）
  // =========================
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;

    const txt = a.textContent || "";
    const href = a.getAttribute("href") || "";

    if (/\.html(\?|$)/.test(href)) {
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }

    if (/^(あ行|か行|さ行|た行|な行|は行|ま行|や行|ら行|わ行)$/.test(txt)) {
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }

    if (/戻る/.test(txt)) {
      window.parent.postMessage({ type: "scrollToTitle" }, "*");
      return;
    }
  });

  // =========================
  // 五十音ページ 検索＋かなフィルタ
  // =========================
  const searchInput = document.querySelector(".search-input");
  const kanaButtons = document.querySelectorAll(".kana-btn");
  const cards = document.querySelectorAll(".mushroom-card");

  if (searchInput && cards.length) {
    let currentKana = "all";

    function applyFilter() {
      const q = searchInput.value.trim();
      const keyword = normalizeJapaneseSearch(q);

      cards.forEach(card => {
        const rawName = card.getAttribute("data-name") || "";
        const name = normalizeJapaneseSearch(rawName);
        const kana = card.getAttribute("data-kana") || "";

        const matchText = !keyword || name.includes(keyword);
        const matchKana = currentKana === "all" || kana === currentKana;
        const show = matchText && matchKana;

        card.style.display = show ? "" : "none";

        const nameEl = card.querySelector(".mushroom-card-name");
        if (nameEl) {
          nameEl.innerHTML = keyword
            ? highlight(rawName, searchInput.value.trim())
            : rawName;
        }
      });

      updateEmptyState();
      updateCardFavorites();
      sendHeight();
    }

    function updateEmptyState() {
      const hasQuery = searchInput.value.trim() !== "" || currentKana !== "all";
      if (!hasQuery) {
        const empty = document.querySelector(".search-empty");
        if (empty) empty.style.display = "none";
        return;
      }

      const visible = Array.from(cards).some(c => c.style.display !== "none");

      let empty = document.querySelector(".search-empty");
      if (!empty) {
        empty = document.createElement("div");
        empty.className = "search-empty";
        empty.innerHTML = `
          🔍 該当するキノコが見つかりませんでした<br>
          <small>別の文字で試してみてください</small>
        `;
        document.querySelector(".mushroom-list")?.after(empty);
      }
      empty.style.display = visible ? "none" : "block";
    }

    searchInput.addEventListener("input", applyFilter);

    kanaButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        kanaButtons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        document.querySelectorAll(".aiuo-link")
          .forEach(l => l.classList.remove("current"));

        const kana = btn.getAttribute("data-kana") || "all";
        document.querySelector(`.aiuo-link[data-kana="${kana}"]`)
          ?.classList.add("current");

        currentKana = kana;
        applyFilter();
      });
    });
  }

  // =========================
  // ⭐ お気に入り専用ページ描画（favorite.html）
  // =========================
    function renderFavoritePage() {
      const gallery = document.querySelector(".favorite-gallery");
      if (!gallery) return;

      const favs = loadFavorites();
      const srcs = Object.keys(favs).filter(src => favs[src]);

      gallery.innerHTML = "";

      const empty = document.querySelector(".favorite-empty");
      if (srcs.length === 0) {
        empty && (empty.style.display = "block");
        sendHeight();
        return;
      }
      empty && (empty.style.display = "none");

      // =========================
      // 季節ごとにグループ化
      // =========================
      const groups = {};

    srcs.forEach(src => {
      const info = getDateFromExif(src);

      let key, year, season;

      if (info) {
        season = getSeason(info.month);
        year = info.year;
        key = `${year}-${season}`;
      } else {
        // ★ EXIFが無い写真の逃げ道
        year = "";
        season = "日付不明";
        key = "unknown";
      }

      if (!groups[key]) {
        groups[key] = {
          year,
          season,
          items: []
        };
      }

      groups[key].items.push(src);
    });

      // =========================
      // 年月順に並び替え（古 → 新）
      // =========================
      const sortedGroups = Object.values(groups).sort((a, b) => {
        const am = a.year * 12 + seasonOrder(a.season);
        const bm = b.year * 12 + seasonOrder(b.season);
        return am - bm;
      });

      // =========================
      // 描画
      // =========================
      sortedGroups.forEach(group => {
        const block = document.createElement("section");
        block.className = "season-block";

        block.appendChild(
          createSeasonHeader(group.year, group.season)
        );

        const grid = document.createElement("div");
        grid.className = "season-grid";

        group.items.forEach(src => {
          const a = document.createElement("a");
          a.className = "gallery-item";
          a.href = src;
          a.setAttribute("data-sub-html", buildNoteCaption(src));
          a.innerHTML = `
            <span class="thumb-fav is-fav">★</span>
            <span class="spores"></span>
            <img src="${src}" loading="lazy">
          `;
          grid.appendChild(a);
        });

        block.appendChild(grid);
        gallery.appendChild(block);
      });

      bindThumbnailStarEvents();
      sendHeight();
    }

    // 季節の並び順（春→夏→秋→冬）
    function seasonOrder(season){
      return { 春:1, 夏:2, 秋:3, 冬:4 }[season] || 9;
    }

  // =========================
  // 観察ノートギャラリー表示時にクラスを付与
  // =========================
  function animateFavoriteGallery() {
      const items = document.querySelectorAll(
        ".favorite-gallery .gallery-item"
      );

      items.forEach((item, i) => {
        item.style.transition = "opacity 0.35s ease, transform 0.35s ease";
        item.style.transitionDelay = `${i * 40}ms`;

        requestAnimationFrame(() => {
          item.style.opacity = "1";
          item.style.transform = "translateY(0)";
        });
      });
  }

  // =========================
  // 観察ノート専用のキャプション関数
  // =========================
    function buildNoteCaption(src){
      const name = window.SRC_TO_ALT?.[src] || "";
      const meta = window.EXIF_CACHE?.[src];
      const date = meta?.date || "";

      if (!name && !date) return "";

      return `
        <div class="exif-wrap">
          ${name ? `<div class="exif-title">${name}</div>` : ""}
          ${date ? `
            <div class="exif-bottom-row">
              <span>📷 ${date}</span>
            </div>
          ` : ""}
        </div>
      `;
    }

  // =========================
  // EXIF から年・月を取り出す関数
  // =========================
    function getDateFromExif(src){
      const cache = window.EXIF_CACHE;
      if (!cache) return null;

      const meta = cache[src];
      if (!meta || !meta.date) return null;

      // "YYYY/MM/DD" → Date
      const d = new Date(meta.date.replace(/\//g, "-"));
      if (isNaN(d)) return null;

      return {
        year: d.getFullYear(),
        month: d.getMonth() + 1
      };
    }

  // =========================
  // 季節判定ロジック
  // =========================
    function getSeason(month){
      if ([12,1,2].includes(month)) return "冬";
      if ([3,4,5].includes(month))  return "春";
      if ([6,7,8].includes(month))  return "夏";
      return "秋";
    }

  // =========================
  // 見出しHTMLを作る関数
  // =========================
    function createSeasonHeader(year, season){
      const h = document.createElement("div");
      h.className = "season-header";
      h.innerHTML = year
        ? `<span>${year}年 ${season}</span>`
        : `<span>${season}</span>`;
      return h;
    }

  // =========================
  // フルスクリーン起動時のヒント表示（初回のみ）
  // =========================
    function showLGHintOnce() {
      if (localStorage.getItem("lg_hint_shown")) return;

      localStorage.setItem("lg_hint_shown", "1");

      // ★ 標準フルスクリーンヒントが消えるのを待つ
      setTimeout(() => {
        const hint = document.createElement("div");
        hint.className = "lg-hint";
        hint.innerHTML = "👆 スワイプで写真を見る<br>✕ で戻ると、観察ノートから見返せます";

        document.body.appendChild(hint);

        setTimeout(() => {
          hint.remove();
        }, 3600);
      }, 3000); // ← ここが重要
    }

  // =========================
  // ★キャッシュ方式
  // =========================
  function isFavorite(src) {
      const favs = loadFavorites();
      return !!favs[src];
    }

  // =========================
  // index 横断検索（ページネーション含む）
  // =========================
  const indexSearchInput = document.querySelector(".index-search-input");
  const indexResults = document.querySelector(".index-search-results");
  const emptyEl = document.querySelector(".section .search-empty");

  if (indexSearchInput && indexResults) {
    const ALL_MUSHROOMS = window.ALL_MUSHROOMS || [];
    let page = 1;
    const PER_PAGE = 30;

    function renderResults(list, q = "") {
      if (!q) {
        indexResults.innerHTML = "";
        emptyEl && (emptyEl.style.display = "none");
        return;
      }

      if (list.length === 0) {
        indexResults.innerHTML = "";
        emptyEl && (emptyEl.style.display = "block");
        return;
      }

      emptyEl && (emptyEl.style.display = "none");

      indexResults.innerHTML = list.map(item => `
        <a href="${item.href}?from=index&q=${encodeURIComponent(q)}"
           class="mushroom-card search-result-item">
          <div class="mushroom-card-thumb">
            <span class="card-fav">☆</span>
            <img src="${item.thumb}" alt="${item.name}">
          </div>
          <div class="mushroom-card-name">
            ${highlight(item.name, q)}
          </div>
        </a>
      `).join("");

      updateCardFavorites();
    }

    function updateURL(q, page) {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (page > 1) params.set("page", page);
      history.replaceState(null, "", "?" + params.toString());
    }

    function loadFromURL() {
      const params = new URLSearchParams(location.search);
      return {
        q: params.get("q") || "",
        p: Number(params.get("page") || 1)
      };
    }

    function renderPagination(totalPages) {
      const wrap = document.querySelector(".index-pagination");
      if (!wrap) return;

      if (totalPages <= 1) {
        wrap.innerHTML = "";
        return;
      }

      wrap.innerHTML = `
        <span class="index-page-btn ${page <= 1 ? "disabled" : ""}" data-move="-1">前へ</span>
        <span style="margin:0 10px;">${page} / ${totalPages}</span>
        <span class="index-page-btn ${page >= totalPages ? "disabled" : ""}" data-move="1">次へ</span>
      `;

      wrap.querySelectorAll(".index-page-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          page += Number(btn.dataset.move);
          doSearch();
          window.parent.postMessage({ type: "scrollToTitle" }, "*");
        });
      });
    }

    function doSearch() {
      const rawQ = indexSearchInput.value.trim().normalize("NFKC");
      const q = normalizeJapaneseSearch(rawQ);

      const filtered = rawQ
        ? ALL_MUSHROOMS.filter(m =>
            normalizeJapaneseSearch(m.name_norm || m.name).includes(q)
          )
        : [];

      const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
      page = Math.min(Math.max(1, page), totalPages);

      const start = (page - 1) * PER_PAGE;
      renderResults(filtered.slice(start, start + PER_PAGE), rawQ);

      renderPagination(rawQ ? totalPages : 0);
      updateURL(rawQ, page);
      sendHeight();
    }

    const { q, p } = loadFromURL();
    indexSearchInput.value = q;
    page = p;
    doSearch();

    indexSearchInput.addEventListener("input", () => {
      page = 1;
      doSearch();
    });
  }

  // =========================
  // カード★ 初期同期（index / 五十音ページ用）
  // =========================
  updateCardFavorites();

  renderFavoritePage();

  // =========================
  // 更新タイミングにだけフックする（ページ初期表示時）
  // =========================
  updateFavoriteCountHook();

  // =========================
  // 高さ監視。ResizeObserver は増加・減少の両方を検知する主系統。
  // =========================
  sendHeight();

  window.addEventListener("load", () => {
    sendHeight("load", true);
    setTimeout(() => sendHeight("load-800ms", true), 800);
    setTimeout(() => sendHeight("load-2000ms", true), 2000);
  });

  // A bfcache-restored document remembers its previous height, while the
  // parent iframe may still have the page we navigated to. Re-send even when
  // the measured value is unchanged; bounded retries cover restored images.
  window.addEventListener("pageshow", event => {
    const prefix = event.persisted ? "pageshow-bfcache" : "pageshow";
    sendHeight(prefix, true);
    setTimeout(() => sendHeight(`${prefix}-100ms`, true), 100);
    setTimeout(() => sendHeight(`${prefix}-800ms`, true), 800);
    setTimeout(() => sendHeight(`${prefix}-2000ms`, true), 2000);
  });

  window.addEventListener("message", e => {
    if (e.data?.type === "requestHeight") sendHeight("request-height", true);
  });

  window.addEventListener("resize", sendHeight);

    if ("ResizeObserver" in window) {
      const contentResizeObserver = new ResizeObserver(() => {
        sendHeight("resize-observer");
      });
      contentResizeObserver.observe(contentRoot);
    } else {
      // 古いブラウザでは通常コンテンツだけを監視し、overlay/toastを除外する。
      new MutationObserver(() => {
        sendHeight("mutation-fallback");
      }).observe(contentRoot, {
        childList: true,
        subtree: true,
        attributes: true,
        characterData: true
      });
    }

});
