"""Independent fixtures for guarded sync. No live credentials or API access."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

import article_sync as sync


STAMP = "2026-10-11T00:00:00+00:00"


def photo(aid="article-A", src="https://images.example/A.jpg", oid="obs-published-A", name="シイタケ", state="confirmed_named_mushroom"):
    return {"observation_id": oid, "src": src, "gallery_name": name,
            "classification": {"status": state, "subject_state_status": "accepted_subject", "classification_confidence": "high"}, "article": {"article_id": aid, "article_path": "articles/article_1.html"},
            "capture": {"date": "2025-05-01"}}


def portal(*rows):
    return {"version": 1, "observations": list(rows or [photo()]),
            "summary": {"observation_count": len(rows or [photo()])}}


def entry(src="https://images.example/A.jpg", state="named_mushroom", updated="1", name="シイタケ"):
    return {"updated_hash": sync.digest(updated), "images": [
        {"url_hash": sync.digest(src), "ordinal": 0, "state": state, "reason": "taxonomy_mushroom", "label_hash": sync.digest(name), "name_hash": sync.digest(name)}]}


def prior(tmp_path, data=None, articles=None):
    root = tmp_path / "previous"
    root.mkdir(exist_ok=True)
    data = data or portal()
    sync.write_json(root / "portal-data.json", data)
    sync.write_json(root / "phase3c-production-status.json", {"cutover_active": True,
                    "validation": {"valid": True}, "production_image_count": len(data["observations"])})
    if articles:
        sync.write_json(root / "article-sync-snapshot.json", sync.seal_snapshot(articles, data, STAMP))
    return root


def test_prepend_and_reorder_preserve_all_ids_and_best_shot(tmp_path):
    old = portal(photo(), photo("article-B", "b", "obs-best-shot", name="ベニテングタケ"))
    new = deepcopy(old)
    new["observations"].reverse()
    for index, row in enumerate(new["observations"], 2):
        row["article"]["article_path"] = f"articles/article_{index}.html"
        row["observation_id"] = f"unstable-{index}"
    new["observations"].insert(0, photo("new-article", "new-photo", "unstable-first"))
    new["summary"]["observation_count"] = 3
    result = sync.reconcile_ids(new, old)
    assert [x["observation_id"] for x in result["observations"]][1:] == ["obs-best-shot", "obs-published-A"]
    assert result["observations"][0]["observation_id"].startswith("obs-")
    assert old["observations"][0]["observation_id"] == "obs-published-A"
    # Next daily run uses newly published IDs, so the registry remains compatible.
    assert sync.reconcile_ids(deepcopy(new), result) == result


def test_photo_insert_changes_ordinal_but_not_existing_identity():
    old = portal(photo(), photo(src="B", oid="obs-B"))
    new = portal(photo(src="NEW", oid="new"), photo(src="B", oid="shifted-B"), photo(oid="shifted-A"))
    result = sync.reconcile_ids(new, old)
    assert [x["observation_id"] for x in result["observations"]][1:] == ["obs-B", "obs-published-A"]


def test_same_url_in_different_articles_never_collapses():
    old = portal(photo(), photo("article-B", oid="obs-B"))
    new = portal(photo("article-B", oid="unstable-B"), photo(oid="unstable-A"))
    assert [x["observation_id"] for x in sync.reconcile_ids(new, old)["observations"]] == ["obs-B", "obs-published-A"]


def test_duplicate_same_url_preserved_only_with_matching_multiplicity():
    old = portal(photo(), photo(oid="obs-repeat"))
    assert [x["observation_id"] for x in sync.reconcile_ids(deepcopy(old), old)["observations"]] == ["obs-published-A", "obs-repeat"]
    new = portal(photo(), photo(oid="new"), photo(oid="new2"))
    with pytest.raises(sync.SyncError, match="DUPLICATE_OCCURRENCE_AMBIGUOUS"):
        sync.reconcile_ids(new, old)


@pytest.mark.parametrize("state", ["legacy_review", "legacy_undetected", "legacy_shadow_missing", "manual_review_name_conflict"])
def test_old_legacy_names_preserved_but_new_uncertain_name_blocks(state):
    old = portal(photo(state=state))
    assert sync.reconcile_ids(deepcopy(old), old) == old
    with pytest.raises(sync.SyncError, match="CLASSIFICATION_REQUIRES_REVIEW"):
        sync.reconcile_ids(portal(photo(state=state), photo(src="new", oid="new", state=state)), old)


@pytest.mark.parametrize("mutate,code", [
    (lambda x: x["observations"][0].update(src="replacement"), "REMOVED_OR_REPLACED"),
    (lambda x: x["observations"][0].update(gallery_name="別名"), "NAME_CHANGE"),
    (lambda x: x["observations"][0]["article"].update(article_id=None), "ID_COMPATIBILITY"),
])
def test_url_or_name_change_is_held_not_alias(mutate, code):
    old, new = portal(), portal()
    mutate(new)
    with pytest.raises(sync.SyncError, match=code):
        sync.reconcile_ids(new, old)


def test_photo_decrease_and_protected_photo_removal():
    old = portal(*[photo(src=str(i), oid=f"obs-{i}") for i in range(20)])
    with pytest.raises(sync.SyncError, match="ABNORMAL_PHOTO_DECREASE"):
        sync.reconcile_ids(portal(*old["observations"][:10]), old)
    with pytest.raises(sync.SyncError, match="REMOVED_OR_REPLACED"):
        sync.reconcile_ids(portal(*old["observations"][:-1]), old)


def test_idempotent_inventory_two_successful_runs_have_zero_diff():
    data = {sync.digest("A"): entry(), sync.digest("B"): entry("B")}
    report = sync.compare_inventory(data, deepcopy(data))
    assert report["comparison"] == "KNOWN"
    assert all(report[k] == 0 for k in ("new_articles", "deleted_articles", "new_images", "deleted_images", "updated_articles", "classification_changes", "url_changes"))


def test_change_types_are_distinguished_and_replacement_is_not_confirmed():
    old = {sync.digest("A"): entry(), sync.digest("B"): entry("B")}
    new = {sync.digest("A"): entry("replacement", updated="2"), sync.digest("C"): entry("C")}
    report = sync.compare_inventory(old, new)
    assert (report["new_articles"], report["deleted_articles"], report["updated_articles"]) == (1, 1, 1)
    assert (report["new_images"], report["deleted_images"]) == (2, 2)
    assert report["possible_url_changes"] == 1 and report["url_changes"] is None
    assert report["pending_changes"][0]["reason"] == "POSSIBLE_URL_REPLACEMENT"
    changed = {sync.digest("A"): entry(state="ambiguous")}
    assert sync.compare_inventory({sync.digest("A"): entry()}, changed)["classification_changes"] == 1


def test_first_comparison_is_unknown_not_all_new():
    report = sync.compare_inventory(None, {sync.digest("A"): entry()})
    assert report["comparison"] == "UNKNOWN"
    assert report["new_images"] is None and report["deleted_images"] is None


def test_bootstrap_requires_healthy_existing_publication(tmp_path):
    run = sync.SyncRun(prior(tmp_path), tmp_path / "report.json")
    assert run.previous_snapshot is None
    with pytest.raises(sync.SyncError, match="EMPTY_HARVEST"):
        run.capture([], {})


@pytest.mark.parametrize("damage", ["hash", "portal", "ordinal", "version", "empty"])
def test_corrupt_snapshot_never_trusted(damage):
    p = portal()
    snap = sync.seal_snapshot({sync.digest("A"): entry()}, p, STAMP)
    if damage == "hash":
        snap["sha256"] = "broken"
    elif damage == "portal":
        p["observations"][0]["src"] = "changed"
    else:
        if damage == "ordinal":
            snap["payload"]["articles"][sync.digest("A")]["images"][0]["ordinal"] = 3
        elif damage == "version":
            snap["payload"]["version"] = 99
        else:
            snap["payload"]["articles"] = {}
        snap["sha256"] = sync.payload_hash(snap["payload"])
    with pytest.raises(sync.SyncError):
        sync.validate_snapshot(snap, p)


def test_inventory_all_articles_and_images_no_source_text_leaked(tmp_path):
    f = tmp_path / "article_99.html"
    f.write_text('<p>private-looking content</p><img src="https://example/A?token=secret"><img src="https://example/A?token=secret">')
    rows = [{"article_path": str(f), "src": "https://example/A?token=secret", "subject_type": "review"}] * 2
    result = sync.inventory([str(f)], {str(f): {"article_id": "atom-A", "updated": "2026"}}, rows)
    images = result[sync.digest("atom-A")]["images"]
    assert [x["ordinal"] for x in images] == [0, 1]
    assert images[0]["state"] == "unclassified"
    assert "token" not in json.dumps(result) and "private-looking" not in json.dumps(result)


@pytest.mark.parametrize("error", [sync.SyncError("API_HTTP_ERROR"), sync.SyncError("API_XML_INVALID"),
                                   sync.SyncError("API_TRANSPORT_ERROR"), RuntimeError("TOP_SECRET"),
                                   sync.SyncError("PROTECTED_REFERENCE_ERROR")])
def test_failure_preserves_old_output_and_report_redacts_errors(tmp_path, monkeypatch, error, capsys):
    import main
    root = prior(tmp_path)
    output = tmp_path / "published-candidate"
    output.mkdir()
    (output / "index.html").write_bytes(b"previous good site")
    def fail(*, sync_run):
        sync.write_json(Path(main.OUTPUT_DIR) / "partial.json", {"partial": True})
        print("TOP_SECRET response or article body")
        raise error
    monkeypatch.setattr(main, "build_gallery", fail)
    report = tmp_path / "report.json"
    assert sync.run(root, output, report) == 1
    assert {p.name: p.read_bytes() for p in output.iterdir()} == {"index.html": b"previous good site"}
    assert "TOP_SECRET" not in report.read_text() + capsys.readouterr().out
    assert sync.read_json(report)["result"] == "BLOCKED"


@pytest.mark.parametrize("damage", ["missing", "broken_portal", "empty_portal", "duplicate_id", "bad_phase", "broken_snapshot"])
def test_baseline_failures_unknown_no_generation_no_publication(tmp_path, monkeypatch, damage):
    import main
    root = prior(tmp_path)
    if damage == "missing":
        (root / "portal-data.json").unlink()
    elif damage == "broken_portal":
        (root / "portal-data.json").write_text("{broken")
    elif damage == "empty_portal":
        sync.write_json(root / "portal-data.json", {"version": 1, "observations": []})
    elif damage == "duplicate_id":
        sync.write_json(root / "portal-data.json", portal(photo(), photo()))
    elif damage == "bad_phase":
        sync.write_json(root / "phase3c-production-status.json", {"cutover_active": False})
    else:
        sync.write_json(root / "article-sync-snapshot.json", {})
    monkeypatch.setattr(main, "build_gallery", lambda **kw: pytest.fail("must not generate"))
    report = tmp_path / "report.json"
    assert sync.run(root, tmp_path / "output", report) == 1
    status = sync.read_json(report)
    assert status["comparison"] == "UNKNOWN"
    assert not (tmp_path / "output").exists()


def test_reference_gate_uses_existing_best_shots_and_research_validators(tmp_path):
    p = portal()
    sync.write_json(tmp_path / "best-shots.json", {"version": 1, "entries": [
        {"selection_id": "best", "observation_id": "obs-published-A", "comment": "example", "order": 1}]})
    sync.write_json(tmp_path / "research-identifications.json", {"version": 1, "identifications": []})
    sync.write_json(tmp_path / "mushroom-master.json", {"version": 1, "entries": []})
    sync.validate_references(p, p, tmp_path)
    with pytest.raises(sync.SyncError, match="PROTECTED_REFERENCE"):
        sync.validate_references(portal(photo(oid="other")), p, tmp_path)
    replaced = portal(photo(src="replaced"))
    with pytest.raises(sync.SyncError, match="PROTECTED_REFERENCE"):
        sync.validate_references(replaced, p, tmp_path)


def test_workflow_schedule_old_triggers_and_gate_before_deploy():
    import yaml
    workflow = yaml.load(Path('.github/workflows/generate.yml').read_text(), Loader=yaml.BaseLoader)
    triggers = workflow["on"]
    assert triggers["schedule"] == [{"cron": "0 0 * * *"}]
    assert triggers["push"]["branches"] == ["main"] and "workflow_dispatch" in triggers
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    steps = workflow["jobs"]["build"]["steps"]
    build = next(i for i, x in enumerate(steps) if "python article_sync.py" in x.get("run", ""))
    deploy = next(i for i, x in enumerate(steps) if "github-pages-deploy-action" in x.get("uses", ""))
    assert build < deploy and "continue-on-error" not in steps[build] and "if" not in steps[deploy]
    assert not any("pull_request" in k for k in triggers)
    assert "--previous .sync-previous" in steps[build]["run"]


def atom_entry(aid="A", src="https://images.example/A.jpg", draft="no", updated="2026-10-11T00:00:00Z"):
    import html
    body = f'<p>シイタケ</p><p><img src="{src}" alt="シイタケ"></p>'
    return (f'<entry><id>{aid}</id><updated>{updated}</updated><title>Fixture article</title>'
            f'<published>2026-10-11T00:00:00Z</published><category term="キノコ探索日記"/>'
            f'<link rel="alternate" type="text/html" href="https://blog.example/entry/{aid}"/>'
            f'<content type="text/html">{html.escape(body)}</content>'
            f'<app:control><app:draft>{draft}</app:draft></app:control></entry>')


def feed(entries, next_url=None):
    import html
    link = f'<link rel="next" href="{html.escape(next_url, quote=True)}"/>' if next_url else ''
    return f'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:app="http://www.w3.org/2007/app">{entries}{link}</feed>'


def api_fixture(monkeypatch, tmp_path, responses):
    import main
    monkeypatch.setattr(main, "HATENA_USER", "fixture")
    monkeypatch.setattr(main, "HATENA_BLOG_ID", "fixture.example")
    monkeypatch.setattr(main, "HATENA_API_KEY", "SECRET")
    monkeypatch.setattr(main, "ATOM_ENDPOINT", "https://blog.hatena.ne.jp/fixture/fixture.example/atom/entry")
    monkeypatch.setattr(main, "ARTICLES_DIR", str(tmp_path / "articles"))
    monkeypatch.setattr(main, "ARTICLE_METADATA_FILE", str(tmp_path / "cache" / "metadata.json"))
    monkeypatch.setattr(main, "CACHE_DIR", str(tmp_path / "cache"))
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        response = responses[len(calls) - 1]
        if isinstance(response, Exception):
            raise response
        status, body = response if isinstance(response, tuple) else (200, response)
        return type("Response", (), {"status_code": status, "text": body})()
    monkeypatch.setattr(main.requests, "get", get)
    return main, calls


def test_complete_paginated_fetch_excludes_drafts_and_has_timeout(monkeypatch, tmp_path):
    endpoint = "https://blog.hatena.ne.jp/fixture/fixture.example/atom/entry"
    main, calls = api_fixture(monkeypatch, tmp_path, [
        feed(atom_entry() + atom_entry("DRAFT", draft="yes"), endpoint + "?page=2"), feed(atom_entry("B"))])
    audit = {}
    drafts = set()
    files = main.fetch_hatena_articles_api(strict=True, audit=audit, excluded_draft_hashes=drafts)
    metadata = main.load_article_metadata()
    assert len(files) == 2 and {x["article_id"] for x in metadata.values()} == {"A", "B"}
    assert len(calls) == 2 and all(x[1]["timeout"] == (10, 60) and x[1]["allow_redirects"] is False for x in calls)
    assert all("DRAFT" not in Path(x).read_text() for x in files)
    assert drafts == {sync.digest("DRAFT")}
    assert audit == {"pages_completed": 2, "entries_received": 3, "drafts_excluded": 1,
                     "published_articles": 2, "html_articles": 2, "pagination_complete": True,
                     "content_type_counts": {"text/html": 2}, "html_source_counts": {"content_html": 2},
                     "html_image_representation_difference_articles": 0}


@pytest.mark.parametrize("response,expected", [
    ((401, "SECRET response"), "API_HTTP_ERROR"),
    ("<broken", "API_XML_INVALID"),
    ("<error/>", "API_FEED_INVALID"),
    (feed(atom_entry() + atom_entry()), "ATOM_ID_MISSING_OR_DUPLICATE"),
    (feed(atom_entry(aid="")), "ATOM_ID_MISSING_OR_DUPLICATE"),
    (feed(atom_entry().replace('<app:control><app:draft>no</app:draft></app:control>', '')), "API_DRAFT_STATE_INVALID"),
    (feed(atom_entry(updated="")), "API_UPDATED_MISSING"),
    (feed(atom_entry().replace('text/html', 'text/plain')), "API_RENDERED_HTML_MISSING"),
    (feed(atom_entry().replace('<content type="text/html">', '<not-content>').replace('</content>', '</not-content>')), "API_CONTENT_MISSING"),
])
def test_strict_api_rejects_malformed_or_incomplete_feed(monkeypatch, tmp_path, response, expected):
    main, _ = api_fixture(monkeypatch, tmp_path, [response])
    with pytest.raises(sync.SyncError, match=expected):
        main.fetch_hatena_articles_api(strict=True)
    assert not Path(main.ARTICLE_METADATA_FILE).exists()


@pytest.mark.parametrize("next_url", ["https://evil.example/steal", "http://blog.hatena.ne.jp/fixture/fixture.example/atom/entry", "https://blog.hatena.ne.jp/other/atom/entry", "https://blog.hatena.ne.jp/fixture/fixture.example/atom/entry"])
def test_pagination_rejects_cycles_and_credential_forwarding(monkeypatch, tmp_path, next_url):
    main, calls = api_fixture(monkeypatch, tmp_path, [feed(atom_entry(), next_url)])
    with pytest.raises(sync.SyncError, match="API_PAGINATION_INVALID"):
        main.fetch_hatena_articles_api(strict=True)
    assert len(calls) == 1
    assert not Path(main.ARTICLE_METADATA_FILE).exists()


def test_page_two_timeout_does_not_mark_partial_fetch_complete(monkeypatch, tmp_path):
    import requests
    endpoint = "https://blog.hatena.ne.jp/fixture/fixture.example/atom/entry"
    main, _ = api_fixture(monkeypatch, tmp_path, [feed(atom_entry(), endpoint + "?page=2"), requests.Timeout("SECRET")])
    audit = {}
    with pytest.raises(sync.SyncError, match="API_TRANSPORT_ERROR"):
        main.fetch_hatena_articles_api(strict=True, audit=audit)
    assert not Path(main.ARTICLE_METADATA_FILE).exists()
    assert audit["pages_completed"] == 1 and audit["pagination_complete"] is False
    assert "SECRET" not in json.dumps(audit)


def test_snapshot_deletion_blocks_even_if_remaining_portal_is_unchanged(tmp_path):
    articles = {sync.digest("A"): entry(), sync.digest("deleted"): entry("B")}
    run = sync.SyncRun(prior(tmp_path, portal(photo(aid="A")), articles=articles), tmp_path / "report.json")
    f = tmp_path / "current.html"
    f.write_text('<img src="https://images.example/A.jpg">')
    run.capture([str(f)], {str(f): {"article_id": "A", "updated": "1"}})
    with pytest.raises(sync.SyncError, match="ABNORMAL_ARTICLE_DECREASE"):
        run.reconcile(portal(), [])
    assert run.status["deleted_articles"] == 1


def test_accepted_subject_guard_blocks_rejected_boundary_new_photos():
    new = photo(src="new", oid="new")
    new["classification"]["subject_state_status"] = "reset_by_rejected_boundary"
    with pytest.raises(sync.SyncError, match="CLASSIFICATION_REQUIRES_REVIEW"):
        sync.reconcile_ids(portal(photo(), new), portal())


def test_real_generator_guarded_bootstrap_then_second_sync_zero_diff(tmp_path, monkeypatch):
    """Real parsing/Phase 3C/portal/UI build. Only HTTP and EXIF are fixtures."""
    main, calls = api_fixture(monkeypatch, tmp_path, [feed(atom_entry()), feed(atom_entry()),
        feed(atom_entry("B", src="https://images.example/B.jpg") + atom_entry()),
        feed(atom_entry("B", src="https://images.example/B.jpg") + atom_entry()),
        feed(atom_entry("B", src="https://images.example/B.jpg") + atom_entry()),
        feed(atom_entry("B", src="https://images.example/B.jpg") + atom_entry(src="https://images.example/replacement.jpg"))])
    previous = prior(tmp_path, portal(photo(aid="A")))
    data = tmp_path / "data"
    sync.write_json(data / "best-shots.json", {"version": 1, "entries": [], "annual_best": {}})
    sync.write_json(data / "research-identifications.json", {"version": 1, "identifications": []})
    sync.write_json(data / "mushroom-master.json", main.load_mushroom_master())
    monkeypatch.setattr(main, "BEST_SHOTS_FILE", str(data / "best-shots.json"))
    monkeypatch.setattr(main, "CACHE_FILE", str(tmp_path / "cache" / "exif.json"))
    monkeypatch.setattr(main, "build_exif_cache", lambda entries, cache: {
        row["src"]: {"date": "2025/05/01"} for row in entries})
    original = sync.validate_references
    monkeypatch.setattr(sync, "validate_references", lambda portal, prev, directory: original(portal, prev, data))
    output, report = tmp_path / "output", tmp_path / "report.json"
    assert sync.run(previous, output, report) == 0, sync.read_json(report)
    first = sync.read_json(output / "article-sync-status.json")
    assert first["bootstrap"] is True and first["comparison"] == "UNKNOWN"
    assert first["new_images"] is None
    assert first["fetch_audit"]["pagination_complete"] is True
    assert first["published_article_count"] == first["detected_image_count"] == 1
    assert first["previous_photo_count"] == first["preserved_photo_ids"] == first["gallery_photo_count"] == 1
    assert first["best_shot_references_preserved"] == first["research_cases_preserved"] == 0
    assert first["generated_html_pages"] > 8
    assert sync.read_json(output / "portal-data.json")["observations"][0]["observation_id"] == "obs-published-A"
    assert (output / "シイタケ.html").exists()
    assert (output / "assets/poison-spores.js").exists()
    assert sync.run(output, tmp_path / "second-output", report) == 0, sync.read_json(report)
    second = sync.read_json(tmp_path / "second-output/article-sync-status.json")
    assert second["comparison"] == "KNOWN" and second["bootstrap"] is False
    assert second["new_articles"] == second["new_images"] == second["deleted_images"] == second["classification_changes"] == 0
    assert len(calls) == 2
    assert "pending_classification" not in second
    second_output = tmp_path / "second-output"
    third_output = tmp_path / "third-output"
    assert sync.run(second_output, third_output, report) == 1
    assert sync.read_json(report)['error_code'] == 'NEW_PHOTO_HUMAN_APPROVAL_REQUIRED'
    assert not third_output.exists()
    from admin.sync import SyncReview, live_capture
    # Fixture hosts replace only the local display allow-list, not any classifier
    # or generation/identity gate. Production allows the actual Hatena hosts only.
    monkeypatch.setattr('admin.sync.safe_url', lambda value, **k: value if isinstance(value,str) and value.startswith('https://') else None)
    publication = {name: sync.read_json(second_output / name) for name in (
        'portal-data.json','article-sync-snapshot.json','article-sync-status.json','phase3c-production-status.json')}
    publication['publication_sha'] = 'a' * 40
    review = SyncReview(tmp_path / 'local-review')
    review.install(publication, live_capture())
    candidate = next(r for r in review.rows if r['change_type'] == 'new_gallery_photo')
    assert candidate['adoptable'] is True
    review.decide({'candidate_id':candidate['candidate_id'], 'bundle_id':review.bundle_id,
                   'decision':'adopt', 'comment':'実写真を確認（fixture）'})
    approved = review.package()
    assert sync.run(second_output, third_output, report, review_manifest=approved) == 0, sync.read_json(report)
    third = sync.read_json(third_output / "article-sync-status.json")
    assert third["new_articles"] == third["new_images"] == 1
    old_photo = next(r for r in sync.read_json(third_output / "portal-data.json")["observations"] if r["article"]["article_id"] == "A")
    assert old_photo["observation_id"] == "obs-published-A"
    assert old_photo["article"]["article_path"].endswith("article_2.html")
    original_files = {p.relative_to(third_output): p.read_bytes() for p in third_output.rglob("*") if p.is_file()}
    assert sync.run(third_output, third_output, report) == 1
    rejected = sync.read_json(report)
    assert rejected["possible_url_changes"] == 1 and rejected["url_changes"] is None
    assert rejected["error_code"] == "DELETION_OR_URL_CHANGE_REQUIRES_REVIEW"
    assert {p.relative_to(third_output): p.read_bytes() for p in third_output.rglob("*") if p.is_file()} == original_files


def test_snapshot_requires_every_published_photo_in_atom_inventory():
    p = portal(photo(aid="A"))
    snapshot = sync.seal_snapshot({sync.digest("A"): entry()}, p, STAMP)
    assert sync.validate_snapshot(snapshot, p)["version"] == 1
    missing = sync.seal_snapshot({sync.digest("B"): entry()}, p, STAMP)
    with pytest.raises(sync.SyncError, match="SNAPSHOT_CORRUPT"):
        sync.validate_snapshot(missing, p)


def test_research_registration_survives_path_and_order_changes(tmp_path):
    from research_ui import build_research_cases
    old = portal(photo(name="不明", state="confirmed_mushroom_identity_uncertain"))
    case = build_research_cases(old)[0]
    registry = {"version": 1, "identifications": [{"identification_id": "identified-A", "case_id": case["case_id"],
        "article": {"article_id": "article-A"}, "original_gallery_name": "不明", "identified_name": "シイタケ",
        "identified_at": STAMP, "status": "identified", "mushroom_master_id": None}]}
    sync.write_json(tmp_path / "research-identifications.json", registry)
    sync.write_json(tmp_path / "mushroom-master.json", {"version": 1, "entries": []})
    sync.write_json(tmp_path / "best-shots.json", {"version": 1, "entries": []})
    current = deepcopy(old)
    current["observations"][0]["article"]["article_path"] = "articles/article_987.html"
    current["observations"][0]["observation_id"] = "unstable"
    resolved = sync.reconcile_ids(current, old)
    counts = sync.validate_references(resolved, old, tmp_path)
    assert counts == {"best_shot_references_preserved": 0, "research_cases_preserved": 1}
    assert build_research_cases(resolved)[0]["case_id"] == case["case_id"]
    assert sync.read_json(tmp_path / "research-identifications.json") == registry


def test_unregistered_research_case_cannot_silently_disappear(tmp_path):
    old = portal(photo(name="不明", state="confirmed_mushroom_identity_uncertain"))
    sync.write_json(tmp_path / "research-identifications.json", {"version": 1, "identifications": []})
    sync.write_json(tmp_path / "mushroom-master.json", {"version": 1, "entries": []})
    sync.write_json(tmp_path / "best-shots.json", {"version": 1, "entries": []})
    with pytest.raises(sync.SyncError, match="PROTECTED_REFERENCE_ERROR"):
        sync.validate_references(portal(), old, tmp_path)


def test_excluded_draft_photo_is_reported_but_gate_is_not_bypassed(tmp_path):
    old = portal(photo(aid="A"), photo(aid="now-draft", src="draft.jpg", oid="old-draft-photo"))
    run = sync.SyncRun(prior(tmp_path, old), tmp_path / "report.json")
    run.excluded_draft_hashes.add(sync.digest("now-draft"))
    f = tmp_path / "article.html"
    f.write_text('<img src="https://images.example/A.jpg">')
    run.capture([str(f)], {str(f): {"article_id": "A", "updated": "1"}})
    # Add enough unrelated valid photos to isolate the exact-ID disappearance gate.
    current = portal(photo(aid="A"), photo(aid="new", src="new", oid="new"))
    with pytest.raises(sync.SyncError, match="REMOVED_OR_REPLACED_PUBLISHED_PHOTO"):
        run.reconcile(current, [])
    assert run.status["missing_photos_in_excluded_drafts"] == 1
    assert run.status["missing_articles_in_excluded_drafts"] == 1
    assert run.status["missing_articles_from_api_harvest"] == 0


@pytest.mark.parametrize("generator", ["generate_season_page_if_fresh", "generate_records_page_if_fresh",
    "build_detail_views_if_fresh", "generate_feature_page_if_fresh", "generate_research_page_if_fresh",
    "generate_best_shot_pages_if_fresh"])
def test_failed_supplemental_generator_is_fail_closed(tmp_path, monkeypatch, generator):
    main, _ = api_fixture(monkeypatch, tmp_path, [feed(atom_entry())])
    root = prior(tmp_path, portal(photo(aid="A")))
    monkeypatch.setattr(main, "build_exif_cache", lambda entries, cache: {x["src"]: {"date": "2025/05/01"} for x in entries})
    monkeypatch.setattr(main, "CACHE_FILE", str(tmp_path / "cache" / "exif.json"))
    monkeypatch.setattr(main, generator, lambda *a, **kw: None)
    output = tmp_path / "output"
    output.mkdir()
    (output / "index.html").write_bytes(b"old-publication")
    report = tmp_path / "report.json"
    assert sync.run(root, output, report) == 1
    assert list(output.iterdir()) == [output / "index.html"]
    assert (output / "index.html").read_bytes() == b"old-publication"


def test_empty_live_feed_does_not_publish(tmp_path, monkeypatch):
    api_fixture(monkeypatch, tmp_path, [feed("")])
    root = prior(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "index.html").write_bytes(b"old-publication")
    report = tmp_path / "report.json"
    assert sync.run(root, output, report) == 1
    assert sync.read_json(report)["error_code"] == "EMPTY_HARVEST"
    assert (output / "index.html").read_bytes() == b"old-publication"


def test_explicit_html_keeps_original_names_even_when_formatted_names_differ(monkeypatch, tmp_path):
    import html
    response = atom_entry()
    rendered = '<p>別名</p><img src="https://images.example/A.jpg" alt="別名">'
    response = response.replace('</content>', '</content><h:formatted-content xmlns:h="http://www.hatena.ne.jp/info/xmlns#" type="text/html">'+html.escape(rendered)+'</h:formatted-content>')
    main, _ = api_fixture(monkeypatch, tmp_path, [feed(response)])
    audit = {}; paths = main.fetch_hatena_articles_api(strict=True, audit=audit)
    assert 'シイタケ' in Path(paths[0]).read_text() and '別名' not in Path(paths[0]).read_text()
    assert audit['html_source_counts'] == {'content_html': 1}


@pytest.mark.parametrize('kind', ['text/x-markdown', 'text/x-hatena-syntax'])
def test_non_html_requires_explicitly_typed_rendered_html(monkeypatch, tmp_path, kind):
    import html
    rendered = '<p>シイタケ</p><img src="https://images.example/A.jpg">'
    response = atom_entry().replace('type="text/html"', 'type="'+kind+'"')
    response = response.replace('</content>', '</content><h:formatted-content xmlns:h="http://www.hatena.ne.jp/info/xmlns#" type="text/html">'+html.escape(rendered)+'</h:formatted-content>')
    main, _ = api_fixture(monkeypatch, tmp_path, [feed(response)])
    assert Path(main.fetch_hatena_articles_api(strict=True)[0]).read_text() == rendered


def test_non_html_formatted_plain_text_is_not_guessed_into_html(monkeypatch, tmp_path):
    response = atom_entry().replace('type="text/html"','type="text/x-markdown"')
    response = response.replace('</content>','</content><h:formatted-content xmlns:h="http://www.hatena.ne.jp/info/xmlns#" type="text/plain">not rendered HTML</h:formatted-content>')
    main,_ = api_fixture(monkeypatch,tmp_path,[feed(response)])
    with pytest.raises(sync.SyncError,match='API_RENDERED_HTML_MISSING'):
        main.fetch_hatena_articles_api(strict=True)
