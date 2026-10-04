/* Recheck on cached-page restores and at the next boundary, without rebuilding. */
(function () {
  "use strict";
  let timer;
  function refresh() {
    clearTimeout(timer);
    const now = Date.now();
    let next = Infinity;
    document.querySelectorAll("[data-notice-start]").forEach(function (node) {
      const start = Number(node.dataset.noticeStart);
      const end = Number(node.dataset.noticeEnd);
      const valid = Number.isFinite(start) && Number.isFinite(end) && start < end;
      node.hidden = !valid || now < start || now >= end;
      if (valid) {
        if (start > now) next = Math.min(next, start);
        if (end > now) next = Math.min(next, end);
      }
    });
    if (Number.isFinite(next)) timer = setTimeout(refresh, Math.min(next - now + 25, 2147483647));
  }
  refresh();
  window.addEventListener("pageshow", refresh);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) refresh();
  });
})();
