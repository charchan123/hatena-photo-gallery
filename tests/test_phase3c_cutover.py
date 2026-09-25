
import pytest

import main


def candidate(*, duplicate=False):
    legacy = [{"alt": "旧名？", "src": "same.jpg"}]
    hybrid = [{"alt": "旧名？", "src": "same.jpg"},
              {"alt": "新菌", "src": "new.jpg"}]
    if duplicate:
        legacy.append({"alt": "旧名？", "src": "same.jpg"})
        hybrid.insert(1, {"alt": "旧名？", "src": "same.jpg"})
    report = {
        "version": 2,
        "summary": {
            "legacy_image_count": len(legacy),
            "hybrid_image_count": len(hybrid),
            "confirmed_non_mushroom_removed_count": 0,
            "confirmed_new_mushroom_added_count": 1,
            "confirmed_mushroom_renamed_count": 0,
            "compatible_rename_count": 0,
        },
        "removed_non_mushroom": [],
        "added_occurrences": [{
            "src": "new.jpg", "subject_type": "mushroom",
            "gallery_name": "新菌", "subject_state_status": "accepted_subject",
            "decision": "confirmed_new_mushroom_added",
        }],
        "renamed_occurrences": [],
        "rename_conflicts": [{
            "src": "same.jpg", "legacy_alt": "旧名？",
            "proposed_hybrid_alt": "別名", "decision": "rename_conflict_manual_review",
        }],
    }
    return legacy, hybrid, report


def test_valid_candidate_and_duplicate_src_accounting_pass():
    legacy, hybrid, report = candidate(duplicate=True)
    result = main.validate_phase3c_hybrid_cutover(legacy, hybrid, report)
    assert result["valid"] is True
    assert all(result["checks"].values())


def _shadow(src, subject_type, *, name=None, status="accepted_subject"):
    return {
        "src": src,
        "subject_type": subject_type,
        "detected_label": name,
        "gallery_name": name if subject_type == "mushroom" else None,
        "subject_state_status": status,
        "article_path": "article.html",
    }


def test_audit_row_preserves_subject_type_without_coercion():
    for subject_type in ("mushroom", "non_mushroom", "review"):
        row = main._phase3c_shadow_audit_row(
            _shadow("image.jpg", subject_type, name="菌名"), {}
        )
        assert row["subject_type"] == subject_type


def test_real_builder_report_validates_new_mushroom_schema_contract():
    legacy = [{"alt": "既存菌", "src": "existing.jpg"}]
    shadows = [
        _shadow("existing.jpg", "mushroom", name="既存菌"),
        _shadow("new.jpg", "mushroom", name="新菌"),
    ]

    hybrid, report = main.build_phase3c_hybrid_preview(legacy, shadows)
    validation = main.validate_phase3c_hybrid_cutover(legacy, hybrid, report)

    assert validation["valid"] is True
    assert report["added_occurrences"][0]["subject_type"] == "mushroom"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda legacy, hybrid, report: report.update(version=1), "version"),
        (lambda legacy, hybrid, report: hybrid[0].update(alt=""), "invalid alt"),
        (lambda legacy, hybrid, report: hybrid[0].update(src=""), "invalid src"),
        (lambda legacy, hybrid, report: report["summary"].update(legacy_image_count=9), "legacy image count"),
        (lambda legacy, hybrid, report: report["summary"].update(hybrid_image_count=9), "hybrid image count"),
        (lambda legacy, hybrid, report: hybrid[0].update(src="wrong.jpg"), "src multiset"),
        (lambda legacy, hybrid, report: report["added_occurrences"][0].update(subject_type="review"), "not a mushroom"),
        (lambda legacy, hybrid, report: report["added_occurrences"][0].update(subject_state_status="reset_by_rejected_boundary"), "accepted subject"),
        (lambda legacy, hybrid, report: hybrid[0].update(alt="別名"), "legacy alt occurrence"),
    ],
)
def test_invalid_candidates_fail_closed(mutation, message):
    legacy, hybrid, report = candidate()
    mutation(legacy, hybrid, report)
    with pytest.raises(main.Phase3CCutoverValidationError, match=message):
        main.validate_phase3c_hybrid_cutover(legacy, hybrid, report)


def test_incompatible_renamed_occurrence_fails():
    legacy, hybrid, report = candidate()
    report["summary"].update(confirmed_mushroom_renamed_count=1,
                             compatible_rename_count=1)
    report["renamed_occurrences"] = [{
        "decision": "compatible_rename", "legacy_alt": "旧名",
        "detected_label": "別名",
    }]
    with pytest.raises(main.Phase3CCutoverValidationError, match="taxonomy-incompatible"):
        main.validate_phase3c_hybrid_cutover(legacy, hybrid, report)


