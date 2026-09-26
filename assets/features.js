(function (root) {
  "use strict";

  function matchesFacets(cardFacets, selectedFacets) {
    return Array.from(selectedFacets).every(function (facet) {
      return cardFacets.indexOf(facet) !== -1;
    });
  }

  function setCardVisibility(card, show) {
    card.style.display = show ? "" : "none";
  }

  function setupFeatureFilters(doc) {
    var buttons = Array.from(doc.querySelectorAll(".feature-filter"));
    var cards = Array.from(doc.querySelectorAll(".feature-card"));
    var count = doc.querySelector(".feature-result-count");
    var empty = doc.querySelector(".feature-empty");
    var clear = doc.querySelector(".feature-clear");
    var selected = new Set();

    function update() {
      var visible = 0;
      cards.forEach(function (card) {
        var facets = (card.dataset.facets || "").split(/\s+/).filter(Boolean);
        var show = matchesFacets(facets, selected);
        setCardVisibility(card, show);
        if (show) visible += 1;
      });
      count.textContent = visible + "種類";
      empty.hidden = visible !== 0;
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var facet = button.dataset.facet;
        if (selected.has(facet)) selected.delete(facet); else selected.add(facet);
        button.setAttribute("aria-pressed", selected.has(facet) ? "true" : "false");
        update();
      });
    });
    clear.addEventListener("click", function () {
      selected.clear();
      buttons.forEach(function (button) { button.setAttribute("aria-pressed", "false"); });
      update();
    });
    update();
    return { selected: selected, update: update };
  }

  if (typeof module !== "undefined") module.exports = {
    matchesFacets: matchesFacets,
    setCardVisibility: setCardVisibility
  };
  if (root.document) root.document.addEventListener("DOMContentLoaded", function () { setupFeatureFilters(root.document); });
}(typeof window !== "undefined" ? window : globalThis));
