import json
from pathlib import Path

import pytest

import main


def write_master(tmp_path, entries, version=1):
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps({"version": version, "entries": entries}, ensure_ascii=False), encoding="utf-8")
    return path


def entry(name="キアシヤマドリタケ", kind="mushroom", aliases=None, **updates):
    value = {
        "canonical_name": name,
        "subject_type": kind,
        "aliases": [] if aliases is None else aliases,
        "verification_status": "project_seed",
        "sources": ["test"],
        "notes": "test",
    }
    value.update(updates)
    return value


def entry_without(field):
    value = entry()
    value.pop(field)
    return value


def test_repository_master_has_exactly_the_eight_approved_seeds():
    taxonomy = main.load_subject_taxonomy()
    actual = {(row["canonical_name"], row["subject_type"]) for row in taxonomy["entries"]}
    assert actual == {
        ("ヤマドリタケモドキ", "mushroom"), ("シイタケ", "mushroom"),
        ("ベニテングタケ", "mushroom"), ("ドクヤマドリ", "mushroom"),
        ("カエンタケ", "mushroom"), ("コブハクチョウ", "non_mushroom"),
        ("ヨシガモ", "non_mushroom"), ("ミツバアケビ", "non_mushroom"),
    }


@pytest.mark.parametrize("bad_entry", [
    entry(subject_type="plant"),
    entry(subject_type=[]), entry(subject_type={}), entry(subject_type=123),
    entry(canonical_name=[]), entry(aliases={}), entry(aliases=[123]),
    entry(sources={}), entry(verification_status=[]), entry(verification_status=None),
    entry(notes={}), entry(notes=None),
    entry_without("verification_status"), entry_without("notes"),
])
def test_malformed_entry_types_raise_subject_taxonomy_error(tmp_path, bad_entry):
    with pytest.raises(main.SubjectTaxonomyError):
        main.load_subject_taxonomy(write_master(tmp_path, [bad_entry]))


@pytest.mark.parametrize("entries", [
    [entry("シイタケ"), entry(" シイタケ ")],
    [entry("甲", aliases=["乙"]), entry("丙", aliases=["乙"])],
    [entry("甲", aliases=["乙"]), entry("乙")],
    [entry("甲", aliases=["乙"]), entry("乙", "non_mushroom")],
])
def test_taxonomy_key_collisions_are_rejected(tmp_path, entries):
    with pytest.raises(main.SubjectTaxonomyError, match="collision"):
        main.load_subject_taxonomy(write_master(tmp_path, entries))


def test_missing_malformed_and_invalid_roots_raise_domain_error(tmp_path):
    with pytest.raises(main.SubjectTaxonomyError):
        main.load_subject_taxonomy(tmp_path / "missing.json")
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(main.SubjectTaxonomyError):
        main.load_subject_taxonomy(malformed)
    for value in (
        [],
        {"entries": []},
        {"version": 1, "entries": {}},
        {"version": "1", "entries": []},
        {"version": True, "entries": []},
        {"version": 2, "entries": []},
    ):
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(main.SubjectTaxonomyError):
            main.load_subject_taxonomy(path)


def test_match_priority_and_conservative_normalization(tmp_path):
    taxonomy = main.load_subject_taxonomy(write_master(tmp_path, [
        entry("キアシヤマドリタケ", aliases=["Test mushroom"]),
    ]))
    assert main.match_subject_taxonomy("キアシヤマドリタケ", taxonomy)[1] == "canonical_exact"
    assert main.match_subject_taxonomy("Test mushroom", taxonomy)[1] == "alias_exact"
    matched, kind = main.match_subject_taxonomy("キアシヤマドリタケ(仮称)？", taxonomy)
    assert (matched["canonical_name"], kind) == ("キアシヤマドリタケ", "normalized")
    assert main.match_subject_taxonomy("キアシヤマドリタケの仲間", taxonomy) == (None, "none")


