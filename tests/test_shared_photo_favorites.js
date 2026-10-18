const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/gallery.js', 'utf8');
const helper = source.match(/function isUnregisteredSharedPhoto\(src\) \{[\s\S]*?\n  \}/)[0];
function unavailable(src, blocked) {
  return vm.runInNewContext(helper+'\nisUnregisteredSharedPhoto(src)', {
    src, normalizeSrc: s => s ? s.replace(/\?.*$/, '') : '',
    document: {querySelectorAll: selector => {
      assert.equal(selector, '.gallery-item[data-favorite-eligible="false"]');
      return blocked.map(href => ({getAttribute: key => key==='href' ? href : null}));
    }}
  });
}
test('HTML-only photo cannot be favorited from enlarged view; registered photos remain usable', () => {
  assert.equal(unavailable('https://cdn.test/shared.jpg', ['https://cdn.test/shared.jpg']), true);
  assert.equal(unavailable('https://cdn.test/shared.jpg?width=300', ['https://cdn.test/shared.jpg']), true);
  assert.equal(unavailable('https://cdn.test/registered.jpg', ['https://cdn.test/shared.jpg']), false);
  assert.equal(unavailable('https://cdn.test/shared.jpg', []), false);
  assert.equal(unavailable(null, []), false);
});
