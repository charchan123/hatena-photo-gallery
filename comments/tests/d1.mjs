import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
export class LocalD1 {
  constructor() {
    this.sql = new DatabaseSync(":memory:");
    this.sql.exec("PRAGMA foreign_keys=ON");
    for (const n of [
      "0001_comments.sql",
      "0002_guards.sql",
      "0003_reviewed_cases.sql",
    ])
      this.sql.exec(
        readFileSync(
          fileURLToPath(new URL("../migrations/" + n, import.meta.url)),
          "utf8",
        ),
      );
  }
  prepare(sql) {
    const db = this;
    return {
      args: [],
      bind(...args) {
        this.args = args;
        return this;
      },
      async first() {
        return db.sql.prepare(sql).get(...this.args) || null;
      },
      async all() {
        return { results: db.sql.prepare(sql).all(...this.args) };
      },
      async run() {
        const r = db.sql.prepare(sql).run(...this.args);
        return { meta: { changes: Number(r.changes) }, results: [] };
      },
      sql,
    };
  }
  async batch(statements) {
    this.sql.exec("BEGIN");
    try {
      const result = [];
      for (const s of statements) {
        const stmt = this.sql.prepare(s.sql);
        if (stmt.columns().length)
          result.push({ results: stmt.all(...s.args), meta: { changes: 0 } });
        else {
          const r = stmt.run(...s.args);
          result.push({ results: [], meta: { changes: Number(r.changes) } });
        }
      }
      this.sql.exec("COMMIT");
      return result;
    } catch (e) {
      this.sql.exec("ROLLBACK");
      throw e;
    }
  }
}
