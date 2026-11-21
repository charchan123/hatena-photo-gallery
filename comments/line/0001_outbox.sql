-- Optional extension. Apply only after approval to the confirmed comments DB.
CREATE TABLE line_outbox (
 comment_id TEXT PRIMARY KEY REFERENCES comments(id),
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','sent','cancelled','stopped')),
 created_at INTEGER NOT NULL, due_at INTEGER NOT NULL DEFAULT 0,
 first_attempt INTEGER, reserved_month TEXT, recipient_hash TEXT, payload TEXT,
 attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_until INTEGER NOT NULL DEFAULT 0,
 last_status INTEGER
);
CREATE INDEX line_outbox_due ON line_outbox(state,due_at,lease_until);
CREATE TABLE line_budget (month TEXT PRIMARY KEY, reserved INTEGER NOT NULL CHECK(reserved>=0));
CREATE TRIGGER line_enqueue AFTER INSERT ON comments
WHEN NEW.role='visitor' AND NEW.state='visible' BEGIN
 INSERT INTO line_outbox(comment_id,created_at) VALUES(NEW.id,NEW.created_at);
END;
CREATE TRIGGER line_cancel_deleted AFTER UPDATE OF state ON comments
WHEN NEW.state='deleted' BEGIN
 UPDATE line_outbox SET state='cancelled',payload=NULL,lease_token=NULL,lease_until=0
 WHERE comment_id=NEW.id AND state='pending';
END;
