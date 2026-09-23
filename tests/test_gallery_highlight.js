const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const galleryPath = path.join(__dirname, "..", "assets", "gallery.js");
const source = fs.readFileSync(galleryPath, "utf8");
const utilityStart = source.indexOf("  function normalizeJapaneseSearch");
const utilityEnd = source.indexOf("    // =========================", utilityStart);

assert.notEqual(utilityStart, -1, "utility functions should be present");
assert.notEqual(utilityEnd, -1, "utility section boundary should be present");

const utilities = source.slice(utilityStart, utilityEnd);
const context = {};
vm.runInNewContext(`${utilities}\nthis.highlight = highlight;`, context);

const cases = [
  ["タマゴタケ", "たまご", "<mark>タマゴ</mark>タケ"],
  ["タマゴタケ", "タマゴ", "<mark>タマゴ</mark>タケ"],
  ["タマゴタケ", "ﾀﾏｺﾞ", "<mark>タマゴ</mark>タケ"],
  ["ベニテングタケ", "べにてんぐ", "<mark>ベニテング</mark>タケ"],
];

for (const [text, query, expected] of cases) {
  assert.equal(context.highlight(text, query), expected);
}

console.log(`${cases.length} kana-insensitive highlight cases passed`);
