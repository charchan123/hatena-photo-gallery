import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { LocalD1 } from "./d1.mjs";
import { createWorker, digest, mac, text } from "../worker.mjs";
import { restoreLocal, verifyBackup } from "../tools/restore.mjs";
const registry = JSON.parse(
    readFileSync(new URL("../cases.json", import.meta.url)),
  ),
  id = registry.cases[0].id,
  origin = "https://charchan123.github.io",
  now = Date.now(),
  secret = "isolated-test-secret-".repeat(3);
function setup() {
  const db = new LocalD1(),
    sha = db.sql
      .prepare("SELECT value FROM metadata WHERE key='registry_sha256'")
      .get().value;
  const env = {
    DB: db,
    ADMIN_TOKEN: secret,
    RATE_SECRET: secret,
    PUBLIC_READ_ENABLED: "true",
    PUBLIC_WRITE_ENABLED: "true",
    RELEASE_APPROVAL: "approved",
    ALLOWED_ORIGINS: origin,
    TURNSTILE_SECRET: secret,
    TURNSTILE_HOSTNAME: "charchan123.github.io",
    REGISTRY_SHA256: sha,
    MANIFEST_URL: origin + "/hatena-photo-gallery/research-comment-cases.json",
  };
  let human = true,
    manifest = true,
    network = false;
  const worker = createWorker({
    clock: () => now,
    fetcher: async (url) => {
      if (network) throw Error("network");
      return Response.json(
        String(url).includes("siteverify")
          ? {
              success: human,
              hostname: "charchan123.github.io",
              action: "research_comment",
              challenge_ts: new Date(now).toISOString(),
            }
          : {
              version: 1,
              registry_sha256: sha,
              active_ids: manifest ? [id] : [],
            },
      );
    },
  });
  let ip = 0;
  async function call(
    path,
    body,
    { admin = false, auth = true, headers = {} } = {},
  ) {
    const req = new Request("https://fixture.test" + path, {
      method: body ? "POST" : "GET",
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(admin
          ? auth
            ? { Authorization: "Bearer " + secret }
            : {}
          : { Origin: origin, "CF-Connecting-IP": "192.0.2." + ++ip }),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const r = await worker.fetch(req, env);
    return { status: r.status, data: await r.json(), headers: r.headers };
  }
  const post = (body) => call("/v1/cases/" + id + "/comments", body);
  const packet = () => ({
    request_id: crypto.randomUUID(),
    nickname: "森の観察者",
    body: "同定のヒントです",
    delete_token: "a".repeat(64),
    turnstile_token: "synthetic-challenge",
  });
  return {
    db,
    env,
    worker,
    call,
    post,
    packet,
    human: (v) => (human = v),
    manifest: (v) => (manifest = v),
    network: (v) => (network = v),
  };
}
const route = "/v1/cases/" + id + "/comments";
async function action(s, comment_id, kind, body) {
  return s.call(
    "/admin/action",
    {
      request_id: crypto.randomUUID(),
      comment_id,
      action: kind,
      ...(body ? { body } : {}),
    },
    { admin: true },
  );
}
test("production closed by default and missing safety secrets fail closed", async () => {
  const s = setup();
  delete s.env.PUBLIC_WRITE_ENABLED;
  assert.equal((await s.post(s.packet())).status, 503);
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM comments").get().n, 0);
  s.env.PUBLIC_WRITE_ENABLED = "true";
  delete s.env.TURNSTILE_SECRET;
  assert.equal((await s.post(s.packet())).status, 503);
});
test("visitor post is immediate, oldest first, paginated and never official", async () => {
  const s = setup();
  for (let n = 0; n < 23; n++) {
    const p = s.packet();
    p.body = "投稿 " + n;
    assert.equal((await s.post(p)).status, 200);
  }
  const first = await s.call(route);
  assert.equal(first.data.comments.length, 20);
  assert.equal(first.data.comments[0].body, "投稿 0");
  assert.equal(first.data.comments[0].official, false);
  const second = await s.call(route + "?after=" + first.data.next_cursor);
  assert.equal(second.data.comments.length, 3);
  assert.equal(second.data.next_cursor, null);
  assert.ok(!JSON.stringify(first.data).includes("delete_hash"));
});
test("strict payload lengths Unicode, reserved names, spoofed role and injection are handled", async () => {
  const s = setup();
  for (const extra of [
    { role: "admin" },
    { parent_id: crypto.randomUUID() },
    { official: true },
    { nickname: "管 理 人" },
    { nickname: "ＯＦＦＩＣＩＡＬ" },
    { body: "x".repeat(501) },
    { nickname: "x".repeat(31) },
  ])
    assert.equal((await s.post({ ...s.packet(), ...extra })).status, 400);
  assert.equal(text("🍄".repeat(500), 500), "🍄".repeat(500));
  const p = s.packet();
  p.body = "<script>alert(1)</script>'); DROP TABLE comments;--";
  assert.equal((await s.post(p)).status, 200);
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM comments").get().n, 1);
});
test("Turnstile rejection/unavailability and stale case manifest do not insert", async () => {
  const s = setup();
  s.human(false);
  assert.equal((await s.post(s.packet())).status, 400);
  s.human(true);
  s.manifest(false);
  assert.equal((await s.post(s.packet())).status, 409);
  s.network(true);
  assert.equal((await s.post(s.packet())).status, 503);
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM comments").get().n, 0);
});
test("request replay returns same ID, changed payload fails, deleted post cannot resurrect", async () => {
  const s = setup(),
    p = s.packet();
  const first = await s.post(p),
    again = await s.post(p);
  assert.equal(first.data.comment.id, again.data.comment.id);
  assert.equal((await s.post({ ...p, body: "different" })).status, 409);
  await s.call(route + "/" + first.data.comment.id + "/delete", {
    delete_token: p.delete_token,
  });
  assert.equal((await s.post(p)).data.comment.state, "deleted");
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM comments").get().n, 1);
});
test("delete requires secret, erases content and reports, invalidates token and stays possible with posting disabled", async () => {
  const s = setup(),
    p = s.packet(),
    c = (await s.post(p)).data.comment;
  assert.equal(
    (
      await s.call(route + "/" + c.id + "/delete", {
        delete_token: "b".repeat(64),
      })
    ).status,
    403,
  );
  await s.call(route + "/" + c.id + "/reports", {
    request_id: crypto.randomUUID(),
    reason: "確認してください",
    turnstile_token: "test",
  });
  s.env.PUBLIC_WRITE_ENABLED = "false";
  assert.equal(
    (
      await s.call(route + "/" + c.id + "/delete", {
        delete_token: p.delete_token,
      })
    ).status,
    200,
  );
  assert.equal(
    (
      await s.call(route + "/" + c.id + "/delete", {
        delete_token: p.delete_token,
      })
    ).status,
    403,
  );
  const row = s.db.sql.prepare("SELECT * FROM comments").get();
  assert.equal(row.body, null);
  assert.equal(row.nickname, null);
  assert.equal(row.delete_hash, null);
  assert.equal(
    s.db.sql.prepare("SELECT reason FROM reports").get().reason,
    null,
  );
  assert.equal((await action(s, c.id, "restore")).status, 409);
});
test("reports are review-only, do not hide and deduplicate per actor", async () => {
  const s = setup(),
    c = (await s.post(s.packet())).data.comment;
  for (let i = 0; i < 2; i++)
    assert.equal(
      (
        await s.call(
          route + "/" + c.id + "/reports",
          {
            request_id: crypto.randomUUID(),
            reason: "理由",
            turnstile_token: "test",
          },
          { headers: { "CF-Connecting-IP": "203.0.113.1" } },
        )
      ).status,
      200,
    );
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM reports").get().n, 1);
  assert.equal((await s.call(route)).data.comments[0].state, "visible");
});
test("atomic per-IP limits and hostile CORS block requests", async () => {
  const s = setup();
  for (let i = 0; i < 3; i++)
    assert.equal(
      (
        await s.call(route, s.packet(), {
          headers: { "CF-Connecting-IP": "203.0.113.1" },
        })
      ).status,
      200,
    );
  assert.equal(
    (
      await s.call(route, s.packet(), {
        headers: { "CF-Connecting-IP": "203.0.113.1" },
      })
    ).status,
    429,
  );
  assert.equal(
    (
      await s.call(route, s.packet(), {
        headers: { Origin: "https://evil.test" },
      })
    ).status,
    403,
  );
  const r = await s.call(route);
  assert.equal(r.headers.get("Access-Control-Allow-Origin"), origin);
  assert.equal(r.headers.get("Access-Control-Allow-Credentials"), null);
});
test("admin authentication, official reply, review/hide/restore and audit are enforced", async () => {
  const s = setup(),
    c = (await s.post(s.packet())).data.comment;
  assert.equal(
    (await s.call("/admin/cases", null, { admin: true, auth: false })).status,
    401,
  );
  const cors = await s.call("/admin/cases", null, {
    admin: true,
    headers: { Origin: origin },
  });
  assert.equal(cors.status, 401);
  assert.equal(cors.headers.get("Access-Control-Allow-Origin"), null);
  assert.equal(
    (await action(s, c.id, "reply", "同定の情報ありがとうございます")).status,
    200,
  );
  let list = (await s.call(route)).data.comments;
  assert.equal(list[1].official, true);
  assert.equal(list[1].parent_id, c.id);
  await action(s, c.id, "review");
  await action(s, c.id, "hide");
  assert.equal((await s.call(route)).data.comments.length, 0);
  await action(s, c.id, "restore");
  assert.equal((await s.call(route)).data.comments.length, 2);
  const h = await s.call("/admin/history?comment_id=" + c.id, null, {
    admin: true,
  });
  assert.deepEqual(
    h.data.audit.map((x) => x.action),
    ["review", "hide", "restore"],
  );
});
test("database forbids alias reassignment and identity change", () => {
  const s = setup();
  assert.throws(() =>
    s.db.sql
      .prepare("UPDATE aliases SET case_id=? WHERE alias=?")
      .run(registry.cases[1].id, id),
  );
  assert.throws(() =>
    s.db.sql
      .prepare("UPDATE cases SET identity_hash=? WHERE id=?")
      .run("changed", id),
  );
});
test("signed consistent backup and offline restore preserve later author deletion", async () => {
  const s = setup(),
    p = s.packet(),
    c = (await s.post(p)).data.comment;
  await action(s, c.id, "reply", "公式の返信");
  const old = (await s.call("/admin/backup", null, { admin: true })).data;
  await verifyBackup(old, secret);
  await s.call(route + "/" + c.id + "/delete", {
    delete_token: p.delete_token,
  });
  const current = (await s.call("/admin/backup", null, { admin: true })).data;
  const db = join(
    mkdtempSync(join(tmpdir(), "comment-restore-")),
    "local.sqlite",
  );
  const r = await restoreLocal(old, current, db, secret);
  assert.equal(r.deleted_preserved, 1);
  const sql = new DatabaseSync(db);
  assert.equal(
    sql.prepare("SELECT state,body FROM comments WHERE id=?").get(c.id).state,
    "deleted",
  );
  assert.equal(
    sql.prepare("SELECT body FROM comments WHERE id=?").get(c.id).body,
    null,
  );
  assert.equal(sql.prepare("PRAGMA foreign_key_check").all().length, 0);
  sql.close();
  const tampered = structuredClone(old);
  tampered.data.comments[0].case_id = registry.cases[1].id;
  await assert.rejects(verifyBackup(tampered, secret));
  const other = setup(),
    different = (await other.call("/admin/backup", null, { admin: true })).data;
  await assert.rejects(
    restoreLocal(old, different, db + "2", secret),
    /CASE_BINDING/,
  );
});
test("D1 batch failure rolls back mutation and receipt", async () => {
  const s = setup(),
    before = s.db.sql.prepare("SELECT count(*) n FROM comments").get().n;
  const b = s.db.batch.bind(s.db);
  s.db.batch = async (statements) =>
    b([...statements, s.db.prepare("INSERT INTO missing_table(x) VALUES(1)")]);
  assert.equal((await s.post(s.packet())).status, 503);
  assert.equal(
    s.db.sql.prepare("SELECT count(*) n FROM comments").get().n,
    before,
  );
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM requests").get().n, 0);
});

test("restore before a later post-and-delete retains its receipt against resurrection by retry", async () => {
  const s = setup(),
    old = (await s.call("/admin/backup", null, { admin: true })).data;
  const packet = s.packet(),
    comment = (await s.post(packet)).data.comment;
  await s.call(route + "/" + comment.id + "/delete", {
    delete_token: packet.delete_token,
  });
  const current = (await s.call("/admin/backup", null, { admin: true })).data;
  const file = join(
    mkdtempSync(join(tmpdir(), "deleted-replay-")),
    "restored.sqlite",
  );
  await restoreLocal(old, current, file, secret);
  s.db.sql.close();
  s.db.sql = new DatabaseSync(file);
  const replay = await s.post(packet);
  assert.equal(replay.status, 200);
  assert.equal(replay.data.comment.state, "deleted");
  assert.equal(replay.data.comment.body, null);
  assert.equal(s.db.sql.prepare("SELECT count(*) n FROM comments").get().n, 1);
  s.db.sql.close();
});
