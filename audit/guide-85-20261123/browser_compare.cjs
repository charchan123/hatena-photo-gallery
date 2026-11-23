const fs = require("node:fs");
const assert = require("node:assert/strict");

const base = JSON.parse(fs.readFileSync("browser-base.json"));
const draft = JSON.parse(fs.readFileSync("browser-draft.json"));
assert.equal(Object.keys(base.result).length, 85);
assert.deepEqual(Object.keys(draft.result).sort(), Object.keys(base.result).sort());

for (const [id, formats] of Object.entries(base.result)) {
  for (const [width, before] of Object.entries(formats)) {
    const after = draft.result[id][width];
    assert.equal(after.warning, before.warning, id);
    assert.equal(after.warningCount, 1, id);
    assert.equal(after.safetyLabel, before.safetyLabel, id);
    assert.ok(before.sourceLinks.every(url => after.sourceLinks.includes(url)), id);
    assert.ok(after.opened && after.linksVisible, id);
    assert.ok(after.labels.includes("科名") && after.labels.includes("属名") && after.labels.includes("生態"), id);
    assert.ok(after.outerOverflow <= Math.max(1, before.outerOverflow), id);
    assert.ok(!after.overlaps || before.overlaps, id);
    assert.ok(after.spills.every(field => before.spills.includes(field)), id);
  }
}
for (const width of Object.keys(base.flow)) {
  assert.ok(base.flow[width].opened && base.flow[width].closed, JSON.stringify(base.flow));
  assert.ok(draft.flow[width].opened && draft.flow[width].closed, JSON.stringify(draft.flow));
  assert.ok(draft.flow[width].scrollDifference <= Math.max(3, base.flow[width].scrollDifference));
}
console.log("PASS: 85 pinned pages at both widths, original source links and food text preserved, no added overflow; LightGallery opens, closes and restores scroll.");
