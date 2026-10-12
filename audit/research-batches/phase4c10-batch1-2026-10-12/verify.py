"""Read-only audit of the pending research batch and immutable production."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from admin import knowledge
from feature_overlay import validate_feature_production_state
from mushroom_knowledge import load_sources

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def check(condition,label):
    if not condition:raise AssertionError(label)
    checks.append(label)

def audit():
    global checks
    checks=[]
    baseline=read(HERE/'baseline.json');base=baseline['base_main_sha']
    master=read(ROOT/'data/mushroom-master.json');sources=read(ROOT/'data/sources.json')
    facets=read(ROOT/'data/feature-facets.json')
    mm={r['mushroom_id']:r for r in master['entries']}
    state=validate_feature_production_state(root=ROOT)
    check(state['overlay_count']==0,'production_validator_and_empty_registry')
    for path,digest in baseline['protected_sha256'].items():
        check(sha((ROOT/path).read_bytes())==digest,'protected_bytes:'+path)
    tracked=subprocess.check_output(['git','ls-tree','-r','-z','--name-only',base],cwd=ROOT).decode().rstrip('\0').split('\0')
    for path in tracked:
        expected=subprocess.check_output(['git','show',base+':'+path],cwd=ROOT)
        check((ROOT/path).is_file() and (ROOT/path).read_bytes()==expected,'base_tracked_file_unchanged:'+path)
    research=read(HERE/'species-research.json')
    mids=[r['mushroom_id'] for r in research['records']]
    check(len(mids)==len(set(mids))==16 and set(mids)<=set(mm),'species_id_uniqueness_scope_16')
    excluded={r['mushroom_id'] for r in facets['coverage']['excluded_mushrooms']}
    check(excluded<=set(mids) and len(excluded)==12,'all_12_excluded_species_checked')
    triage=read(HERE/'partial-gap-triage.json')
    check(triage['screened_records']==139,'139_partial_records_gap_screened_without_full_research')
    check(sum(r['verification']['record_status']=='verified_core' for r in master['entries'])==2,'verified_core_2_preserved')
    new=read(HERE/'source-candidates.json')['sources']
    source_ids={r['source_id'] for r in sources['sources']}
    new_ids=[r['source_id'] for r in new];new_urls=[r['url'] for r in new]
    check(len(new_ids)==len(set(new_ids))==3 and not set(new_ids)&source_ids,'new_source_ids_unique_noncolliding')
    check(len(new_urls)==len(set(new_urls)) and not set(new_urls)&{r['url'] for r in sources['sources']},'new_source_urls_not_double_registered')
    combined={**{r['source_id']:r for r in sources['sources']},**{r['source_id']:r for r in new}}
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'sources.json'
        augmented={**sources,'sources':sources['sources']+new}
        path.write_text(json.dumps(augmented,ensure_ascii=False))
        load_sources(path)
    check(True,'all_3_source_candidates_existing_source_schema')
    snapshots=[json.loads(x) for x in (HERE/'research-source-snapshots.jsonl').read_text().splitlines()]
    snaps={s['source_id']:s for s in snapshots}
    check(len(snaps)==len(snapshots)==22,'research_snapshot_ids_unique_22')
    for snapshot in snapshots:
        sid=snapshot['source_id'];text=snapshot['full_extracted_text']
        check(set(snapshot)==knowledge.SNAPSHOT_KEYS,'snapshot_exact_schema:'+sid)
        check(sid in combined and snapshot['source_url']==combined[sid]['url'],'snapshot_source_url_join:'+sid)
        check(snapshot['text_snapshot_sha256']==snapshot['extracted_text_sha256']==sha(text.encode()),'snapshot_text_hash:'+sid)
        check((snapshot['unicode_codepoint_length'],snapshot['utf8_byte_length'],snapshot['lf_line_count'])==(len(text),len(text.encode()),1+text.count('\n')),'snapshot_lengths:'+sid)
    provenance=read(HERE/'retrieval-provenance.json')
    check({r['source_id'] for r in provenance}==set(snaps),'bounded_snapshot_provenance_complete')
    check(all(r['origin_http_body_obtained'] is False and 'NOT origin' in r['response_hash_semantics'] for r in provenance),'no_false_origin_http_hash_claim')
    proposals=read(HERE/'proposals.json')['proposals']
    check(len(proposals)==10 and len({p['proposal_id'] for p in proposals})==10,'10_unique_proposals')
    check(len({p['evidence']['evidence_id'] for p in proposals})==10,'10_unique_evidence_candidates')
    for p in proposals:
        check(p['mushroom_id'] in mm and p['human_decision']=='pending' and p['human_approval'] is None,'proposal_identity_pending:'+p['proposal_id'])
        current=mm[p['mushroom_id']]
        if p['target_field']=='head_reticulate':current=None
        else:
            for key in p['target_field'].split('.'):current=current[key]
        check(p['current_value']==current,'exact_old_value:'+p['proposal_id'])
        evidence=p['evidence'];snapshot=snaps[p['source_id']];text=snapshot['full_extracted_text']
        start,end=evidence['char_start'],evidence['char_end'];quote=evidence['quote']
        check(text[start:end]==quote and sha(quote.encode())==evidence['quote_sha256'],'evidence_offsets_quote_hash:'+p['proposal_id'])
        check(evidence['snapshot_identity']==snapshot['snapshot_identity'] and evidence['text_snapshot_sha256']==snapshot['text_snapshot_sha256'],'evidence_snapshot_join:'+p['proposal_id'])
        check(p['source_url']==combined[p['source_id']]['url'],'proposal_source_url_join:'+p['proposal_id'])
        check((evidence['snapshot_line_start'],evidence['snapshot_line_end'])==(1+text[:start].count('\n'),1+text[:start].count('\n')+quote.count('\n')),'evidence_line_ranges:'+p['proposal_id'])
    check(not any(p['target_field'].startswith(('food_safety','toxins','scientific_name')) for p in proposals),'no_food_safety_toxin_or_scientific_name_changes')
    check(len(read(HERE/'master-completion-proposals.json')['proposals'])==9,'9_master_proposals_separate_from_additive_intake')
    batch=HERE.name;intake=knowledge.load_batch(batch,inbox=HERE/'intake')
    validation=knowledge.validate_batch(batch,inbox=HERE/'intake')
    check(validation['status']=='PASS','unchanged_admin_knowledge_validator_PASS')
    existing_keys={(r['mushroom_id'],a['facet_id']) for r in facets['entries'] for a in r['assignments']}
    held=read(ROOT/'audit/phase4c9/v2/phase4c9-feature-evidence-ledger-approved-2026-10-03.json')['held_decisions']
    held_keys={(r['mushroom_id'],r['facet_id']) for r in held}
    added_keys=[(r['mushroom_id'],r['assignment']['facet_id']) for r in intake['delta']['assignment_additions']]
    check(len(added_keys)==len(set(added_keys))==1 and not set(added_keys)&(existing_keys|held_keys),'new_facet_no_duplicate_or_held_key')
    check(('tamagotakemodoki','ring') not in added_keys and len(held)==10,'IA029_ring_prohibition_and_10_holds_preserved')
    check(not intake['delta']['mushroom_additions'],'no_new_species_intake')
    with tempfile.TemporaryDirectory() as directory:
        preview=knowledge.preview_promotion(batch,inbox=HERE/'intake',state_root=Path(directory)/'state',origin_main_sha=base)
        check(preview['pending_count']==1 and preview['approved_count']==0 and preview['ready'] is False and preview['production_after'] is None,'no_human_approval_no_production_promotion')
        try:
            knowledge.materialize_promotion_package(batch,Path(directory)/'forbidden',inbox=HERE/'intake',state_root=Path(directory)/'state',base_sha=base)
        except knowledge.KnowledgeError:check(True,'unapproved_materialization_rejected')
        else:raise AssertionError('unapproved materialization unexpectedly accepted')
    return {'status':'PASS','check_count':len(checks),'checks':checks,'counts':{'species_researched':16,'partial_screened':139,'new_sources_research':3,'proposal_evidence':10,'research_snapshots':22,'facet_candidates':1,'master_completion_proposals':9,'intake_new_sources':1,'intake_snapshots':1,'human_approved':0},'intake_validation':validation,'promotion_preview':preview,'raw_http_validation':'NOT_PERFORMED; service response hash is not origin HTTP body hash','limitations':['Snapshot text is a bounded source passage extraction, not a complete HTML response.','Source body was read through web retrieval; direct HTTP download was blocked.','Validator PASS proves schema/hash/join consistency and does not certify biological conclusions.','Master replacement cannot enter the current additive-only contract.']}

if __name__=='__main__':
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
