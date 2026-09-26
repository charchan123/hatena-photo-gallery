const assert = require("assert");
const { matchesFacets } = require("../assets/features.js");
assert.strictEqual(matchesFacets(["ring", "volva"], new Set()), true);
assert.strictEqual(matchesFacets(["ring", "volva"], new Set(["ring"])), true);
assert.strictEqual(matchesFacets(["ring", "volva"], new Set(["ring", "volva"])), true);
assert.strictEqual(matchesFacets(["ring"], new Set(["ring", "volva"])), false);
assert.strictEqual(matchesFacets([], new Set(["ring"])), false);
console.log("feature filter tests passed");
