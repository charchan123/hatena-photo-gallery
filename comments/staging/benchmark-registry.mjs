// Offline Node/SQLite process CPU benchmark. Never a Cloudflare CPU measurement.
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import { cpus } from "node:os";
import registry from "../cases.json" with { type: "json" };
import manifest from "./manifest.json" with { type: "json" };
import { canonical, digest } from "../worker.mjs";
import { LocalD1 } from "../tests/d1.mjs";
import { createRegistryChecker } from "./registry.mjs";

const baseline = "582a6c19e136fe5f7f6b2c2448cb0f63f14d1235";
const source = execFileSync("git",["show",baseline+":comments/staging/worker.mjs"],{encoding:"utf8"});
const begin=source.indexOf("async function checkRegistry(env) {"),end=source.indexOf("\nexport function createStagingWorker",begin);
if(begin<0||end<0)throw Error("PINNED_BASELINE_UNAVAILABLE");
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
// Execute the exact pinned baseline function, not a rewritten approximation.
const old=new AsyncFunction("registry","manifest","canonical","digest","env",
  source.slice(begin,end)+"\nreturn checkRegistry(env);");
const db=new LocalD1(),env={DB:db,REGISTRY_SHA256:manifest.registry_sha256,
  STAGING_INSTALLATION_ID:db.sql.prepare("SELECT value FROM metadata WHERE key='installation_id'").get().value};
let shaCalls=0,reads=0;
const native=crypto.subtle.digest.bind(crypto.subtle),prepare=db.prepare.bind(db);
crypto.subtle.digest=(...args)=>{shaCalls++;return native(...args);};
db.prepare=sql=>{reads++;return prepare(sql);};
const fresh=()=>createRegistryChecker(registry,manifest);
const oldCheck=()=>old(registry,manifest,canonical,digest,env);
const optimized=fresh();
async function measure(operation,count){
  const start=process.cpuUsage(),wall=performance.now(),h=shaCalls,r=reads;
  for(let i=0;i<count;i++)await operation();
  const cpu=process.cpuUsage(start);
  return {calls:count,cpu_ms:(cpu.user+cpu.system)/1000,wall_ms:performance.now()-wall,
    sha_calls:shaCalls-h,d1_reads:reads-r};
}
const first=await measure(()=>optimized(env),1);
await measure(oldCheck,20); await measure(()=>optimized(env),20);
const samples=[];
for(let i=0;i<7;i++){
  // Alternate ordering to reduce systematic warmup/scheduling bias.
  let before,after;
  if(i%2){after=await measure(()=>optimized(env),100);before=await measure(oldCheck,100);}
  else{before=await measure(oldCheck,100);after=await measure(()=>optimized(env),100);}
  samples.push({before,after});
}
const median=a=>a.sort((a,b)=>a-b)[Math.floor(a.length/2)];
const before=median(samples.map(s=>s.before.cpu_ms/s.before.calls));
const after=median(samples.map(s=>s.after.cpu_ms/s.after.calls));
const cold=await measure(()=>fresh()(env),20);
const result={environment:"LOCAL Node process CPU + in-memory SQLite; no JWT/network/Cloudflare CPU claim",
  baseline,node:process.version,platform:process.platform,arch:process.arch,cpu:cpus()[0]?.model,
  cases:registry.cases.length,samples,first_request:first,cold_20_instances:cold,
  median_cpu_ms_per_check:{before,after,reduction_percent:100*(1-after/before)},
  warm_sha_per_check:{before:67,after:0},d1_full_reads_per_check:{before:3,after:3},
  remote_mutations:[]};
if(process.argv[2])writeFileSync(process.argv[2],JSON.stringify(result,null,2)+"\n");
console.log(JSON.stringify(result,null,2));
crypto.subtle.digest=native;db.sql.close();
