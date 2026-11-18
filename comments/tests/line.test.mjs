import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { LocalD1 } from "./d1.mjs";
import { notifyComments } from "../line/notify.mjs";
import { createWorker } from "../worker.mjs";

const now = Date.parse("2026-11-18T01:00:00Z"), secret = "synthetic-line-test-".repeat(3);
function setup() {
  const db = new LocalD1();
  db.sql.exec(readFileSync(new URL("../line/0001_outbox.sql", import.meta.url), "utf8"));
  const id = db.sql.prepare("SELECT id FROM cases LIMIT 1").get().id,
    env = { DB: db, LINE_ENABLED: "true", LINE_MONTHLY_LIMIT: "200",
      LINE_CHANNEL_ACCESS_TOKEN: secret, LINE_RECIPIENT_ID: "U" + "a".repeat(32),
      LINE_START_AT: new Date(now - 1000).toISOString(), RELEASE_APPROVAL: "approved",
      PUBLIC_READ_ENABLED: "true", PUBLIC_WRITE_ENABLED: "true" };
  const pushes = [];
  let response = 200, usage = 0, acceptedHeader = false, network = false;
  const fetcher = async (url, options) => {
    assert.equal(options.redirect, "error");
    if (url.endsWith("/quota")) return Response.json({type:"limited",value:200});
    if (url.endsWith("/quota/consumption")) return Response.json({totalUsage:usage});
    pushes.push({body: options.body, key: options.headers["X-Line-Retry-Key"]});
    if (network) throw Error("synthetic timeout");
    return new Response("{}", {status:response,headers:acceptedHeader ? {"x-line-accepted-request-id":"synthetic-accepted"} : {}});
  };
  const post = (created = now) => {
    const uuid = crypto.randomUUID();
    db.sql.prepare("INSERT INTO comments(id,case_id,role,nickname,body,created_at,delete_hash) VALUES(?,?,'visitor',?,?,?,?)")
      .run(uuid,id,"森の観察者","合成コメント🍄",created,"f".repeat(64));
    db.sql.prepare("INSERT INTO requests(key,kind,payload_hash,resource_id,created_at) VALUES(?,'post',?,?,?)")
      .run(crypto.randomUUID(),"a".repeat(64),uuid,created);
    return uuid;
  };
  const send = (time = now) => notifyComments(env,{fetcher,now:time});
  const row = id => db.sql.prepare("SELECT * FROM line_outbox WHERE comment_id=?").get(id);
  return {db,env,id,post,pushes,fetcher,send,row, response:(v,h=false)=>{response=v;acceptedHeader=h},
    usage:v=>{usage=v},network:v=>{network=v}};
}
test("outbox is part of the comment transaction and excludes official replies", async () => {
  const s = setup();
  const before = s.db.sql.prepare("SELECT count(*) n FROM line_outbox").get().n;
  await assert.rejects(s.db.batch([
    s.db.prepare("INSERT INTO comments(id,case_id,role,nickname,body,created_at,delete_hash) VALUES(?,?,'visitor','観察者','合成',?,?)")
      .bind(crypto.randomUUID(),s.id,now,"f".repeat(64)),
    s.db.prepare("INSERT INTO not_a_table VALUES(1)").bind(),
  ]));
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM line_outbox").get().n,before);
  const parent = s.post(), reply = crypto.randomUUID();
  s.db.sql.prepare("INSERT INTO comments(id,case_id,parent_id,role,nickname,body,created_at) VALUES(?,?,?,'admin','管理人','返信',?)")
    .run(reply,s.id,parent,now);
  assert.equal(s.row(reply),undefined);
  await s.send();
  assert.equal(s.pushes.length,1);
});
test("disabled, closed, invalid settings and missing extension never send", async () => {
  const s = setup();s.post();
  for (const [key,value] of [["LINE_ENABLED","false"],["PUBLIC_READ_ENABLED","false"],
    ["PUBLIC_WRITE_ENABLED","false"],["RELEASE_APPROVAL","not-approved"],
    ["LINE_MONTHLY_LIMIT","201"],["LINE_MONTHLY_LIMIT","0"],["LINE_RECIPIENT_ID","invalid"]]) {
    const saved=s.env[key];s.env[key]=value;
    assert.equal((await s.send()).status,"disabled");s.env[key]=saved;
  }
  assert.equal(s.pushes.length,0);
  s.env.DB=new LocalD1();
  assert.equal((await s.send()).status,"unavailable");
});
test("one committed comment sends once with a stable case link and no localhost link", async () => {
  const s=setup(), id=s.post();
  assert.equal((await s.send()).accepted,1);
  await s.send();
  assert.equal(s.pushes.length,1);
  assert.equal(s.row(id).state,"sent");
  assert.equal(s.row(id).payload,null);
  assert.equal(s.pushes[0].key,id);
  const body=JSON.parse(s.pushes[0].body);
  assert.equal(body.to,s.env.LINE_RECIPIENT_ID);
  assert.match(body.messages[0].text,/合成コメント🍄/);
  assert.ok(body.messages[0].text.includes("#comments-"+s.id));
  assert.ok(!body.messages[0].text.includes("127.0.0.1"));
});
test("uncertain timeout retries identical content and recipient using the same LINE retry key", async () => {
  const s=setup(),id=s.post();s.network(true);
  await s.send();
  assert.equal(s.row(id).state,"pending");
  s.db.sql.prepare("UPDATE cases SET label='名称変更' WHERE id=?").run(s.id);
  s.network(false);s.response(409,true);
  await s.send(now+60001);
  assert.deepEqual(s.pushes[0],s.pushes[1]);
  assert.equal(s.row(id).state,"sent");
  assert.equal(s.db.sql.prepare("SELECT reserved FROM line_budget").get().reserved,1);
});
test("concurrent drains claim each message once and reserve the hard monthly cap atomically", async () => {
  const s=setup();s.env.LINE_MONTHLY_LIMIT="1";s.post();s.post();
  await Promise.all([s.send(),s.send()]);
  assert.equal(s.pushes.length,1);
  assert.equal(s.db.sql.prepare("SELECT reserved FROM line_budget").get().reserved,1);
  await s.send(now+600001);
  assert.equal(s.pushes.length,1);
});
test("hidden, deleted, uncommitted and pre-activation comments do not notify", async () => {
  const s=setup(), hidden=s.post(),deleted=s.post(),uncommitted=s.post();
  s.db.sql.prepare("UPDATE comments SET state='hidden' WHERE id=?").run(hidden);
  s.db.sql.prepare("UPDATE comments SET state='deleted',nickname=NULL,body=NULL,delete_hash=NULL WHERE id=?").run(deleted);
  s.db.sql.prepare("DELETE FROM requests WHERE resource_id=?").run(uncommitted);
  s.post(now-2000);await s.send();
  assert.equal(s.pushes.length,0);
  assert.equal(s.row(deleted).state,"cancelled");
});
test("deletion scrubs a pending payload after a timeout", async () => {
  const s=setup(),id=s.post();s.network(true);await s.send();
  assert.ok(s.row(id).payload);
  s.db.sql.prepare("UPDATE comments SET state='deleted',nickname=NULL,body=NULL,delete_hash=NULL WHERE id=?").run(id);
  assert.equal(s.row(id).payload,null);assert.equal(s.row(id).state,"cancelled");
  s.network(false);await s.send(now+60001);assert.equal(s.pushes.length,1);
});
test("changed recipient, retry age and month rollover stop uncertain re-delivery", async () => {
  for (const kind of ["recipient","age","month"]) {
    const s=setup(),id=s.post();s.network(true);await s.send();s.network(false);
    let time=now+60001;
    if(kind==="recipient")s.env.LINE_RECIPIENT_ID="U"+"b".repeat(32);
    if(kind==="age")time=now+23*3600000+1;
    if(kind==="month")time=Date.parse("2026-12-01T00:00:00Z");
    await s.send(time);assert.equal(s.pushes.length,1);assert.equal(s.row(id).state,"stopped");
  }
});
test("quota exhaustion pauses sends and permanent auth errors stop a batch", async () => {
  const s=setup();s.post();s.post();s.usage(200);await s.send();
  assert.equal(s.pushes.length,0);
  s.usage(0);s.response(401);await s.send();
  assert.equal(s.pushes.length,1);
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM line_outbox WHERE state='stopped'").get().n,1);
});
test("confirmed POST succeeds and duplicate replay has one queue entry despite a LINE outage", async () => {
  const s=setup(),sha=s.db.sql.prepare("SELECT value FROM metadata WHERE key='registry_sha256'").get().value,
    origin="https://charchan123.github.io", waits=[];
  Object.assign(s.env,{RATE_SECRET:secret,ADMIN_TOKEN:secret,TURNSTILE_SECRET:secret,
    TURNSTILE_HOSTNAME:"charchan123.github.io",ALLOWED_ORIGINS:origin,REGISTRY_SHA256:sha,
    MANIFEST_URL:origin+"/hatena-photo-gallery/research-comment-cases.json"});
  const worker=createWorker({clock:()=>now,fetcher:async (url,options)=>{
    if(String(url).startsWith("https://api.line.me/"))throw Error("offline");
    return Response.json(String(url).includes("siteverify")
      ? {success:true,hostname:"charchan123.github.io",action:"research_comment",challenge_ts:new Date(now).toISOString()}
      : {version:1,registry_sha256:sha,active_ids:[s.id]});
  }});
  const body={request_id:crypto.randomUUID(),nickname:"観察者",body:"合成コメント",delete_token:"a".repeat(64),turnstile_token:"synthetic"};
  const post=()=>worker.fetch(new Request("https://fixture.test/v1/cases/"+s.id+"/comments",{
    method:"POST",headers:{"Content-Type":"application/json",Origin:origin,"CF-Connecting-IP":"192.0.2.1"},body:JSON.stringify(body)
  }),s.env,{waitUntil:p=>waits.push(p)});
  assert.equal((await post()).status,200);
  assert.equal((await (await post()).json()).duplicate,true);
  await Promise.all(waits);
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM line_outbox").get().n,1);
  assert.equal(waits.length,1);
});
