'use strict';
const assert=require('node:assert/strict'),{total}=require('../assets/record-stars.js');
assert.equal(total([]),null); // Loading/failure and genuine zero have the same empty native DOM.
assert.equal(total([{kind:'star'}]),1);
assert.equal(total(Array.from({length:130},()=>({kind:'star'}))),130);
assert.equal(total([{kind:'star'},{kind:'star'},{kind:'count',count:100}]),102);
assert.equal(total([{kind:'count',count:0}]),0);
// Same username/mixed colours do not deduplicate or change a star's weight.
assert.equal(total([{kind:'star',name:'same',color:'green'},{kind:'star',name:'same',color:'red'},{kind:'count',count:5,color:'yellow'}]),7);
for(const item of [{kind:'placeholder'},{kind:'unknown'},{kind:'count',count:-1},{kind:'count',count:1.5},{kind:'count',count:'5'},{kind:'count',count:Infinity}])assert.equal(total([item]),null);
assert.equal(total([{kind:'count',count:Number.MAX_SAFE_INTEGER},{kind:'star'}]),null);
console.log('Hatena Star totals: repeated users, colours, collapsed counts, unknown/failure and integer integrity PASS');
