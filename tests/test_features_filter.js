const assert = require("assert");
const { matchesFacets, setCardVisibility, updateCardChipHighlights } = require("../assets/features.js");
assert.strictEqual(matchesFacets(["ring", "volva"], new Set()), true);
assert.strictEqual(matchesFacets(["ring", "volva"], new Set(["ring"])), true);
assert.strictEqual(matchesFacets(["ring", "volva"], new Set(["ring", "volva"])), true);
assert.strictEqual(matchesFacets(["ring"], new Set(["ring", "volva"])), false);
assert.strictEqual(matchesFacets([], new Set(["ring"])), false);
const card = { style: { display: "initial" } };
setCardVisibility(card, true);
assert.strictEqual(card.style.display, "");
setCardVisibility(card, false);
assert.strictEqual(card.style.display, "none");

function fakeChip(facet) {
  return {
    dataset: { facetChip: facet },
    selected: false,
    classList: {
      toggle(name, enabled) {
        assert.strictEqual(name, "is-selected");
        this.owner.selected = enabled;
      },
      owner: null
    }
  };
}
const ringChip = fakeChip("ring");
const volvaChip = fakeChip("volva");
ringChip.classList.owner = ringChip;
volvaChip.classList.owner = volvaChip;
const chipCard = { querySelectorAll: () => [ringChip, volvaChip] };
const selected = new Set(["ring"]);
updateCardChipHighlights(chipCard, selected);
assert.strictEqual(ringChip.selected, true);
assert.strictEqual(volvaChip.selected, false);
selected.add("volva");
updateCardChipHighlights(chipCard, selected);
assert.strictEqual(ringChip.selected, true);
assert.strictEqual(volvaChip.selected, true);
selected.clear();
updateCardChipHighlights(chipCard, selected);
assert.strictEqual(ringChip.selected, false);
assert.strictEqual(volvaChip.selected, false);
console.log("feature filter tests passed");
