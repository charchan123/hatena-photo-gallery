"""Version-controlled, auditable identifications for research cases."""

from datetime import datetime
import json
from pathlib import Path

from research_ui import build_research_cases

SCHEMA_VERSION = 1
STATUSES = {"identified", "reopened"}
FIELDS = {"identification_id", "case_id", "article", "original_gallery_name",
          "identified_name", "identified_at", "mushroom_master_id", "note", "status"}


class ResearchIdentificationError(ValueError):
    pass


def load_registry(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ResearchIdentificationError(f"{field} must be a non-empty string")
    return value.strip()


def validate_registry(registry, portal_data, mushroom_master):
    """Validate references without changing either portal or knowledge data."""
    if not isinstance(registry, dict) or registry.get("version") != SCHEMA_VERSION:
        raise ResearchIdentificationError("registry version must be exactly 1")
    if not isinstance(registry.get("identifications"), list):
        raise ResearchIdentificationError("identifications must be a list")
    cases = {case["case_id"]: case for case in build_research_cases(portal_data)}
    masters = {row.get("mushroom_id"): row for row in mushroom_master.get("entries", [])}
    ids = set()
    active_cases = set()
    validated = []
    for index, row in enumerate(registry["identifications"]):
        if not isinstance(row, dict) or set(row) - FIELDS:
            raise ResearchIdentificationError(f"identifications[{index}] has invalid fields")
        identification_id = _text(row.get("identification_id"), "identification_id")
        case_id = _text(row.get("case_id"), "case_id")
        if identification_id in ids:
            raise ResearchIdentificationError(f"duplicate identification_id: {identification_id}")
        ids.add(identification_id)
        case = cases.get(case_id)
        if case is None:
            raise ResearchIdentificationError(f"research case does not exist: {case_id}")
        article = row.get("article")
        if not isinstance(article, dict) or not any(str(article.get(k) or "").strip()
                                                   for k in ("article_id", "article_path", "url")):
            raise ResearchIdentificationError("article requires a stable identity")
        expected = case["article"]
        if not any(article.get(k) and article.get(k) == expected.get(k)
                   for k in ("article_id", "article_path", "url")):
            raise ResearchIdentificationError("article identity does not match research case")
        if _text(row.get("original_gallery_name"), "original_gallery_name") != case["gallery_name"]:
            raise ResearchIdentificationError("original_gallery_name does not match research case")
        _text(row.get("identified_name"), "identified_name")
        raw_date = _text(row.get("identified_at"), "identified_at")
        try:
            parsed = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError as error:
            raise ResearchIdentificationError("identified_at is invalid") from error
        if parsed.tzinfo is None:
            raise ResearchIdentificationError("identified_at requires a timezone")
        if row.get("status") not in STATUSES:
            raise ResearchIdentificationError("status must be identified or reopened")
        master_id = row.get("mushroom_master_id")
        if master_id is not None and master_id not in masters:
            raise ResearchIdentificationError(f"mushroom_master_id does not exist: {master_id}")
        if row.get("note") is not None and not isinstance(row["note"], str):
            raise ResearchIdentificationError("note must be a string")
        if row["status"] == "identified":
            if case_id in active_cases:
                raise ResearchIdentificationError(f"duplicate active identification: {case_id}")
            active_cases.add(case_id)
        validated.append(dict(row))
    return validated


def split_research_cases(portal_data, registry, mushroom_master):
    rows = validate_registry(registry, portal_data, mushroom_master)
    cases = build_research_cases(portal_data)
    active = {row["case_id"]: row for row in rows if row["status"] == "identified"}
    return ([case for case in cases if case["case_id"] not in active],
            [{"case": case, "identification": active[case["case_id"]]}
             for case in cases if case["case_id"] in active])
