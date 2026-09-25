"""Pure, inference-free construction of the supplemental portal data export."""

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os


CLASSIFICATION_STATUSES = (
    "confirmed_named_mushroom",
    "confirmed_mushroom_identity_uncertain",
    "manual_review_name_conflict",
    "legacy_review",
    "legacy_undetected",
    "legacy_shadow_missing",
)


def _normal_path(value):
    return os.path.normpath(value) if isinstance(value, str) and value else value


def _match_shadows(production_entries, shadow_metadata):
    """Match ordered occurrences without collapsing duplicate source URLs."""
    by_src = defaultdict(list)
    for row in shadow_metadata:
        if isinstance(row, dict) and row.get("src"):
            by_src[row["src"]].append(row)
    consumed = set()
    matches = []
    for entry in production_entries:
        candidates = by_src.get(entry.get("src"), [])
        selected = None
        status = "shadow_missing"
        for position, row in enumerate(candidates):
            key = (entry.get("src"), position)
            if key in consumed or row.get("subject_type") == "non_mushroom":
                continue
            if entry.get("alt") == row.get("gallery_name"):
                selected, status = (position, row), "exact_gallery_name"
                break
            if entry.get("alt") == row.get("legacy_alt"):
                selected, status = (position, row), "exact_legacy_alt"
                break
        if selected is None:
            for position, row in enumerate(candidates):
                key = (entry.get("src"), position)
                if key not in consumed and row.get("subject_type") != "non_mushroom":
                    selected, status = (position, row), "src_only_fallback"
                    break
        if selected is None:
            matches.append((None, "shadow_missing"))
        else:
            position, row = selected
            consumed.add((entry.get("src"), position))
            matches.append((row, status))
    return matches


def _classification_status(gallery_name, shadow):
    if shadow is None:
        return "legacy_shadow_missing"
    if shadow.get("detected_label") is None:
        return "legacy_undetected"
    if shadow.get("subject_type") == "review":
        return "legacy_review"
    if shadow.get("subject_type") == "mushroom":
        if gallery_name == "不明":
            return "confirmed_mushroom_identity_uncertain"
        if shadow.get("gallery_name") and gallery_name == shadow.get("gallery_name"):
            return "confirmed_named_mushroom"
        return "manual_review_name_conflict"
    return "legacy_review"


def _capture(exif):
    exif = exif if isinstance(exif, dict) else {}
    normalized = None
    month = None
    raw_date = exif.get("date")
    if isinstance(raw_date, str):
        try:
            parsed = datetime.strptime(raw_date, "%Y/%m/%d")
            normalized, month = parsed.strftime("%Y-%m-%d"), parsed.month
        except ValueError:
            pass
    return {
        "date": normalized,
        "month": month,
        "date_source": "exif" if normalized else None,
        "camera": {key: exif.get(key, "") for key in
                   ("model", "lens", "iso", "f", "exposure", "focal")},
    }


def _article(shadow, article_metadata):
    if shadow is None or not shadow.get("article_path"):
        return None
    path = shadow["article_path"]
    metadata = article_metadata.get(_normal_path(path), {})
    return {
        "article_path": path,
        "article_id": metadata.get("article_id", shadow.get("article_id")),
        "title": metadata.get("title", shadow.get("article_title")),
        "url": metadata.get("url"),
        "published": metadata.get("published"),
        "updated": metadata.get("updated"),
        "categories": deepcopy(metadata.get(
            "categories", shadow.get("article_categories") or []
        )),
    }


def _knowledge_link(gallery_name, taxonomy_by_name, master_ids):
    taxonomy = taxonomy_by_name.get(gallery_name)
    if not taxonomy or taxonomy.get("subject_type") != "mushroom":
        return None, None
    mushroom_id = taxonomy.get("mushroom_master_id")
    if mushroom_id is None:
        return taxonomy, None
    if mushroom_id not in master_ids:
        raise ValueError(f"taxonomy references missing mushroom master: {mushroom_id}")
    return taxonomy, mushroom_id


