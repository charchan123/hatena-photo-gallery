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
const next=(id,own)=>context.monthSlots(id,own).next;
assert.equal(next('a'),1);
state.best_shots.entries=[{selection_id:'one',observation_id:'b',order:1}];
assert.equal(next('a'),2);
state.best_shots.entries.push({selection_id:'three',observation_id:'c',order:3});
assert.equal(next('a'),2);
assert.equal(next('a','one'),1);
assert.equal(next('d'),1);
state.best_shots.entries.push({selection_id:'two',observation_id:'a',order:2});
assert.equal(next('a'),4);
assert.equal(next('a','two'),2);
for(const count of [1,3,4,10,30,35]){
 state.best_shots.entries=Array.from({length:count},(_,i)=>({selection_id:'slot-'+i,observation_id:'a',order:i+1}));
 assert.equal(next('b'),count+1);assert.equal(next('d'),1);
 state.best_shots.entries.splice(Math.floor(count/2),1);
 assert.equal(next('b'),Math.floor(count/2)+1);
}
state.best_shots.entries=[{selection_id:'sparse',observation_id:'a',order:1000000}];assert.equal(next('b'),1);
for(const value of ['1','3','4','10','30','999',' 31 '])assert.equal(context.bestShotOrder(value),Number(value));
for(const value of ['',null,undefined,'0','-1','1.5','1e2','Infinity','9007199254740993'])assert.equal(context.bestShotOrder(value),null);
assert.equal(context.captureMonth({capture:{date:'2026-02-30'}}),'');
assert.equal(context.captureMonth({capture:{date:null}}),'');
console.log('Best Shot search, unbounded month counts, smallest missing order and integer input: passed');
