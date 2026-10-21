CREATE TRIGGER official_reply_guard BEFORE INSERT ON comments WHEN NEW.parent_id IS NOT NULL BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM comments p WHERE p.id=NEW.parent_id AND p.case_id=NEW.case_id AND p.parent_id IS NULL AND p.state='visible') THEN RAISE(ABORT,'reply parent unavailable') END;
END;
CREATE TRIGGER immutable_comment_identity BEFORE UPDATE OF id,case_id,parent_id,role,created_at ON comments BEGIN SELECT RAISE(ABORT,'immutable comment identity'); END;
CREATE TRIGGER no_deleted_restore BEFORE UPDATE ON comments WHEN OLD.state='deleted' AND NEW.state!='deleted' BEGIN SELECT RAISE(ABORT,'author deletion is final'); END;
CREATE TRIGGER immutable_case_anchor BEFORE UPDATE OF id,identity_hash ON cases BEGIN SELECT RAISE(ABORT,'permanent case identity'); END;
CREATE TRIGGER immutable_alias BEFORE UPDATE ON aliases BEGIN SELECT RAISE(ABORT,'alias reassignment forbidden'); END;
CREATE TRIGGER retain_alias BEFORE DELETE ON aliases BEGIN SELECT RAISE(ABORT,'alias history retained'); END;
