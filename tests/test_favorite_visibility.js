const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/gallery.js', 'utf8');
const selection = source.match(/const srcs = Object\.keys\(favs\)\.filter\([\s\S]*?\);/)[0];
function visible(favs, names) {
  return Array.from(vm.runInNewContext(`${selection}\nsrcs`, {favs, window:{SRC_TO_ALT:names}}));
}
test('stored retired URL cannot recreate a favorite card, storage stays unchanged', () => {
  const saved = {current:true, retired:true, off:false};
  assert.deepEqual(visible(saved, {current:'シイタケ'}), ['current']);
  assert.deepEqual(saved, {current:true, retired:true, off:false});
});
test('current photo without EXIF remains visible and shared valid URL is retained', () => {
  assert.deepEqual(visible({shared:true}, {shared:'ヒラタケ'}), ['shared']);
});
test('missing published index and inherited property cannot authorize an old URL', () => {
  assert.deepEqual(visible({retired:true}, undefined), []);
  assert.deepEqual(visible({retired:true}, Object.create({retired:'stale'})), []);
});
