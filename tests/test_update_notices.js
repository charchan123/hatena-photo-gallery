const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
let now = 1000;
const nodes = [
  {dataset: {noticeStart: "1000", noticeEnd: "2000"}},
  {dataset: {noticeStart: "2000", noticeEnd: "3000"}},
  {dataset: {noticeStart: "bad", noticeEnd: "4000"}}
];
const events = {};
let scheduled;
const document = {hidden: false, querySelectorAll: () => nodes,
  addEventListener: (name, callback) => { events[name] = callback; }};
const context = {document, Date: {now: () => now},
  window: {addEventListener: (name, callback) => { events[name] = callback; }},
  clearTimeout: () => {}, setTimeout: (callback, delay) => { scheduled = {callback, delay}; }};
vm.runInNewContext(fs.readFileSync("assets/update-notices.js", "utf8"), context);
assert.deepEqual(nodes.map(n => n.hidden), [false, true, true]);
assert.equal(scheduled.delay, 1025);
now = 2000;
scheduled.callback();
assert.deepEqual(nodes.map(n => n.hidden), [true, false, true]);
now = 3000;
events.pageshow();
assert(nodes.every(n => n.hidden));
now = 1500;
events.visibilitychange();
assert.deepEqual(nodes.map(n => n.hidden), [false, true, true]);
console.log("Update notices: expiry, transition, bfcache, visibility, invalid dates PASS");
