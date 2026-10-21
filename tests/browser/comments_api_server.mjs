import http from "node:http";
import { createWorker } from "../../comments/worker.mjs";
import { LocalD1 } from "../../comments/tests/d1.mjs";
const db = new LocalD1(),
  rows = db.sql.prepare("SELECT * FROM cases ORDER BY rowid").all(),
  id = rows[0].id,
  secret = "isolated-browser-secret-".repeat(3),
  sha = db.sql
    .prepare("SELECT value FROM metadata WHERE key='registry_sha256'")
    .get().value;
for (let i = 0; i < 23; i++)
  db.sql
    .prepare(
      "INSERT INTO comments(id,case_id,role,nickname,body,created_at,delete_hash) VALUES(?,?,'visitor',?,?,?,?)",
    )
    .run(
      crypto.randomUUID(),
      id,
      "森の試験参加者",
      i === 0
        ? "<img src=x onerror=alert(1)> これは合成データです"
        : "試験コメント " + i,
      Date.now() - 86400000 + i,
      "f".repeat(64),
    );
const env = {
  DB: db,
  ADMIN_TOKEN: secret,
  RATE_SECRET: secret,
  PUBLIC_READ_ENABLED: "true",
  PUBLIC_WRITE_ENABLED: "true",
  RELEASE_APPROVAL: "approved",
  ALLOWED_ORIGINS: "https://charchan123.github.io",
  TURNSTILE_SECRET: secret,
  TURNSTILE_HOSTNAME: "charchan123.github.io",
  REGISTRY_SHA256: sha,
  MANIFEST_URL:
    "https://charchan123.github.io/hatena-photo-gallery/research-comment-cases.json",
};
const worker = createWorker({
  fetcher: async (url) =>
    Response.json(
      String(url).includes("siteverify")
        ? {
            success: true,
            hostname: "charchan123.github.io",
            action: "research_comment",
            challenge_ts: new Date().toISOString(),
          }
        : {
            version: 1,
            registry_sha256: sha,
            active_ids: rows.map((r) => r.id),
          },
    ),
});
let fail = false,
  publicCalls = 0;
const server = http.createServer(async (req, res) => {
  try {
    let raw = "";
    for await (const c of req) raw += c;
    if (req.url === "/__test/stats") {
      res.setHeader("Content-Type", "application/json");
      res.end(
        JSON.stringify({
          publicCalls,
          caseId: id,
          label: rows[0].label,
          firstId: db.sql
            .prepare("SELECT id FROM comments ORDER BY seq LIMIT 1")
            .get().id,
          comments: db.sql
            .prepare("SELECT id,state,role FROM comments ORDER BY seq")
            .all(),
        }),
      );
      return;
    }
    if (req.url === "/__test/fail") {
      fail = JSON.parse(raw).fail;
      res.end("{}");
      return;
    }
    if (req.url.startsWith("/v1/")) publicCalls++;
    if (fail && req.url.startsWith("/v1/")) {
      res.writeHead(503, {
        "Access-Control-Allow-Origin": "https://charchan123.github.io",
        "Content-Type": "application/json",
      });
      res.end('{"error":"SERVICE_UNAVAILABLE"}');
      return;
    }
    const headers = new Headers();
    for (const [k, v] of Object.entries(req.headers))
      if (v) headers.set(k, Array.isArray(v) ? v.join(",") : v);
    headers.set("CF-Connecting-IP", "198.51.100.2");
    const request = new Request("https://comments.fixture.test" + req.url, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method) ? undefined : raw,
    });
    const result = await worker.fetch(request, env);
    res.writeHead(result.status, Object.fromEntries(result.headers));
    res.end(await result.text());
  } catch {
    res.writeHead(500);
    res.end("{}");
  }
});
server.listen(0, "127.0.0.1", () =>
  console.log(JSON.stringify({ port: server.address().port })),
);
