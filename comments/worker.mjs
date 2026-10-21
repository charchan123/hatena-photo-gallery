// No deployment side effects. All public flags default closed; secrets are bindings.
export const TABLES = [
  "metadata",
  "cases",
  "aliases",
  "comments",
  "requests",
  "reports",
  "audit",
];
export const canonical = (v) =>
  Array.isArray(v)
    ? "[" + v.map(canonical).join(",") + "]"
    : v && typeof v === "object"
      ? "{" +
        Object.keys(v)
          .sort()
          .map((k) => JSON.stringify(k) + ":" + canonical(v[k]))
          .join(",") +
        "}"
      : JSON.stringify(v);
const bytes = (s) => new TextEncoder().encode(s),
  hex = (a) =>
    [...new Uint8Array(a)].map((n) => n.toString(16).padStart(2, "0")).join("");
export const digest = async (s) =>
  hex(await crypto.subtle.digest("SHA-256", bytes(s)));
export async function mac(secret, text) {
  const k = await crypto.subtle.importKey(
    "raw",
    bytes(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return hex(await crypto.subtle.sign("HMAC", k, bytes(text)));
}
const equal = async (a, b) => {
  const x = await digest(a),
    y = await digest(b);
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return d === 0;
};
class Failure extends Error {
  constructor(code, status = 400) {
    super(code);
    this.status = status;
  }
}
const fail = (c, s) => {
  throw new Failure(c, s);
};
const uuid = (s) =>
  typeof s === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(
    s,
  );
const fields = (obj, allowed) => {
  if (
    !obj ||
    typeof obj !== "object" ||
    Array.isArray(obj) ||
    Object.keys(obj).some((k) => !allowed.includes(k))
  )
    fail("INVALID_FIELDS");
};
export function text(s, max, nickname = false) {
  if (
    typeof s !== "string" ||
    !s.isWellFormed() ||
    !s.trim() ||
    [...s.trim()].length > max ||
    /[\u0000-\u0008\u000b-\u001f\u007f\u202a-\u202e\u2066-\u2069]/u.test(s)
  )
    fail("INVALID_TEXT");
  s = s.trim();
  if (nickname) {
    const n = s
      .normalize("NFKC")
      .replace(/[\s\p{P}\p{Cf}]/gu, "")
      .toLowerCase();
    if (/管理|公式|運営|admin|official|moderator|staff/.test(n))
      fail("RESERVED_NICKNAME");
  }
  return s;
}
const q = (db, sql, ...args) => db.prepare(sql).bind(...args);
const all = async (db, sql, ...args) =>
  (await q(db, sql, ...args).all()).results;
const first = (db, sql, ...args) => q(db, sql, ...args).first();
const PAGE = 20;
function number(v) {
  if (v === null || v === undefined) return 0;
  if (!/^(0|[1-9][0-9]{0,14})$/.test(String(v))) fail("INVALID_CURSOR");
  return Number(v);
}
async function json(request) {
  if (
    !/^application\/json(?:;|$)/i.test(
      request.headers.get("Content-Type") || "",
    )
  )
    fail("JSON_REQUIRED", 415);
  const reader = request.body?.getReader();
  if (!reader) fail("EMPTY_BODY");
  let size = 0,
    chunks = [];
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 8192) {
        await reader.cancel();
        fail("BODY_TOO_LARGE", 413);
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  try {
    const raw = new Uint8Array(size);
    let p = 0;
    for (const c of chunks) {
      raw.set(c, p);
      p += c.length;
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
  } catch {
    fail("INVALID_JSON");
  }
}
async function quota(db, key, limit, seconds, now) {
  const slot = Math.floor(now / (seconds * 1000)),
    k = key + ":" + slot;
  const r = await q(
    db,
    "INSERT INTO limits(key,count,expires) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1 WHERE count<?",
    k,
    (slot + 1) * seconds * 1000,
    limit,
  ).run();
  if (r.meta.changes !== 1) fail("RATE_LIMITED", 429);
}
async function limit(db, env, request, kind, now) {
  const ip = request.headers.get("CF-Connecting-IP");
  if (!ip) fail("CLIENT_UNAVAILABLE", 503);
  const actor = await mac(
    env.RATE_SECRET,
    Math.floor(now / 86400000) + ":" + ip,
  );
  await q(db, "DELETE FROM limits WHERE expires<?", now).run();
  await quota(db, "global", 4000, 86400, now);
  await quota(
    db,
    kind + ":" + actor,
    kind === "read" ? 60 : kind === "post" ? 3 : 5,
    60,
    now,
  );
  if (kind !== "read")
    await quota(
      db,
      kind + "-daily:" + actor,
      kind === "post" ? 20 : 10,
      86400,
      now,
    );
  return actor;
}
function ready(env, write = false) {
  if (
    !env.DB ||
    env.RELEASE_APPROVAL !== "approved" ||
    env.PUBLIC_READ_ENABLED !== "true" ||
    typeof env.RATE_SECRET !== "string" ||
    env.RATE_SECRET.length < 32
  )
    fail("COMMENTS_DISABLED", 503);
  if (
    write &&
    (env.PUBLIC_WRITE_ENABLED !== "true" ||
      typeof env.TURNSTILE_SECRET !== "string" ||
      env.TURNSTILE_SECRET.length < 20 ||
      /^[123]x0{5}/.test(env.TURNSTILE_SECRET) ||
      !env.TURNSTILE_HOSTNAME ||
      !env.MANIFEST_URL ||
      !env.REGISTRY_SHA256)
  )
    fail("POSTING_DISABLED", 503);
}
async function resolve(db, id) {
  if (!/^research-[0-9a-f]{16}$/.test(id)) fail("CASE_NOT_FOUND", 404);
  const row = await first(
    db,
    "SELECT c.* FROM cases c JOIN aliases a ON a.case_id=c.id WHERE a.alias=?",
    id,
  );
  if (!row) fail("CASE_NOT_FOUND", 404);
  return row;
}
async function verify(fetcher, env, token, now) {
  if (typeof token !== "string" || !token || token.length > 2048)
    fail("HUMAN_CHECK_REQUIRED");
  const response = await fetcher(
    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    {
      method: "POST",
      body: new URLSearchParams({
        secret: env.TURNSTILE_SECRET,
        response: token,
      }),
      signal: AbortSignal.timeout(5000),
    },
  );
  if (!response.ok) fail("HUMAN_CHECK_UNAVAILABLE", 503);
  const v = await response.json();
  const age = now - Date.parse(v.challenge_ts);
  if (
    v.success !== true ||
    v.hostname !== env.TURNSTILE_HOSTNAME ||
    v.action !== "research_comment" ||
    !Number.isFinite(age) ||
    age < -30000 ||
    age > 300000
  )
    fail("HUMAN_CHECK_FAILED");
}
async function active(fetcher, db, env, id) {
  const u = new URL(env.MANIFEST_URL);
  if (
    u.protocol !== "https:" ||
    u.username ||
    u.password ||
    u.hash ||
    u.hostname !== "charchan123.github.io" ||
    u.pathname !== "/hatena-photo-gallery/research-comment-cases.json"
  )
    fail("MANIFEST_CONFIGURATION", 503);
  const r = await fetcher(u.href, {
    signal: AbortSignal.timeout(3000),
    redirect: "error",
  });
  if (!r.ok) fail("CASE_REVIEW_REQUIRED", 503);
  const m = await r.json();
  const stored = await first(
    db,
    "SELECT value FROM metadata WHERE key='registry_sha256'",
  );
  if (
    m.version !== 1 ||
    m.registry_sha256 !== env.REGISTRY_SHA256 ||
    stored?.value !== m.registry_sha256 ||
    !Array.isArray(m.active_ids) ||
    !m.active_ids.includes(id)
  )
    fail("CASE_REVIEW_REQUIRED", 409);
}
function safeComment(c, admin = false) {
  return {
    id: c.id,
    case_id: c.case_id,
    parent_id: c.parent_id,
    nickname: c.nickname,
    body: c.body,
    created_at: c.created_at,
    state: c.state,
    official: c.role === "admin",
    seq: c.seq,
    ...(admin ? { reviewed: c.reviewed } : {}),
  };
}
async function page(db, caseId, cursor, admin = false, unread = false) {
  const rows = await all(
    db,
    `SELECT c.* FROM comments c WHERE c.case_id=? AND c.seq>? ${admin ? (unread ? "AND c.reviewed=0 AND c.role='visitor' AND c.state!='deleted'" : "") : "AND c.state!='hidden' AND (c.parent_id IS NULL OR EXISTS(SELECT 1 FROM comments p WHERE p.id=c.parent_id AND p.state!='hidden'))"} ORDER BY c.seq LIMIT ?`,
    caseId,
    cursor,
    PAGE + 1,
  );
  return {
    comments: rows.slice(0, PAGE).map((c) => safeComment(c, admin)),
    next_cursor: rows.length > PAGE ? rows[PAGE - 1].seq : null,
  };
}
async function receipt(db, body, kind, payload) {
  if (!uuid(body.request_id)) fail("INVALID_REQUEST_ID");
  const key = await digest(kind + ":" + body.request_id),
    hash = await digest(canonical(payload));
  const old = await first(db, "SELECT * FROM requests WHERE key=?", key);
  if (old && (old.kind !== kind || old.payload_hash !== hash))
    fail("IDEMPOTENCY_CONFLICT", 409);
  return { key, hash, old };
}
function remember(db, r, kind, id, now) {
  return q(
    db,
    "INSERT INTO requests(key,kind,payload_hash,resource_id,created_at) VALUES(?,?,?,?,?)",
    r.key,
    kind,
    r.hash,
    id,
    now,
  );
}
function audit(db, id, action, actor, now) {
  return q(
    db,
    "INSERT INTO audit(comment_id,action,actor,created_at) VALUES(?,?,?,?)",
    id,
    action,
    actor,
    now,
  );
}
async function publicRoute(req, env, url, fetcher, now) {
  const db = env.DB,
    parts = url.pathname.split("/").filter(Boolean),
    caseId = parts[2];
  if (parts[0] !== "v1" || parts[1] !== "cases" || !caseId)
    fail("NOT_FOUND", 404);
  const deleting = req.method === "POST" && parts[5] === "delete";
  if (!deleting) ready(env, req.method === "POST");
  else if (
    !env.DB ||
    typeof env.RATE_SECRET !== "string" ||
    env.RATE_SECRET.length < 32
  )
    fail("UNAVAILABLE", 503);
  const c = await resolve(db, caseId);
  if (req.method === "GET" && parts.length === 4 && parts[3] === "comments") {
    ready(env);
    await limit(db, env, req, "read", now);
    return page(db, c.id, number(url.searchParams.get("after")));
  }
  if (req.method !== "POST") fail("NOT_FOUND", 404);
  const body = await json(req);
  await limit(db, env, req, parts[5] === "reports" ? "report" : "post", now);
  if (parts.length === 4 && parts[3] === "comments") {
    fields(body, [
      "request_id",
      "nickname",
      "body",
      "delete_token",
      "turnstile_token",
    ]);
    const nickname = text(body.nickname, 30, true),
      message = text(body.body, 500);
    if (
      typeof body.delete_token !== "string" ||
      !/^[a-f0-9]{64}$/.test(body.delete_token)
    )
      fail("INVALID_DELETE_TOKEN");
    const r = await receipt(db, body, "post", {
      case_id: c.id,
      nickname,
      body: message,
      delete_token: body.delete_token,
    });
    if (r.old) {
      const old = await first(
        db,
        "SELECT * FROM comments WHERE id=?",
        r.old.resource_id,
      );
      return { comment: safeComment(old), duplicate: true };
    }
    await active(fetcher, db, env, c.id);
    await verify(fetcher, env, body.turnstile_token, now);
    const id = crypto.randomUUID(),
      hash = await digest(id + ":" + body.delete_token);
    try {
      await db.batch([
        q(
          db,
          "INSERT INTO comments(id,case_id,role,nickname,body,created_at,delete_hash) VALUES(?,?,'visitor',?,?,?,?)",
          id,
          c.id,
          nickname,
          message,
          now,
          hash,
        ),
        remember(db, r, "post", id, now),
      ]);
    } catch (e) {
      const old = await first(db, "SELECT * FROM requests WHERE key=?", r.key);
      if (old?.payload_hash === r.hash)
        return {
          comment: safeComment(
            await first(
              db,
              "SELECT * FROM comments WHERE id=?",
              old.resource_id,
            ),
          ),
          duplicate: true,
        };
      throw e;
    }
    return {
      comment: safeComment(
        await first(db, "SELECT * FROM comments WHERE id=?", id),
      ),
    };
  }
  if (parts.length === 6 && parts[3] === "comments" && uuid(parts[4])) {
    const id = parts[4],
      row = await first(
        db,
        "SELECT * FROM comments WHERE id=? AND case_id=?",
        id,
        c.id,
      );
    if (!row) fail("COMMENT_NOT_FOUND", 404);
    if (parts[5] === "delete") {
      fields(body, ["delete_token"]);
      if (
        row.role !== "visitor" ||
        typeof body.delete_token !== "string" ||
        !/^[a-f0-9]{64}$/.test(body.delete_token) ||
        !row.delete_hash ||
        !(await equal(
          await digest(id + ":" + body.delete_token),
          row.delete_hash,
        ))
      )
        fail("DELETE_NOT_AUTHORIZED", 403);
      const result = await db.batch([
        q(
          db,
          "UPDATE comments SET state='deleted',nickname=NULL,body=NULL,delete_hash=NULL WHERE id=? AND delete_hash=?",
          id,
          row.delete_hash,
        ),
        q(
          db,
          "INSERT INTO audit(comment_id,action,actor,created_at) SELECT ?,'author_delete','author',? WHERE changes()=1",
          id,
          now,
        ),
        q(
          db,
          "UPDATE reports SET reason=NULL,reporter_hash=id WHERE comment_id=?",
          id,
        ),
        q(db, "DELETE FROM requests WHERE resource_id=? AND kind!='post'", id),
      ]);
      if (result[0].meta.changes !== 1) fail("DELETE_NOT_AUTHORIZED", 403);
      return { deleted: true };
    }
    if (parts[5] === "reports") {
      fields(body, ["reason", "request_id", "turnstile_token"]);
      if (row.state !== "visible") fail("COMMENT_UNAVAILABLE", 409);
      const reason = text(body.reason, 200),
        actor = await mac(
          env.RATE_SECRET,
          "report:" +
            Math.floor(now / 86400000) +
            ":" +
            req.headers.get("CF-Connecting-IP"),
        );
      const r = await receipt(db, body, "report", {
        comment_id: id,
        reason,
        actor,
      });
      if (r.old) return { reported: true, duplicate: true };
      await verify(fetcher, env, body.turnstile_token, now);
      await db.batch([
        q(
          db,
          "INSERT OR IGNORE INTO reports(id,comment_id,reporter_hash,reason,created_at) VALUES(?,?,?,?,?)",
          crypto.randomUUID(),
          id,
          actor,
          reason,
          now,
        ),
        remember(db, r, "report", id, now),
      ]);
      return { reported: true };
    }
  }
  fail("NOT_FOUND", 404);
}
async function adminRoute(req, env, url, now) {
  const token = req.headers.get("Authorization") || "";
  if (
    req.headers.has("Origin") ||
    typeof env.ADMIN_TOKEN !== "string" ||
    env.ADMIN_TOKEN.length < 32 ||
    !(await equal(token, "Bearer " + env.ADMIN_TOKEN))
  )
    fail("ADMIN_UNAUTHORIZED", 401);
  if (!env.DB) fail("UNAVAILABLE", 503);
  const db = env.DB;
  await quota(db, "admin", 500, 86400, now);
  if (req.method === "GET" && url.pathname === "/admin/cases") {
    const search = (url.searchParams.get("q") || "").slice(0, 80);
    return {
      cases: await all(
        db,
        "SELECT c.*, (SELECT count(*) FROM comments x WHERE x.case_id=c.id) AS total,(SELECT count(*) FROM comments x WHERE x.case_id=c.id AND x.reviewed=0 AND x.role='visitor' AND x.state!='deleted') AS unread,(SELECT count(*) FROM reports r JOIN comments x ON r.comment_id=x.id WHERE x.case_id=c.id) AS reports FROM cases c WHERE instr(c.label,?)>0 ORDER BY unread DESC,c.id",
        search,
      ),
    };
  }
  if (req.method === "GET" && url.pathname === "/admin/comments") {
    const c = await resolve(db, url.searchParams.get("case_id") || "");
    return page(
      db,
      c.id,
      number(url.searchParams.get("after")),
      true,
      url.searchParams.get("unread") === "1",
    );
  }
  if (req.method === "GET" && url.pathname === "/admin/history") {
    const id = url.searchParams.get("comment_id") || "";
    if (!uuid(id)) fail("INVALID_ID");
    return {
      audit: await all(
        db,
        "SELECT seq,comment_id,action,actor,created_at FROM audit WHERE comment_id=? ORDER BY seq",
        id,
      ),
      reports: await all(
        db,
        "SELECT id,reason,created_at FROM reports WHERE comment_id=? ORDER BY created_at,id",
        id,
      ),
    };
  }
  if (req.method === "POST" && url.pathname === "/admin/action") {
    const b = await json(req);
    fields(b, ["request_id", "action", "comment_id", "body"]);
    if (
      !uuid(b.comment_id) ||
      !["reply", "hide", "restore", "review"].includes(b.action)
    )
      fail("INVALID_ACTION");
    const row = await first(
      db,
      "SELECT * FROM comments WHERE id=?",
      b.comment_id,
    );
    if (!row) fail("COMMENT_NOT_FOUND", 404);
    const message = b.action === "reply" ? text(b.body, 500) : null,
      r = await receipt(db, b, "admin", {
        action: b.action,
        comment_id: b.comment_id,
        body: message,
      });
    if (r.old) return { ok: true, duplicate: true };
    if (row.state === "deleted") fail("AUTHOR_DELETION_FINAL", 409);
    const id = b.action === "reply" ? crypto.randomUUID() : row.id,
      statements = [];
    if (b.action === "reply") {
      if (row.parent_id || row.state !== "visible")
        fail("REPLY_NOT_ALLOWED", 409);
      statements.push(
        q(
          db,
          "INSERT INTO comments(id,case_id,parent_id,role,nickname,body,created_at,reviewed) VALUES(?,?,?,'admin','管理人',?,?,1)",
          id,
          row.case_id,
          row.id,
          message,
          now,
        ),
      );
    } else if (b.action === "review")
      statements.push(q(db, "UPDATE comments SET reviewed=1 WHERE id=?", id));
    else
      statements.push(
        q(
          db,
          "UPDATE comments SET state=? WHERE id=?",
          b.action === "hide" ? "hidden" : "visible",
          id,
        ),
      );
    statements.push(
      audit(db, id, b.action, "admin", now),
      remember(db, r, "admin", id, now),
    );
    await db.batch(statements);
    return { ok: true };
  }
  if (req.method === "GET" && url.pathname === "/admin/backup") {
    // D1 batch gives one consistent read transaction. Never return a partial export.
    const result = await db.batch(
      TABLES.map((t) =>
        db.prepare(
          "SELECT * FROM " +
            t +
            " ORDER BY " +
            (t === "metadata"
              ? "key"
              : t === "aliases"
                ? "alias"
                : t === "requests"
                  ? "key"
                  : t === "comments" || t === "audit"
                    ? "seq"
                    : "id"),
        ),
      ),
    );
    const data = Object.fromEntries(
      TABLES.map((t, i) => [t, result[i].results]),
    );
    for (const report of data.reports) report.reporter_hash = report.id;
    const backup = { version: 1, created_at: now, data };
    const raw = canonical(backup);
    if (bytes(raw).length > 16 * 1024 * 1024)
      fail("BACKUP_TOO_LARGE_USE_D1_EXPORT", 413);
    return {
      ...backup,
      sha256: await digest(raw),
      signature: await mac(env.ADMIN_TOKEN, raw),
    };
  }
  fail("NOT_FOUND", 404);
}
export function createWorker({
  fetcher = globalThis.fetch,
  clock = () => Date.now(),
} = {}) {
  return {
    async fetch(request, env) {
      let origin = null,
        admin = false;
      try {
        const url = new URL(request.url);
        admin = url.pathname.startsWith("/admin/");
        const allow = (env.ALLOWED_ORIGINS || "")
          .split(",")
          .filter((s) => /^https:\/\/[^/]+$/.test(s));
        origin = request.headers.get("Origin");
        if (!admin && origin && !allow.includes(origin))
          fail("ORIGIN_FORBIDDEN", 403);
        if (!admin && request.method === "POST" && !origin)
          fail("ORIGIN_REQUIRED", 403);
        if (request.method === "OPTIONS") {
          if (admin || !origin || !allow.includes(origin))
            fail("ORIGIN_FORBIDDEN", 403);
          return new Response(null, {
            status: 204,
            headers: {
              "Access-Control-Allow-Origin": origin,
              "Access-Control-Allow-Methods": "GET, POST",
              "Access-Control-Allow-Headers": "Content-Type",
              "Access-Control-Max-Age": "600",
              Vary: "Origin",
            },
          });
        }
        const run = admin
          ? adminRoute(request, env, url, clock())
          : publicRoute(request, env, url, fetcher, clock());
        let timer;
        const result = await Promise.race([
          run,
          new Promise((_, reject) => {
            timer = setTimeout(
              () => reject(new Failure("TIMEOUT", 504)),
              12000,
            );
          }),
        ]).finally(() => clearTimeout(timer));
        return response(result, 200, admin ? null : origin);
      } catch (error) {
        return response(
          {
            error:
              error instanceof Failure ? error.message : "SERVICE_UNAVAILABLE",
          },
          error instanceof Failure ? error.status : 503,
          !admin &&
            origin &&
            (env.ALLOWED_ORIGINS || "").split(",").includes(origin)
            ? origin
            : null,
        );
      }
    },
    async scheduled(event, env) {
      if (env.DB)
        await env.DB.batch([
          q(env.DB, "DELETE FROM limits WHERE expires<?", Date.now()),
          q(
            env.DB,
            "UPDATE reports SET reporter_hash=id WHERE created_at<? AND length(reporter_hash)=64",
            Date.now() - 86400000,
          ),
        ]);
    },
  };
}
function response(body, status, origin) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    Vary: "Origin",
  };
  if (origin) headers["Access-Control-Allow-Origin"] = origin;
  return new Response(JSON.stringify(body), { status, headers });
}
export default createWorker();