@pytest.mark.parametrize("label,kind,reason", [
    ("ヤマドリタケモドキ", "mushroom", "taxonomy_mushroom"),
    ("シイタケ", "mushroom", "taxonomy_mushroom"),
    ("ベニテングタケ", "mushroom", "taxonomy_mushroom"),
    ("ドクヤマドリ", "mushroom", "taxonomy_mushroom"),
    ("カエンタケ", "mushroom", "taxonomy_mushroom"),
    ("コブハクチョウ", "non_mushroom", "taxonomy_non_mushroom"),
    ("ヨシガモ", "non_mushroom", "taxonomy_non_mushroom"),
    ("ミツバアケビ", "non_mushroom", "taxonomy_non_mushroom"),
])
def test_repository_seed_classification(label, kind, reason):
    assert main.classify_subject_type(label, main.load_subject_taxonomy()) == (kind, reason, "high")


def test_unmatched_none_and_unavailable_classification():
    taxonomy = main.load_subject_taxonomy()
    assert main.classify_subject_type("未登録ラベル", taxonomy) == ("review", "taxonomy_unmatched", "low")
    assert main.classify_subject_type(None, taxonomy) == ("review", "no_detected_label", "low")
    assert main.classify_subject_type("シイタケ", None) == ("review", "taxonomy_unavailable", "low")


def shadow_record(tmp_path, label, categories=(), alt="legacy", taxonomy="load"):
    article = tmp_path / "article.html"
    article.write_text(f'<p>{label}</p><img src="x.jpg" alt="{alt}">', encoding="utf-8")
    return main.extract_shadow_metadata(
        [article], {str(article): {"categories": list(categories)}}, taxonomy=taxonomy
    )[0]


def test_category_and_legacy_alt_are_independent_of_taxonomy(tmp_path):
    taxonomy = main.load_subject_taxonomy()
    unmatched = shadow_record(tmp_path, "ムキタケ", ["キノコ探索日記", "ムキタケ"], taxonomy=taxonomy)
    assert (unmatched["subject_type"], unmatched["classification_confidence"]) == ("review", "low")
    assert unmatched["category_match_type"] == "exact"
    bird = shadow_record(tmp_path, "コブハクチョウ", ["コブハクチョウ"], alt="シイタケ", taxonomy=taxonomy)
    assert bird["subject_type"] == "non_mushroom"
    assert bird["category_match_type"] == "exact"


def test_gallery_name_is_classification_aware_and_preserves_label(tmp_path):
    taxonomy = main.load_subject_taxonomy()
    assert shadow_record(tmp_path, "シイタケ", taxonomy=taxonomy)["gallery_name"] == "シイタケ"
    uncertain = shadow_record(tmp_path, "シイタケ？", taxonomy=taxonomy)
    assert uncertain["gallery_name"] == "不明"
    assert uncertain["detected_label"] == "シイタケ？"
    assert shadow_record(tmp_path, "コブハクチョウ？", taxonomy=taxonomy)["gallery_name"] is None
    assert shadow_record(tmp_path, "ムキタケ？", taxonomy=taxonomy)["gallery_name"] is None


def test_category_audit_counters_use_evidence_not_classification_reason(tmp_path, capsys):
    taxonomy = main.load_subject_taxonomy()
    context = shadow_record(tmp_path, "ムキタケ", ["キノコ探索日記"], taxonomy=taxonomy)
    conflict = shadow_record(tmp_path, "シイタケ", ["キノコ探索日記", "野鳥"], taxonomy=taxonomy)
    explicit_conflict = shadow_record(tmp_path, "シイタケ", ["キノコ", "野鳥"], taxonomy=taxonomy)
    summary = main.summarize_shadow_metadata([context, conflict, explicit_conflict])
    assert summary["mushroom_context_only_review"] == 1
    assert summary["category_conflicts"] == 2
    assert main.has_category_conflict(conflict)
    main.report_shadow_metadata([conflict])
    assert "Phase 3B.2 suspicious-label audit" in capsys.readouterr().out


