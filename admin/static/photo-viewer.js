"use strict";

(() => {
  const dialog = document.querySelector("#admin-photo-viewer");
  const photo = dialog.querySelector("img"), frame = dialog.querySelector("figure");
  const caption = dialog.querySelector("figcaption"), counter = dialog.querySelector("output");
  const close = dialog.querySelector(".viewer-close"), prev = dialog.querySelector(".viewer-prev");
  const next = dialog.querySelector(".viewer-next");
  let entries = [], index = 0, trigger, start;
  function display() {
    const entry = entries[index];
    photo.src = entry.src;
    photo.alt = entry.alt;
    caption.textContent = entry.caption || entry.alt;
    counter.textContent = `${index + 1} / ${entries.length}`;
    prev.disabled = index === 0;
    next.disabled = index === entries.length - 1;
    prev.hidden = next.hidden = entries.length < 2;
  }
  function move(offset) {
    const candidate = index + offset;
    if (candidate >= 0 && candidate < entries.length) {
      index = candidate;
      display();
    }
  }
  close.onclick = () => dialog.close();
  prev.onclick = () => move(-1);
  next.onclick = () => move(1);
  dialog.addEventListener("click", event => {
    if (event.target === dialog || event.target === frame) dialog.close();
  });
  dialog.addEventListener("keydown", event => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      move(event.key === "ArrowLeft" ? -1 : 1);
    }
  });
  dialog.addEventListener("touchstart", event => {
    start = event.touches.length === 1 ? event.touches[0] : undefined;
  }, {passive: true});
  dialog.addEventListener("touchmove", event => {
    if (event.touches.length > 1) start = undefined;
  }, {passive: true});
  dialog.addEventListener("touchend", event => {
    if (start && !event.touches.length) {
      const touch = event.changedTouches[0];
      const dx = touch.clientX - start.clientX;
      if (Math.abs(dx) > 50 && Math.abs(dx) > 2 * Math.abs(touch.clientY - start.clientY)) move(dx < 0 ? 1 : -1);
    }
    start = undefined;
  }, {passive: true});
  dialog.addEventListener("close", () => {
    photo.removeAttribute("src");
    if (trigger?.isConnected) trigger.focus({preventScroll: true});
  });
  window.adminPhotoViewer = {
    open(photos, selected, source) {
      entries = photos.filter(entry => entry.src);
      index = entries.indexOf(selected);
      if (index < 0) return;
      trigger = source;
      display();
      if (!dialog.open) dialog.showModal();
      close.focus({preventScroll: true});
    },
    close() { if (dialog.open) dialog.close(); },
  };
})();
