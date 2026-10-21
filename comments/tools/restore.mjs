// Offline-only restoration into a NEW local SQLite file. No Cloudflare API code.
import { DatabaseSync } from "node:sqlite";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname, join } from "node:path";
import { TABLES, canonical, digest, mac } from "../worker.mjs";
const home = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export async function verifyBackup(b, secret) {
  if (
    !secret ||
    secret.length < 32 ||
    !b ||
    Object.keys(b).sort().join(",") !==
      "created_at,data,sha256,signature,version" ||
    b.version !== 1 ||
    !Number.isSafeInteger(b.created_at) ||
    !b.data ||
    Object.keys(b.data).sort().join(",") !== [...TABLES].sort().join(",")
  )
    throw Error("BACKUP_SCHEMA");
  const raw = canonical({
    version: b.version,
    created_at: b.created_at,
    data: b.data,
  });
  if (
    b.sha256 !== (await digest(raw)) ||
    b.signature !== (await mac(secret, raw))
  )
    throw Error("BACKUP_SIGNATURE");
  for (const t of TABLES)
    if (!Array.isArray(b.data[t])) throw Error("BACKUP_ROWS");
  return b;
}
export async function restoreLocal(b, current, database, secret) {
  await verifyBackup(b, secret);
  await verifyBackup(current, secret);
  if (current.created_at < b.created_at)
    throw Error("CURRENT_DELETION_LEDGER_REQUIRED");
  for (const t of ["metadata", "cases", "aliases"])
    if (canonical(b.data[t]) !== canonical(current.data[t]))
      throw Error("CASE_BINDING_MISMATCH");
  const permanent = new Set(b.data.cases.map((c) => c.id));
  if (
    permanent.size !== b.data.cases.length ||
    new Set(b.data.aliases.map((a) => a.alias)).size !== b.data.aliases.length
  )
    throw Error("CASE_COLLISION");
  const data = structuredClone(b.data),
    deleted = new Set(
      current.data.comments
        .filter((c) => c.state === "deleted")
        .map((c) => c.id),
    );
  // Retain tombstones added after an older backup, and never resurrect an author deletion.
  for (const row of current.data.comments.filter((c) => c.state === "deleted"))
    if (!data.comments.some((c) => c.id === row.id)) data.comments.push(row);
  data.comments.sort((a, b) => a.seq - b.seq);
  const comments = new Map();
  for (const c of data.comments) {
    if (comments.has(c.id) || !permanent.has(c.case_id))
      throw Error("COMMENT_REFERENCE");
    if (deleted.has(c.id)) {
      c.state = "deleted";
      c.nickname = c.body = c.delete_hash = null;
    }
    comments.set(c.id, c);
  }
  for (const c of data.comments) {
    if (c.parent_id) {
      const p = comments.get(c.parent_id);
      if (!p || p.parent_id || p.case_id !== c.case_id || c.role !== "admin")
        throw Error("REPLY_REFERENCE");
    } else if (c.role !== "visitor") throw Error("ROLE_REFERENCE");
  }
  for (const r of data.reports) {
    if (!comments.has(r.comment_id)) throw Error("REPORT_REFERENCE");
    if (comments.get(r.comment_id).state === "deleted") {
      r.reason = null;
      r.reporter_hash = r.id;
    }
  }
  data.requests = data.requests.filter(
    (r) => !deleted.has(r.resource_id) || r.kind === "post",
  );
  // A post made AND deleted after the old backup also needs its receipt.
  // Otherwise retrying that old browser request could recreate its erased body.
  for (const r of current.data.requests.filter(
    (r) => deleted.has(r.resource_id) && r.kind === "post",
  )) {
    const old = data.requests.find((x) => x.key === r.key);
    if (old && canonical(old) !== canonical(r))
      throw Error("DELETION_RECEIPT_CONFLICT");
    if (!old) data.requests.push(r);
  }
  for (const r of data.requests)
    if (!comments.has(r.resource_id)) throw Error("REQUEST_REFERENCE");
  // Preserve minimal author-deletion audit records from the CURRENT signed ledger.
  for (const r of current.data.audit.filter(
    (r) => r.action === "author_delete",
  ))
    if (
      !data.audit.some(
        (a) => a.comment_id === r.comment_id && a.action === "author_delete",
      )
    ) {
      data.audit.push({
        ...r,
        seq: Math.max(0, ...data.audit.map((a) => a.seq)) + 1,
      });
    }
  if (existsSync(database)) throw Error("NEW_LOCAL_DATABASE_REQUIRED");
  const db = new DatabaseSync(database);
  try {
    db.exec(readFileSync(join(home, "migrations/0001_comments.sql"), "utf8"));
    db.exec("BEGIN");
    for (const table of TABLES) {
      for (const row of data[table]) {
        const columns = Object.keys(row);
        const known = new Set(
          db
            .prepare("PRAGMA table_info(" + table + ")")
            .all()
            .map((c) => c.name),
        );
        if (
          columns.some((k) => !known.has(k)) ||
          columns.some(
            (k) =>
              row[k] !== null &&
              typeof row[k] !== "string" &&
              !Number.isSafeInteger(row[k]),
          )
        )
          throw Error("ROW_FIELD_INVALID");
        const stmt = db.prepare(
          "INSERT INTO " +
            table +
            "(" +
            columns.join(",") +
            ") VALUES(" +
            columns.map(() => "?").join(",") +
            ")",
        );
        stmt.run(...columns.map((k) => row[k]));
      }
    }
    if (db.prepare("PRAGMA foreign_key_check").all().length)
      throw Error("FOREIGN_KEY_CHECK");
    db.exec(readFileSync(join(home, "migrations/0002_guards.sql"), "utf8"));
    db.exec("COMMIT");
    return { comments: data.comments.length, deleted_preserved: deleted.size };
  } catch (e) {
    try {
      db.exec("ROLLBACK");
    } catch {}
    throw e;
  } finally {
    db.close();
  }
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const [backup, ledger, database, approve] = process.argv.slice(2);
  if (approve !== "--approved-local-restore" || !backup || !ledger || !database)
    throw Error(
      "Use: node comments/tools/restore.mjs BACKUP CURRENT_SIGNED_BACKUP NEW_LOCAL.sqlite --approved-local-restore",
    );
  const result = await restoreLocal(
    JSON.parse(readFileSync(backup)),
    JSON.parse(readFileSync(ledger)),
    database,
    process.env.KINOKO_COMMENTS_ADMIN_TOKEN,
  );
  writeFileSync(
    database + ".verification.json",
    JSON.stringify(result, null, 2),
  );
  console.log("Verified local restoration only; no Cloudflare connection");
}
