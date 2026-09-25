document.addEventListener("DOMContentLoaded", () => {
  const tabs = Array.from(document.querySelectorAll("[data-season]"));
  const panels = Array.from(document.querySelectorAll("[data-season-panel]"));

  function selectSeason(key, focus = false) {
    tabs.forEach((tab) => {
      const selected = tab.dataset.season === key;
      tab.setAttribute("aria-selected", String(selected));
      if (selected && focus) tab.focus();
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.seasonPanel !== key;
    });
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectSeason(tab.dataset.season));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(index + offset + tabs.length) % tabs.length];
      selectSeason(next.dataset.season, true);
    });
  });
  if (tabs.length) selectSeason(tabs[0].dataset.season);
});
