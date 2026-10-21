PRAGMA foreign_keys = ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE cases (id TEXT PRIMARY KEY, label TEXT NOT NULL, identity_hash TEXT NOT NULL UNIQUE);
CREATE TABLE aliases (alias TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id));
CREATE TABLE comments (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
 case_id TEXT NOT NULL REFERENCES cases(id), parent_id TEXT REFERENCES comments(id),
 role TEXT NOT NULL CHECK(role IN ('visitor','admin')),
 nickname TEXT CHECK(nickname IS NULL OR length(nickname)<=30), body TEXT CHECK(body IS NULL OR length(body)<=500), created_at INTEGER NOT NULL CHECK(typeof(created_at)='integer' AND created_at>=0),
 state TEXT NOT NULL DEFAULT 'visible' CHECK(state IN ('visible','hidden','deleted')),
 delete_hash TEXT, reviewed INTEGER NOT NULL DEFAULT 0 CHECK(reviewed IN (0,1)),
 CHECK((role='visitor' AND parent_id IS NULL) OR (role='admin' AND parent_id IS NOT NULL)),
 CHECK((state='deleted' AND nickname IS NULL AND body IS NULL AND delete_hash IS NULL) OR
       (state!='deleted' AND length(body)>0 AND length(nickname)>0)),
 CHECK((role='admin' AND delete_hash IS NULL) OR (role='visitor' AND (state='deleted' OR (delete_hash IS NOT NULL AND length(delete_hash)=64)))),
 CHECK(role!='admin' OR nickname='管理人')
);
CREATE INDEX comments_case_seq ON comments(case_id,seq);
CREATE INDEX comments_unreviewed ON comments(reviewed,seq);
CREATE TABLE requests (key TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('post','report','admin')), payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64), resource_id TEXT NOT NULL REFERENCES comments(id), created_at INTEGER NOT NULL);
CREATE TABLE reports (id TEXT PRIMARY KEY, comment_id TEXT NOT NULL REFERENCES comments(id), reporter_hash TEXT NOT NULL, reason TEXT CHECK(reason IS NULL OR length(reason)<=200), created_at INTEGER NOT NULL, UNIQUE(comment_id,reporter_hash));
CREATE INDEX reports_comment ON reports(comment_id,created_at);
CREATE TABLE audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, comment_id TEXT REFERENCES comments(id), action TEXT NOT NULL, actor TEXT NOT NULL CHECK(actor IN ('admin','author')), created_at INTEGER NOT NULL);
CREATE INDEX audit_comment ON audit(comment_id,seq);
CREATE TABLE limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
CREATE INDEX limits_expiry ON limits(expires);
