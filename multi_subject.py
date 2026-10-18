"""Read-only, evidence-gated mixed-mushroom photograph links in generated HTML.

The source photo/observation is never replicated in any production snapshot.
"""
from collections import Counter, defaultdict
import re


def build_multi_subject_photo_overlays(shadow_metadata, taxonomy, production_entries, match_subject_taxonomy):
    if taxonomy is None or not shadow_metadata:
        return {}
    count = Counter(row.get("src") for row in shadow_metadata if row.get("src"))
    present = defaultdict(set)
    for item in production_entries:
        if isinstance(item, dict):
            present[item.get("src")].add(item.get("alt"))
    linked = defaultdict(list)
    for row in shadow_metadata:
        if row.get("subject_state_status") != "reset_by_rejected_boundary":
            continue
        if row.get("last_rejected_boundary_reason") != "multiple_subject_separator":
            continue
        if row.get("detected_label") is not None:
            continue
        src = row.get("src")
        if not isinstance(src, str) or not src or count[src] != 1:
            continue
        if not row.get("article_id") or not row.get("article_categories"):
            continue
        raw = row.get("last_rejected_boundary_text")
        if not isinstance(raw, str) or not re.fullmatch(r"[^&＆]+[&＆][^&＆]+", raw):
            continue
        labels = [part.strip() for part in re.split("[&＆]", raw)]
        if len(labels) != 2 or labels[0] == labels[1]:
            continue
        if any(not label or any(term in label for term in
               ("?", "？", "不明", "(仮称)", "（仮称）", "の仲間")) for label in labels):
            continue
        accepted = []
        for label in labels:
            match, match_type = match_subject_taxonomy(label, taxonomy)
            if not match or match_type not in ("canonical_exact", "alias_exact"):
                break
            if match.get("subject_type") != "mushroom":
                break
            if label not in row["article_categories"]:
                break
            accepted.append(match["canonical_name"])
        if len(accepted) != 2 or accepted[0] == accepted[1]:
            continue
        # Never cross-link a photo the current gallery attributes to a third species.
        if any(old_name not in accepted for old_name in present.get(src, set())):
            continue
        for name in accepted:
            if name not in present.get(src, set()) and src not in linked[name]:
                linked[name].append(src)
    return dict(linked)
