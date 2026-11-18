/* Optional notification sender. All calls require explicit enablement. */
const ENDPOINT = "https://api.line.me/v2/bot/message/",
  MAX_AGE = 23 * 60 * 60 * 1000,
  LEASE = 60000;
const statement = (db, sql, ...args) => db.prepare(sql).bind(...args);
const rows = async (db, sql, ...args) => (await statement(db, sql, ...args).all()).results;
const run = (db, sql, ...args) => statement(db, sql, ...args).run();

function settings(env, now) {
  const start = Date.parse(env.LINE_START_AT || ""),
    cap = Number(env.LINE_MONTHLY_LIMIT);
  if (env.LINE_ENABLED !== "true" || env.RELEASE_APPROVAL !== "approved" ||
      env.PUBLIC_READ_ENABLED !== "true" || env.PUBLIC_WRITE_ENABLED !== "true" ||
      !env.DB || !env.LINE_CHANNEL_ACCESS_TOKEN || !/^U[0-9a-f]{32}$/.test(env.LINE_RECIPIENT_ID || "") ||
      !Number.isFinite(start) || start > now || !Number.isInteger(cap) || cap < 1 || cap > 200)
    return null;
  return { start, cap, to: env.LINE_RECIPIENT_ID };
}
async function recipientHash(value) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}
function monthAt(now) {
  return new Date(now + 9 * 60 * 60 * 1000).toISOString().slice(0, 7);
}
function message(row) {
  return JSON.stringify([{ type: "text", text:
    row.label + "に新しいコメント\n" + row.nickname + "\n" +
    [...row.body].slice(0, 120).join("") + (Array.from(row.body).length > 120 ? "…" : "") +
    "\nhttps://charchan123.github.io/hatena-photo-gallery/research.html#comments-" + row.case_id +
    "\n管理はPCのローカル管理室でケースID " + row.case_id + " を検索してください。"
  }]);
}
async function sendBatch(env, fetcher, now) {
  const config = settings(env, now);
  if (!config) return { status: "disabled", accepted: 0 };
  const db = env.DB,
    headers = { Authorization: "Bearer " + env.LINE_CHANNEL_ACCESS_TOKEN },
    request = (path, options = {}) => fetcher(ENDPOINT + path, {
      ...options, headers: { ...headers, ...options.headers },
      redirect: "error", signal: AbortSignal.timeout(8000),
    }),
    quotaResponse = await request("quota"),
    consumptionResponse = await request("quota/consumption");
  if (!quotaResponse.ok || !consumptionResponse.ok) return { status: "quota-unavailable", accepted: 0 };
  const quota = await quotaResponse.json(),
    usage = await consumptionResponse.json();
  if (quota.type !== "limited" || !Number.isInteger(quota.value) ||
      !Number.isInteger(usage.totalUsage) || usage.totalUsage < 0 ||
      usage.totalUsage >= Math.min(config.cap, quota.value))
    return { status: "quota-limited", accepted: 0 };
  const month = monthAt(now), recipient = await recipientHash(config.to);
  await run(db, "UPDATE line_outbox SET state='cancelled',payload=NULL WHERE state='pending' AND created_at<?", config.start);
  await run(db, `UPDATE line_outbox SET state='stopped',payload=NULL
    WHERE state='pending' AND first_attempt IS NOT NULL AND (first_attempt<? OR reserved_month!=? OR recipient_hash!=?)`,
    now - MAX_AGE, month, recipient);
  const pending = await rows(db, `SELECT o.*,c.case_id,c.nickname,c.body,k.label FROM line_outbox o
    JOIN comments c ON c.id=o.comment_id JOIN cases k ON k.id=c.case_id
    WHERE o.state='pending' AND o.due_at<=? AND o.lease_until<=? AND c.state='visible'
    AND EXISTS(SELECT 1 FROM requests r WHERE r.kind='post' AND r.resource_id=c.id)
    ORDER BY o.created_at,o.comment_id LIMIT 10`, now, now);
  let accepted = 0, remaining = Math.min(config.cap, quota.value) - usage.totalUsage;
  for (const row of pending) {
    if (remaining <= 0) break;
    const lease = crypto.randomUUID();
    const claim = await statement(db, `UPDATE line_outbox SET lease_token=?,lease_until=?
      WHERE comment_id=? AND state='pending' AND lease_until<=? AND due_at<=?
      RETURNING *`, lease, now + LEASE, row.comment_id, now, now).first();
    if (!claim) continue;
    if (claim.first_attempt === null) {
      await db.batch([
        statement(db, "INSERT INTO line_budget(month,reserved) VALUES(?,0) ON CONFLICT DO NOTHING", month),
        statement(db, `UPDATE line_outbox SET first_attempt=?,reserved_month=?,recipient_hash=?,payload=?
          WHERE comment_id=? AND lease_token=? AND state='pending' AND first_attempt IS NULL
          AND (SELECT reserved FROM line_budget WHERE month=?)<?`,
          now, month, recipient, message(row), row.comment_id, lease, month, config.cap),
        statement(db, `UPDATE line_budget SET reserved=reserved+1 WHERE month=? AND EXISTS
          (SELECT 1 FROM line_outbox WHERE comment_id=? AND lease_token=? AND first_attempt=?
           AND reserved_month=? AND state='pending')`, month, row.comment_id, lease, now, month),
      ]);
    }
    const owned = await statement(db, `SELECT o.* FROM line_outbox o JOIN comments c ON c.id=o.comment_id
      WHERE o.comment_id=? AND o.lease_token=? AND o.state='pending' AND c.state='visible'`,
      row.comment_id, lease).first();
    if (!owned?.payload) {
      await run(db, "UPDATE line_outbox SET lease_token=NULL,lease_until=0,due_at=? WHERE comment_id=? AND lease_token=?",
        now + 300000, row.comment_id, lease);
      continue;
    }
    let response;
    try {
      response = await request("push", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Line-Retry-Key": row.comment_id },
        body: JSON.stringify({ to: config.to, messages: JSON.parse(owned.payload) }),
      });
    } catch {}
    const status = response?.status || 0,
      duplicate = status === 409 && !!response.headers.get("x-line-accepted-request-id"),
      sent = status === 200 || duplicate,
      permanent = status >= 400 && status < 500 && status !== 429 && !duplicate,
      state = sent ? "sent" : permanent ? "stopped" : "pending";
    await response?.body?.cancel();
    await run(db, `UPDATE line_outbox SET state=?,last_status=?,attempts=attempts+1,
      payload=CASE WHEN ?='pending' THEN payload ELSE NULL END,due_at=?,lease_token=NULL,lease_until=0
      WHERE comment_id=? AND lease_token=? AND state='pending'`,
      state, status, state, now + Math.min(1800000, 60000 * 2 ** Math.min(owned.attempts, 5)),
      row.comment_id, lease);
    remaining--;
    if (sent) accepted++;
    if (status === 401 || status === 403 || status === 429) break;
  }
  return { status: "processed", accepted };
}
export async function notifyComments(env, { fetcher = globalThis.fetch, now = Date.now() } = {}) {
  try {
    return await sendBatch(env, fetcher, now);
  } catch {
    // The comment transaction is already committed. No data or credentials are logged.
    return { status: "unavailable", accepted: 0 };
  }
}
