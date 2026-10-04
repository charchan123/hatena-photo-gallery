"""Domain operations for the local administration console."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from best_shot_ui import validate_best_shot_config
from research_identifications import validate_registry
from update_notices import NOTICE_DAYS, timestamp, validate_notice_config

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class AdminError(ValueError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_notices(config, now=None):
    try:
        events = validate_notice_config(config)
    except (TypeError, ValueError) as error:
        raise AdminError(str(error)) from error
    current = (now or datetime.now(timezone.utc)).timestamp()
    for event in events:
        instant = timestamp(event["occurred_at"])
        if instant is None or instant > current + 1:
            raise AdminError("notice time must include a timezone and cannot be in the future")
    return events


def notice_window(event, now=None):
    current = (now or datetime.now(timezone.utc)).timestamp()
    start = timestamp(event["occurred_at"])
    end = start + NOTICE_DAYS[event["kind"]] * 86400
    return {"starts_at": start, "ends_at": end, "active": start <= current < end,
            "remaining_seconds": max(0, int(end - current))}


def master_name_index(master):
    return {str(row.get("canonical_name_ja") or "").strip(): row.get("mushroom_id")
            for row in master.get("entries", []) if row.get("canonical_name_ja")}


class ChangeSet:
    """An in-memory draft. Disk is touched only by the reviewed PR workflow."""
    def __init__(self, portal_data):
        self.portal = portal_data
        self.best_shots = read_json(DATA / "best-shots.json")
        self.notices = read_json(DATA / "update-notices.json")
        self.identifications = read_json(DATA / "research-identifications.json")
        self.master = read_json(DATA / "mushroom-master.json")

    def add_best_shot(self, entry, *, annual=False, add_notice=False, occurred_at=None):
        candidate = deepcopy(self.best_shots)
        candidate["entries"].append(entry)
        if annual:
            observation = next((o for o in self.portal.get("observations", [])
                                if o.get("observation_id") == entry.get("observation_id")), None)
            year = str((observation.get("capture") or {}).get("date", "")[:4]) if observation else ""
            candidate["annual_best"][year] = entry.get("selection_id")
        validate_best_shot_config(candidate, self.portal)
        self.best_shots = candidate
        if add_notice:
            self.add_notice("best-shots", "new", "ベストショットを追加", occurred_at)

    def update_best_shot(self, selection_id, changes):
        allowed = {"observation_id", "comment", "annual_comment", "location", "order"}
        candidate = deepcopy(self.best_shots)
        row = next((r for r in candidate["entries"] if r.get("selection_id") == selection_id), None)
        if row is None or set(changes) - allowed:
            raise AdminError("Best Shot or editable field is invalid")
        row.update(changes)
        validate_best_shot_config(candidate, self.portal)
        self.best_shots = candidate

    def delete_best_shot(self, selection_id):
        candidate = deepcopy(self.best_shots)
        candidate["entries"] = [r for r in candidate["entries"] if r.get("selection_id") != selection_id]
        candidate["annual_best"] = {y: sid for y, sid in candidate["annual_best"].items() if sid != selection_id}
        if len(candidate["entries"]) == len(self.best_shots["entries"]):
            raise AdminError("Best Shot does not exist")
        validate_best_shot_config(candidate, self.portal)
        self.best_shots = candidate

    def set_annual(self, year, selection_id=None):
        candidate = deepcopy(self.best_shots)
        if selection_id is None:
            candidate["annual_best"].pop(str(year), None)
        else:
            candidate["annual_best"][str(year)] = selection_id
        validate_best_shot_config(candidate, self.portal)
        self.best_shots = candidate

    def add_notice(self, section, kind, summary, occurred_at):
        occurred_at = occurred_at or datetime.now().astimezone().isoformat(timespec="seconds")
        candidate = deepcopy(self.notices)
        candidate["events"].append({"section": section, "kind": kind,
                                    "summary": summary, "occurred_at": occurred_at})
        validate_notices(candidate)
        self.notices = candidate

    def update_notice(self, index, values):
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise AdminError("notice index is invalid")
        candidate = deepcopy(self.notices)
        try:
            candidate["events"][index] = {key: values[key] for key in
                                           ("section", "kind", "summary", "occurred_at")}
        except (IndexError, KeyError, TypeError) as error:
            raise AdminError("notice does not exist or has missing fields") from error
        validate_notices(candidate)
        self.notices = candidate

    def delete_notice(self, index):
        candidate = deepcopy(self.notices)
        try:
            candidate["events"].pop(index)
        except (IndexError, TypeError) as error:
            raise AdminError("notice does not exist") from error
        self.notices = candidate

    def identify(self, case, name, note="", *, summary="1種の正体が判明", occurred_at=None):
        name = str(name).strip()
        if not name:
            raise AdminError("identified_name is required")
        identity = {key: case["article"].get(key) for key in ("article_id", "article_path", "url")
                    if case["article"].get(key)}
        record = {"identification_id": "ident-" + uuid.uuid4().hex[:16], "case_id": case["case_id"],
                  "article": identity, "original_gallery_name": case["gallery_name"],
                  "identified_name": name,
                  "identified_at": occurred_at or datetime.now().astimezone().isoformat(timespec="seconds"),
                  "mushroom_master_id": master_name_index(self.master).get(name),
                  "note": str(note).strip(), "status": "identified"}
        candidate = deepcopy(self.identifications)
        candidate["identifications"].append(record)
        validate_registry(candidate, self.portal, self.master)
        self.identifications = candidate
        self.add_notice("research", "identified", summary, record["identified_at"])
        return record

    def reopen(self, identification_id):
        candidate = deepcopy(self.identifications)
        row = next((r for r in candidate["identifications"] if r["identification_id"] == identification_id), None)
        if row is None:
            raise AdminError("identification does not exist")
        row["status"] = "reopened"
        validate_registry(candidate, self.portal, self.master)
        self.identifications = candidate

    def validate(self):
        return {"best_shots": len(validate_best_shot_config(self.best_shots, self.portal)),
                "notices": len(validate_notices(self.notices)),
                "identifications": len(validate_registry(self.identifications, self.portal, self.master))}

    def files(self):
        return {"data/best-shots.json": self.best_shots,
                "data/update-notices.json": self.notices,
                "data/research-identifications.json": self.identifications}

    def preview(self):
        original = {name: read_json(ROOT / name) for name in self.files()}
        return {name: {"before": original[name], "after": value,
                       "changed": original[name] != value} for name, value in self.files().items()}


def safe_branch_name(operation="changes"):
    kind = re.sub(r"[^a-z0-9-]", "-", operation.lower()).strip("-")[:24] or "changes"
    return f"admin/{kind}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