def _validate(data, production_entries, master_ids):
    observations, subjects = data["observations"], data["subjects"]
    expected = Counter((row.get("src"), row.get("alt")) for row in production_entries)
    actual = Counter((row["src"], row["gallery_name"]) for row in observations)
    if len(observations) != len(production_entries) or expected != actual:
        raise ValueError("portal observations do not preserve production occurrences")
    if [row["production_index"] for row in observations] != list(range(len(observations))):
        raise ValueError("portal production indexes are not contiguous")
    ids = [row["observation_id"] for row in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("portal observation IDs are not unique")
    grouped = Counter(row["gallery_name"] for row in observations)
    if sum(row["photo_count"] for row in subjects) != len(observations):
        raise ValueError("portal subject total does not match observations")
    if any(grouped[row["gallery_name"]] != row["photo_count"] for row in subjects):
        raise ValueError("portal subject grouping is inconsistent")
    if any(row["mushroom_master_id"] not in master_ids
           for row in observations if row["mushroom_master_id"] is not None):
        raise ValueError("portal observation has an unknown mushroom master ID")


def build_portal_data(*, production_entries, shadow_metadata, article_metadata,
                      exif_cache, taxonomy, mushroom_master, sources,
                      production_mode, cutover_active):
    """Return schema v1 without mutating any caller-owned input."""
    shadows = shadow_metadata if isinstance(shadow_metadata, list) else []
    articles = {_normal_path(key): value for key, value in article_metadata.items()}
    taxonomy_entries = taxonomy.get("entries", [])
    master_entries = mushroom_master.get("entries", [])
    taxonomy_by_name = {row.get("canonical_name"): row for row in taxonomy_entries}
    master_ids = {row.get("mushroom_id") for row in master_entries}
    occurrences = Counter()
    observations = []
    for index, (entry, (shadow, match_status)) in enumerate(
            zip(production_entries, _match_shadows(production_entries, shadows))):
        gallery_name, src = entry.get("alt"), entry.get("src")
        article = _article(shadow, articles)
        article_path = article["article_path"] if article else ""
        occurrence_key = (src, article_path)
        ordinal = occurrences[occurrence_key]
        occurrences[occurrence_key] += 1
        digest = hashlib.sha256(
            f"{src}\0{article_path}\0{ordinal}".encode("utf-8")
        ).hexdigest()
        taxonomy_row, mushroom_id = _knowledge_link(
            gallery_name, taxonomy_by_name, master_ids
        )
        status = _classification_status(gallery_name, shadow)
        observations.append({
            "observation_id": f"obs-{digest}",
            "production_index": index,
            "gallery_name": gallery_name,
            "src": src,
            "shadow_match_status": match_status,
            "classification": {
                "status": status,
                "subject_type": shadow.get("subject_type") if shadow else None,
                "detected_label": shadow.get("detected_label") if shadow else None,
                "shadow_gallery_name": shadow.get("gallery_name") if shadow else None,
                "classification_reason": shadow.get("classification_reason") if shadow else None,
                "classification_confidence": shadow.get("classification_confidence") if shadow else None,
                "subject_state_status": shadow.get("subject_state_status") if shadow else None,
                "taxonomy_canonical_name": shadow.get("taxonomy_canonical_name") if shadow else None,
                "taxonomy_match_type": shadow.get("taxonomy_match_type") if shadow else None,
            },
            "capture": _capture(exif_cache.get(src)),
            "article": article,
            "mushroom_master_id": mushroom_id,
        })

    grouped = defaultdict(list)
    for observation in observations:
        grouped[observation["gallery_name"]].append(observation)
    subjects = []
    for gallery_name in sorted(grouped):
        rows = grouped[gallery_name]
        dates = [row["capture"]["date"] for row in rows if row["capture"]["date"]]
        months = Counter(row["capture"]["month"] for row in rows
                         if row["capture"]["month"] is not None)
        taxonomy_row, mushroom_id = _knowledge_link(
            gallery_name, taxonomy_by_name, master_ids
        )
        article_keys = {
            (row["article"].get("article_path"), row["article"].get("article_id"))
            for row in rows if row["article"] is not None
        }
        subjects.append({
            "gallery_name": gallery_name,
            "photo_count": len(rows),
            "cover_src": rows[0]["src"],
            "article_count": len(article_keys),
            "capture_date_count": len(dates),
            "capture_months": sorted(months),
            "capture_month_counts": {str(month): months[month] for month in sorted(months)},
            "first_capture_date": min(dates) if dates else None,
            "last_capture_date": max(dates) if dates else None,
            "classification_counts": dict(sorted(Counter(
                row["classification"]["status"] for row in rows
            ).items())),
            "taxonomy": ({
                "canonical_name": taxonomy_row.get("canonical_name"),
                "subject_type": taxonomy_row.get("subject_type"),
                "verification_status": taxonomy_row.get("verification_status"),
                "mushroom_master_id": taxonomy_row.get("mushroom_master_id"),
            } if taxonomy_row else None),
            "mushroom_master_id": mushroom_id,
            "knowledge_available": mushroom_id is not None,
        })

    status_counts = Counter(row["classification"]["status"] for row in observations)
    match_counts = Counter(row["shadow_match_status"] for row in observations)
    summary = {
        "production_image_count": len(production_entries),
        "observation_count": len(observations),
        "subject_count": len(subjects),
        "article_count": len({key for row in observations if row["article"] for key in [
            (row["article"].get("article_path"), row["article"].get("article_id"))]}),
        "shadow_matched_observation_count": len(observations) - match_counts["shadow_missing"],
        "shadow_src_only_fallback_count": match_counts["src_only_fallback"],
        "shadow_missing_observation_count": match_counts["shadow_missing"],
        "exif_dated_observation_count": sum(row["capture"]["date"] is not None for row in observations),
        "exif_undated_observation_count": sum(row["capture"]["date"] is None for row in observations),
        **{f"{name}_count": status_counts[name] for name in CLASSIFICATION_STATUSES},
        "master_linked_subject_count": sum(row["mushroom_master_id"] is not None for row in subjects),
        "master_unlinked_subject_count": sum(row["mushroom_master_id"] is None for row in subjects),
        "knowledge_record_count": len(master_entries),
        "source_count": len(sources.get("sources", [])),
    }
    data = {
        "version": 1,
        "production": {"mode": production_mode, "cutover_active": bool(cutover_active),
                       "image_count": len(production_entries)},
        "summary": summary,
        "subjects": subjects,
        "observations": observations,
        "reference_data": {
            "subject_taxonomy": deepcopy(taxonomy),
            "mushroom_master": deepcopy(mushroom_master),
            "sources": deepcopy(sources),
        },
    }
    _validate(data, production_entries, master_ids)
    return data


def save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def success_status(data):
    summary = data["summary"]
    return {
        "version": 1, "build_ok": True, "error": None,
        "production_mode": data["production"]["mode"],
        "production_image_count": data["production"]["image_count"],
        "portal_observation_count": summary["observation_count"],
        "portal_subject_count": summary["subject_count"],
        "shadow_missing_observation_count": summary["shadow_missing_observation_count"],
        "master_linked_subject_count": summary["master_linked_subject_count"],
    }


def failure_status(error, production_mode, production_image_count):
    return {"version": 1, "build_ok": False, "error": str(error),
            "production_mode": production_mode,
            "production_image_count": production_image_count}
