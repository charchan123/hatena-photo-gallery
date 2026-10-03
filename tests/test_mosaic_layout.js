const assert = require("assert");
const {
  MOSAIC_GAP,
  MAX_CROP_RATIO,
  SINGLE_MAX_WIDTH,
  computeMosaicLayout,
} = require("../assets/mosaic-layout.js");

function verify(ratios, width, columns) {
  const layout = computeMosaicLayout(ratios, width, columns, MOSAIC_GAP, {
    maxCropRatio: MAX_CROP_RATIO,
  });
  assert.strictEqual(layout.gap, 10);
  assert.ok(layout.maxBottomError <= 1);
  assert.strictEqual(layout.items.length, ratios.length);
  assert.deepStrictEqual(layout.items.map(item => item.index).sort((a, b) => a - b),
    ratios.map((_, index) => index));
  assert.ok(layout.items.every(item => item.cropRatio <= MAX_CROP_RATIO));
  layout.columns.forEach(column => {
    const tiles = column.items.map(index => layout.items[index]);
    for (let i = 1; i < tiles.length; i++) {
      assert.ok(Math.abs(tiles[i].top - tiles[i - 1].top - tiles[i - 1].height - MOSAIC_GAP) < 1e-7);
    }
    assert.ok(Math.abs(column.bottom - layout.height) < 1e-7);
  });
  return layout;
}

const single = verify([4 / 3], 1080, 1);
assert.ok(single.width <= SINGLE_MAX_WIDTH);
assert.deepStrictEqual(single.items[0].corners, ["tl", "tr", "bl", "br"]);

const pair = verify([4 / 3, 3 / 4], 850, 2);
assert.strictEqual(pair.columns[0].bottom, pair.columns[1].bottom);
assert.deepStrictEqual(pair.items[0].corners, ["tl", "bl"]);
assert.deepStrictEqual(pair.items[1].corners, ["tr", "br"]);

verify([0.62, 1.55, 0.8, 1.9, 1.2], 1080, 5);
verify([1.5, 0.75, 1.2, 1.8, 0.66, 1.33, 0.9, 2, 0.7, 1.1, 1.65, 0.82, 1.4, 0.6, 1.75], 1080, 5);
verify([0.25, 4, 0.3, 3.5, 0.4, 3, 0.5, 2.8, 0.35, 4.2], 1080, 5);

console.log("5 fixed-gap mosaic layout cases passed");
