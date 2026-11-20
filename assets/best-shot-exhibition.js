/* Exhibition row alignment: no image manipulation, only natural-size layout.
 * On desktop, one row uses the same actual image height for both aspect ratios.
 * On mobile, CSS returns each original image to its natural full-width ratio.
 */
(() => {
  "use strict";
  const grids = [...document.querySelectorAll(".best-shot-grid")];
  if (!grids.length) return;
  const isSingleColumn = () => window.matchMedia("(max-width: 700px)").matches;
  let frame = 0;
  function alignRows() {
    frame = 0;
    for (const grid of grids) {
      const cards = [...grid.querySelectorAll(":scope > .best-shot-card")];
      if (isSingleColumn()) {
        for (const card of cards) card.querySelector(".best-shot-stage")?.style.removeProperty("--exhibit-row-height");
        continue;
      }
      const target = Math.min(240, Math.max(140, window.innerWidth * .18));
      for (let i = 0; i < cards.length; i += 2) {
        const row = cards.slice(i, i + 2);
        let height = target;
        for (const card of row) {
          const stage = card.querySelector(".best-shot-stage");
          const img = stage?.querySelector("img");
          if (stage && img?.naturalWidth && img?.naturalHeight) {
            const space = Math.max(1, stage.clientWidth - 20);
            height = Math.min(height, space * img.naturalHeight / img.naturalWidth);
          }
        }
        const size = Math.max(1, Math.floor(height)) + "px";
        for (const card of row) {
          card.querySelector(".best-shot-stage")?.style.setProperty("--exhibit-row-height", size);
        }
      }
    }
  }
  function schedule() {
    if (frame) return;
    frame = requestAnimationFrame(alignRows);
  }
  for (const img of document.querySelectorAll(".best-shot-grid .best-shot-photo img")) {
    if (!img.complete) img.addEventListener("load", schedule, { once: true });
  }
  window.addEventListener("resize", schedule);
  if ("ResizeObserver" in window) {
    const widths = new WeakMap();
    const observer = new ResizeObserver(entries => {
      for (const { target, contentRect } of entries) {
        const width = Math.round(contentRect.width);
        if (widths.get(target) !== width) {
          widths.set(target, width);
          schedule();
        }
      }
    });
    for (const grid of grids) observer.observe(grid);
  }
  schedule();
})();