def test_unavailable_taxonomy_preserves_detection_and_low_review(tmp_path, capsys):
    row = shadow_record(tmp_path, "シイタケ", taxonomy=None)
    assert row["detected_label"] == "シイタケ"
    assert (row["subject_type"], row["classification_reason"], row["classification_confidence"]) == (
        "review", "taxonomy_unavailable", "low"
    )


def test_candidate_export_contains_distinct_unmatched_labels(tmp_path, monkeypatch):
    taxonomy = main.load_subject_taxonomy()
    row = shadow_record(tmp_path, "ムキタケ？", taxonomy=taxonomy)
    output = tmp_path / "cache" / "candidates.json"
    monkeypatch.setattr(main, "CACHE_DIR", str(output.parent))
    monkeypatch.setattr(main, "SUBJECT_TAXONOMY_CANDIDATES_FILE", str(output))
    main.save_taxonomy_candidates([row, row])
    candidate = json.loads(output.read_text(encoding="utf-8"))[0]
    assert candidate["image_count"] == 2
    assert candidate["current_taxonomy_match"] == "none"

@pytest.mark.parametrize("failure", ["missing file", "malformed JSON", "invalid schema"])
def test_build_taxonomy_failures_fall_back_and_preserve_production_identity(
    tmp_path, monkeypatch, capsys, failure
):
    article = tmp_path / "article.html"
    article.write_text('<p>シイタケ</p><img src="x.jpg" alt="legacy-name">', encoding="utf-8")
    entries = [{"alt": "legacy-name", "src": "x.jpg"}]
    generated = []
    captured = []
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: [str(article)])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries)
    monkeypatch.setattr(main, "load_subject_taxonomy", lambda: (_ for _ in ()).throw(main.SubjectTaxonomyError(failure)))
    monkeypatch.setattr(main, "report_category_inventory", lambda files: None)
    monkeypatch.setattr(main, "report_shadow_metadata", lambda metadata, **kwargs: captured.extend(metadata))
    monkeypatch.setattr(main, "save_taxonomy_candidates", lambda metadata: None)
    monkeypatch.setattr(main, "save_shadow_metadata", lambda metadata: None)
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: None)
    monkeypatch.setattr(main, "generate_gallery", lambda actual, cache: generated.append(actual) or {})
    monkeypatch.setattr(main, "generate_index", lambda grouped, cache: None)
    monkeypatch.setattr(main, "generate_favorite_page", lambda grouped: None)

    main.build_gallery()

    assert generated[0] is entries
    assert captured[0]["detected_label"] == "シイタケ"
    assert (captured[0]["subject_type"], captured[0]["classification_reason"]) == ("review", "taxonomy_unavailable")
    assert f"Phase 3B.2 taxonomy unavailable: {failure}" in capsys.readouterr().out


def test_audit_and_candidate_export_failures_do_not_block_legacy_generation(monkeypatch):
    entries = [{"alt": "legacy", "src": "x.jpg"}]
    generated = []
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: entries)
    monkeypatch.setattr(main, "extract_shadow_metadata", lambda files, **kwargs: [])
    monkeypatch.setattr(main, "report_category_inventory", lambda files: None)
    monkeypatch.setattr(main, "report_shadow_metadata", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit")))
    monkeypatch.setattr(main, "save_taxonomy_candidates", lambda data: (_ for _ in ()).throw(OSError("export")))
    monkeypatch.setattr(main, "save_shadow_metadata", lambda data: None)
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache", lambda actual, cache: cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: None)
    monkeypatch.setattr(main, "generate_gallery", lambda actual, cache: generated.append(actual) or {})
    monkeypatch.setattr(main, "generate_index", lambda grouped, cache: None)
    monkeypatch.setattr(main, "generate_favorite_page", lambda grouped: None)
    main.build_gallery()
    assert generated[0] is entries