def _stub_build(monkeypatch, legacy, hybrid, report, *, failure=None):
    seen = {"exif": [], "gallery": [], "status": [], "report": [], "preview": [],
            "portal": []}
    monkeypatch.setattr(main, "fetch_hatena_articles_api", lambda: ["article.html"])
    monkeypatch.setattr(main, "fetch_images", lambda files: legacy)
    monkeypatch.setattr(main, "load_subject_taxonomy", lambda: {"entries": []})
    monkeypatch.setattr(main, "extract_shadow_metadata", lambda *args, **kwargs: [])
    for name in ("report_category_inventory", "report_shadow_metadata",
                 "save_taxonomy_candidates", "save_shadow_metadata"):
        monkeypatch.setattr(main, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "build_phase3c_readiness", lambda *args: {})
    monkeypatch.setattr(main, "report_phase3c_readiness", lambda *args: None)
    monkeypatch.setattr(main, "save_phase3c_readiness", lambda *args: None)
    monkeypatch.setattr(main, "load_article_metadata", lambda: {})
    monkeypatch.setattr(main, "build_phase3c_hybrid_preview",
                        lambda *args: (_ for _ in ()).throw(RuntimeError("hybrid"))
                        if failure == "hybrid" else (hybrid, report))
    if failure == "validation":
        monkeypatch.setattr(main, "validate_phase3c_hybrid_cutover",
                            lambda *args: (_ for _ in ()).throw(RuntimeError("validation")))
    monkeypatch.setattr(main, "report_phase3c_hybrid_preview",
                        lambda value: seen["report"].append(value))
    monkeypatch.setattr(main, "save_phase3c_hybrid_preview",
                        lambda value: seen["preview"].append(value))
    monkeypatch.setattr(main, "build_residual_gap_audit", lambda *args: {})
    monkeypatch.setattr(main, "report_residual_gap_audit", lambda *args: None)
    monkeypatch.setattr(main, "save_residual_gap_audit", lambda *args: None)
    monkeypatch.setattr(main, "save_phase3c_production_status",
                        lambda status: seen["status"].append(status))
    monkeypatch.setattr(main, "load_exif_cache", lambda: {})
    monkeypatch.setattr(main, "build_exif_cache",
                        lambda entries, cache: seen["exif"].append(entries) or cache)
    monkeypatch.setattr(main, "save_exif_cache", lambda cache: None)
    monkeypatch.setattr(
        main, "export_portal_data",
        lambda **kwargs: seen["portal"].append(kwargs["production_entries"]),
    )
    monkeypatch.setattr(main, "generate_gallery",
                        lambda entries, cache: seen["gallery"].append(entries) or {})
    monkeypatch.setattr(main, "generate_index", lambda *args: None)
    monkeypatch.setattr(main, "generate_favorite_page", lambda *args: None)
    return seen


def test_active_cutover_preserves_candidate_identity_and_new_image(monkeypatch):
    legacy, hybrid, report = candidate()
    seen = _stub_build(monkeypatch, legacy, hybrid, report)
    main.build_gallery()
    assert seen["exif"][0] is hybrid
    assert seen["gallery"][0] is hybrid
    assert seen["portal"][0] is hybrid
    assert any(row["src"] == "new.jpg" for row in seen["gallery"][0])
    assert seen["gallery"][0][0]["alt"] == "旧名？"
    assert seen["status"][0]["production_mode"] == "phase3c_hybrid"


@pytest.mark.parametrize("failure", ["hybrid", "validation"])
def test_candidate_failure_uses_exact_legacy_object(monkeypatch, failure):
    legacy, hybrid, report = candidate()
    seen = _stub_build(monkeypatch, legacy, hybrid, report, failure=failure)
    main.build_gallery()
    assert seen["exif"][0] is legacy
    assert seen["gallery"][0] is legacy
    assert seen["status"][0]["production_mode"] == "legacy_fallback"
    if failure == "validation":
        assert seen["report"] == [report]
        assert seen["preview"] == [report]
    else:
        assert seen["report"] == []
        assert seen["preview"] == []


def test_shadow_failure_uses_exact_legacy_object(monkeypatch):
    legacy, hybrid, report = candidate()
    seen = _stub_build(monkeypatch, legacy, hybrid, report)
    monkeypatch.setattr(main, "extract_shadow_metadata",
                        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("shadow")))
    main.build_gallery()
    assert seen["exif"][0] is legacy
    assert seen["gallery"][0] is legacy


def test_taxonomy_failure_uses_exact_legacy_object(monkeypatch):
    legacy, hybrid, report = candidate()
    seen = _stub_build(monkeypatch, legacy, hybrid, report)
    monkeypatch.setattr(main, "load_subject_taxonomy",
                        lambda: (_ for _ in ()).throw(RuntimeError("taxonomy")))
    main.build_gallery()
    assert seen["exif"][0] is legacy
    assert seen["gallery"][0] is legacy
