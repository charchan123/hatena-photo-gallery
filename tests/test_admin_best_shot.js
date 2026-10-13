'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('admin/static/admin.js','utf8');
const helper=source.slice(source.indexOf('function normalizeMushroomName'),source.indexOf('function observationSelect'));
const observations=[
 {observation_id:'a',gallery_name:'ベニテングタケ',capture:{date:'2026-10-01'}},
 {observation_id:'b',gallery_name:'ベニテングタケ',capture:{date:'2026-10-02'}},
 {observation_id:'c',gallery_name:'バライロウラベニイロガワリ',capture:{date:'2026-10-03'}},
 {observation_id:'d',gallery_name:'ベニタケ',capture:{date:'2026-09-03'}},
];
const state={observations,best_shots:{entries:[]}};
const context=vm.createContext({state,observation:id=>observations.find(o=>o.observation_id===id)||{}});
vm.runInContext(helper,context);
const normalize=context.normalizeMushroomName;
const find=query=>observations.filter(o=>normalize(o.gallery_name).includes(normalize(query))).map(o=>o.observation_id);
assert.deepEqual(find('べ'),['a','b','c','d']);
assert.deepEqual(find('ベニテ'),find('べにて'));
assert.deepEqual(find('ﾍﾞﾆﾃ'),['a','b']);
assert.deepEqual(find(''),['a','b','c','d']);
assert.deepEqual(find('見つからない'),[]);
assert.equal(normalize('ＡＢＣ　べ'),normalize('abc ベ'));
const slots=(id,own)=>Array.from(context.monthSlots(id,own).free);
assert.deepEqual(slots('a'),[1,2,3]);
state.best_shots.entries=[{selection_id:'one',observation_id:'b',order:1}];
assert.deepEqual(slots('a'),[2,3]);
state.best_shots.entries.push({selection_id:'three',observation_id:'c',order:3});
assert.deepEqual(slots('a'),[2]);
assert.deepEqual(slots('a','one'),[1,2]);
assert.deepEqual(slots('d'),[1,2,3]);
state.best_shots.entries.push({selection_id:'two',observation_id:'a',order:2});
assert.equal(context.monthSlots('a').full,true);
assert.deepEqual(slots('a'),[]);
assert.equal(context.monthSlots('a','two').full,false);
assert.equal(context.captureMonth({capture:{date:'2026-02-30'}}),'');
assert.equal(context.captureMonth({capture:{date:null}}),'');
console.log('Best Shot search normalization and available month slots: passed');
