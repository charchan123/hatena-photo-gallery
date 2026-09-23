const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const galleryPath = path.join(__dirname, "..", "assets", "gallery.js");
const source = fs.readFileSync(galleryPath, "utf8");

const helperStart = source.indexOf("function calculateIframeContentHeight");
const helperEnd = source.indexOf("\ndocument.addEventListener", helperStart);
assert.notEqual(helperStart, -1, "height helper should be present");
assert.notEqual(helperEnd, -1, "height helper boundary should be present");

const context = { Math };
vm.runInNewContext(
  `${source.slice(helperStart, helperEnd)}\nthis.calculate = calculateIframeContentHeight;`,
  context
);

assert.equal(context.calculate(868.2, 16, 16), 901);
assert.equal(context.calculate(2368, 16, 16), 2400);
assert.equal(context.calculate(868, 16, 16), 900, "a smaller height is not clamped");

assert.match(source, /getElementById\("gallery-content-root"\)/);
assert.match(source, /contentRoot\.getBoundingClientRect\(\)\.height/);
assert.match(source, /getComputedStyle\(document\.body\)/);
assert.match(source, /contentResizeObserver\.observe\(contentRoot\)/);
assert.match(source, /type: "setHeight", height: h, reason/);
assert.doesNotMatch(source, /document\.body\.(?:scrollHeight|offsetHeight)/);
assert.doesNotMatch(source, /document\.documentElement\.(?:scrollHeight|offsetHeight)/);

console.log("iframe content height regression checks passed");
