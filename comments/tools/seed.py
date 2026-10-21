"""Offline only: materialize reviewed bindings as SQL, never connect to Cloudflare."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research_comments import validate_bindings, registry_digest, fingerprint
root=Path(__file__).resolve().parents[1]
registry=validate_bindings(json.loads((root/'cases.json').read_text(encoding='utf-8')))
def sql(s):return "'"+s.replace("'","''")+"'"
lines=['-- Reviewed initial 66-case registry. No existing case IDs are renumbered.',
       "INSERT INTO metadata(key,value) VALUES('installation_id',lower(hex(randomblob(16))));",
       "INSERT INTO metadata(key,value) VALUES('schema_version','1');",
       "INSERT INTO metadata(key,value) VALUES('registry_sha256',"+sql(registry_digest(registry))+");"]
for c in registry['cases']:
    lines.append('INSERT INTO cases(id,label,identity_hash) VALUES('+','.join(map(sql,[c['id'],c['label'],fingerprint(c['article_identity'],c['observation_ids'])]))+');')
    for a in c['render_ids']:lines.append('INSERT INTO aliases(alias,case_id) VALUES('+sql(a)+','+sql(c['id'])+');')
(root/'migrations/0003_reviewed_cases.sql').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
print(registry_digest(registry))
