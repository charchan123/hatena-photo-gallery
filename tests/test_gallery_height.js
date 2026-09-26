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

const context = {
  Math,
  performance: { getEntriesByType: () => [{ type: "navigate" }] }
};
vm.runInNewContext(
  `${source.slice(helperStart, helperEnd)}\n` +
    "this.calculate = calculateIframeContentHeight;\n" +
    "this.isHistoryTraversal = isHistoryTraversal;",
  context
);

assert.equal(context.calculate(868.2, 16, 16), 901);
assert.equal(context.calculate(2368, 16, 16), 2400);
assert.equal(context.calculate(868, 16, 16), 900, "a smaller height is not clamped");
assert.equal(context.isHistoryTraversal({ persisted: true }), true);
assert.equal(context.isHistoryTraversal({ persisted: false }), false);
context.performance.getEntriesByType = () => [{ type: "back_forward" }];
assert.equal(context.isHistoryTraversal({ persisted: false }), true);

assert.match(source, /getElementById\("gallery-content-root"\)/);
assert.match(source, /contentRoot\.getBoundingClientRect\(\)\.height/);
assert.match(source, /getComputedStyle\(document\.body\)/);
assert.match(source, /contentResizeObserver\.observe\(contentRoot\)/);
assert.match(source, /type: "setHeight", height: h, reason/);
assert.match(source, /function sendHeight\(reason = "", force = false\)/);
assert.match(source, /!forceSend && h === __lastSentHeight/);
assert.match(source, /addEventListener\("pageshow"/);
assert.match(source, /event\.persisted/);
assert.match(source, /isHistoryTraversal\(event\)/);
assert.match(source, /navigation\?\.type === "back_forward"/);
assert.match(source, /if \(isHistoryTraversal\(event\)\) \{\s*window\.parent\.postMessage\(\{ type: "scrollToTitle" \}, "\*"\)/);
assert.match(source, /sendHeight\(prefix, true\)/);
assert.match(source, /sendHeight\("request-height", true\)/);
assert.match(source, /sendHeight\("resize-observer"\)/);
assert.doesNotMatch(source, /document\.body\.(?:scrollHeight|offsetHeight)/);
assert.doesNotMatch(source, /document\.documentElement\.(?:scrollHeight|offsetHeight)/);

assert.match(source, /\/\\\.html\(\\\?\|\$\)\/.test\(href\)/);
assert.match(source, /if \(\/戻る\/.test\(txt\)\)/);

console.log("iframe content height regression checks passed");
