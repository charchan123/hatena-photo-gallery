"""Fail-closed publication wrapper; no knowledge edits or remote writes.

Public inventory contains hashes/enums only. Exact URL identity is conservative:
article-local remove/add pairs are possible replacements, never automatic aliases.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import contextlib
import io
import sys

if __name__ == "__main__":
    sys.modules["article_sync"] = sys.modules[__name__]

from bs4 import BeautifulSoup

SAFE_NEW = {"confirmed_named_mushroom", "confirmed_mushroom_identity_uncertain"}
HASH = re.compile(r"^[0-9a-f]{64}$")
STATES = {"non_mushroom", "unidentified_mushroom", "named_mushroom", "conflict", "unclassified", "ambiguous"}
REVIEW_STATES = {"unidentified_mushroom", "conflict", "unclassified", "ambiguous"}
REASONS = {"no_detected_label", "taxonomy_unavailable", "taxonomy_unmatched", "taxonomy_mushroom",
           "taxonomy_non_mushroom", "taxonomy_review", "shadow_metadata_missing", "unspecified"}


class SyncError(ValueError):
    """Only allowlisted codes, not API responses or arbitrary exception strings."""


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def payload_hash(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SyncError("BASELINE_UNAVAILABLE_OR_CORRUPT") from None


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def observation_groups(portal):
    if not isinstance(portal, dict) or portal.get("version") != 1:
        raise SyncError("PORTAL_SCHEMA_INVALID")
    rows = portal.get("observations")
    if not isinstance(rows, list) or not rows:
        raise SyncError("PORTAL_EMPTY")
    groups, ids = defaultdict(list), set()
    for row in rows:
        if not isinstance(row, dict):
            raise SyncError("PORTAL_SCHEMA_INVALID")
        article = row.get("article") or {}
        aid, src, oid = article.get("article_id"), row.get("src"), row.get("observation_id")
        if not all(isinstance(x, str) and x for x in (aid, src, oid)) or oid in ids:
            raise SyncError("ID_COMPATIBILITY_ERROR")
        ids.add(oid)
        groups[(aid, src)].append(row)
    if portal.get("summary", {}).get("observation_count") != len(rows):
        raise SyncError("PORTAL_COUNT_INVALID")
    return groups


def reconcile_ids(current, previous):
    """Preserve every old ID by Atom id + exact URL, not article_N or DOM order.

    Duplicate occurrences require identical multiplicity and ordered name labels;
    changed multiplicity/labels cannot safely identify the previous occurrence.
    Missing old photos and existing name changes require human review.
    """
    old, new = observation_groups(previous), observation_groups(current)
    result = deepcopy(current)
    target = observation_groups(result)
    if len(current["observations"]) < len(previous["observations"]) * .9:
        raise SyncError("ABNORMAL_PHOTO_DECREASE")
    if old.keys() - new.keys():
        raise SyncError("REMOVED_OR_REPLACED_PUBLISHED_PHOTO")
    for key, rows in target.items():
        prior = old.get(key, [])
        if prior and len(prior) != len(rows):
            raise SyncError("DUPLICATE_OCCURRENCE_AMBIGUOUS")
        for ordinal, row in enumerate(rows):
            if prior:
                if row["gallery_name"] != prior[ordinal]["gallery_name"]:
                    raise SyncError("PUBLISHED_NAME_CHANGE_REQUIRES_REVIEW")
                row["observation_id"] = prior[ordinal]["observation_id"]
            else:
                classification = row.get("classification", {})
                if (classification.get("status") not in SAFE_NEW
                        or classification.get("subject_state_status") != "accepted_subject"
                        or classification.get("classification_confidence") != "high"):
                    raise SyncError("NEW_PHOTO_CLASSIFICATION_REQUIRES_REVIEW")
                row["observation_id"] = "obs-" + digest(
                    "hatena-photo-v2\0" + key[0] + "\0" + key[1] + "\0" + str(ordinal))
    observation_groups(result)
    return result


def inventory(article_files, metadata, shadows):
    """All published Atom articles and DOM image occurrences, not only mushrooms."""
    by_path = defaultdict(list)
    for row in shadows:
        by_path[os.path.normpath(row["article_path"])].append(row)
    articles = {}
    for path in article_files:
        meta = metadata.get(os.path.normpath(str(path)), {})
        aid = meta.get("article_id")
        if not isinstance(aid, str) or not aid:
            raise SyncError("ATOM_ID_MISSING")
        key = digest(aid)
        if key in articles:
            raise SyncError("ATOM_ID_DUPLICATE")
        candidates = defaultdict(list)
        for shadow in by_path[os.path.normpath(str(path))]:
            candidates[shadow["src"]].append(shadow)
        images = []
        occurrences = Counter()
        soup = BeautifulSoup(Path(path).read_text(encoding="utf-8"), "html.parser")
        for node in soup.find_all("img"):
            src = node.get("src")
            if not src:
                continue
            ordinal = occurrences[src]
            occurrences[src] += 1
            queue = candidates.get(src, [])
            shadow = queue[ordinal] if ordinal < len(queue) else {}
            subject = shadow.get("subject_type")
            if shadow.get("subject_state_status") == "reset_by_rejected_boundary":
                state = "conflict"
            elif subject == "non_mushroom":
                state = "non_mushroom"
            elif subject == "mushroom" and shadow.get("gallery_name") == "不明":
                state = "unidentified_mushroom"
            elif subject == "mushroom" and shadow.get("gallery_name"):
                state = "named_mushroom"
            elif shadow.get("detected_label") is None:
                state = "unclassified"
            else:
                state = "ambiguous"
            reason = shadow.get("classification_reason", "shadow_metadata_missing")
            images.append({"url_hash": digest(src), "ordinal": ordinal, "state": state,
                           "reason": reason if reason in REASONS else "unspecified",
                           "name_hash": digest(shadow.get("gallery_name") or ""),
                           "label_hash": digest(shadow.get("detected_label") or "")})
        articles[key] = {"updated_hash": digest(meta.get("updated") or ""), "images": images}
    if not articles or not any(row["images"] for row in articles.values()):
        raise SyncError("EMPTY_HARVEST")
    return articles


def seal_snapshot(articles, portal, timestamp, retirement=None):
    payload = {"version": 1, "last_success_at": timestamp, "articles": articles,
               "portal_sha256": payload_hash(portal)}
    if retirement is not None:
        payload["retirement"] = retirement
    return {"payload": payload, "sha256": payload_hash(payload)}


def validate_snapshot(snapshot, portal):
    try:
        payload = snapshot["payload"]
        assert snapshot["sha256"] == payload_hash(payload)
        assert type(payload["version"]) is int and payload["version"] == 1
        assert payload["portal_sha256"] == payload_hash(portal)
        assert datetime.fromisoformat(payload["last_success_at"]).tzinfo is not None
        articles = payload["articles"]
        if "retirement" in payload:
            from sync_retirement import validate_ledger
            validate_ledger(payload["retirement"], portal)
        assert isinstance(articles, dict) and articles
        for aid, row in articles.items():
            assert HASH.fullmatch(aid) and HASH.fullmatch(row["updated_hash"])
            assert isinstance(row["images"], list)
            counts = Counter()
            for image in row["images"]:
                url = image["url_hash"]
                assert HASH.fullmatch(url) and HASH.fullmatch(image["name_hash"])
                assert HASH.fullmatch(image["label_hash"]) and image["reason"] in REASONS
                assert image["ordinal"] == counts[url]
                assert image["state"] in STATES
                counts[url] += 1
        for (aid, src), rows in observation_groups(portal).items():
            images = articles[digest(aid)]["images"]
            assert sum(image["url_hash"] == digest(src) for image in images) >= len(rows)
        return payload
    except (AssertionError, KeyError, TypeError, ValueError):
        raise SyncError("SNAPSHOT_CORRUPT") from None


def compare_inventory(previous, current):
    if previous is None:
        return {"comparison": "UNKNOWN", "new_articles": None, "deleted_articles": None,
                "new_images": None, "deleted_images": None, "updated_articles": None,
                "classification_changes": None, "possible_url_changes": None, "url_changes": None}
    old_ids, new_ids = set(previous), set(current)
    new_images = deleted_images = changed = updated = replacements = 0
    pending = []
    for aid in sorted(old_ids | new_ids):
        before, after = previous.get(aid, {}), current.get(aid, {})
        old = {(x["url_hash"], x["ordinal"]): x for x in before.get("images", [])}
        new = {(x["url_hash"], x["ordinal"]): x for x in after.get("images", [])}
        added, removed = new.keys() - old.keys(), old.keys() - new.keys()
        new_images += len(added)
        deleted_images += len(removed)
        if aid in old_ids & new_ids:
            updated += before["updated_hash"] != after["updated_hash"]
            changed += sum(old[k] != new[k] for k in old.keys() & new.keys())
            if added and removed:
                replacements += min(len(added), len(removed))
                pending.append({"article_hash": aid, "reason": "POSSIBLE_URL_REPLACEMENT",
                                "removed": [list(k) for k in sorted(removed)],
                                "added": [list(k) for k in sorted(added)]})
    return {"comparison": "KNOWN", "new_articles": len(new_ids - old_ids),
            "deleted_articles": len(old_ids - new_ids), "new_images": new_images,
            "deleted_images": deleted_images, "updated_articles": updated,
            "classification_changes": changed, "url_changes": None if replacements else 0,
            "possible_url_changes": replacements, "pending_changes": pending,
            "deleted_article_hashes": sorted(old_ids - new_ids)}


def validate_references(portal, previous, data_directory):
    from best_shot_ui import validate_best_shot_config
    from research_identifications import validate_registry
    from research_ui import build_research_cases
    old = {row["observation_id"]: row for row in previous["observations"]}
    current = {row["observation_id"]: row for row in portal["observations"]}
    try:
        config = read_json(Path(data_directory) / "best-shots.json")
        validate_best_shot_config(config, portal)
        validate_registry(read_json(Path(data_directory) / "research-identifications.json"),
                          portal, read_json(Path(data_directory) / "mushroom-master.json"))
        for row in config["entries"]:
            oid = row["observation_id"]
            assert oid in old and oid in current
            assert (old[oid]["src"], old[oid]["article"]["article_id"]) == (
                current[oid]["src"], current[oid]["article"]["article_id"])
        old_cases = build_research_cases(previous)
        new_cases = {case["case_id"]: case for case in build_research_cases(portal)}
        for case in old_cases:
            assert case["case_id"] in new_cases
            assert {photo["observation_id"] for photo in case["photos"]} <= {
                photo["observation_id"] for photo in new_cases[case["case_id"]]["photos"]}
    except (ValueError, KeyError, AssertionError):
        raise SyncError("PROTECTED_REFERENCE_ERROR") from None
    return {"best_shot_references_preserved": len(config["entries"]),
            "research_cases_preserved": len(old_cases)}


class SyncRun:
    def __init__(self, previous_directory, report_path):
        self.previous_directory = Path(previous_directory)
        self.report_path = Path(report_path)
        self.status = {"version": 1, "result": "BLOCKED", **compare_inventory(None, {}),
                       "last_success_at": None, "classification_review_count": None,
                       "fetch_error": None, "id_compatibility_error": None}
        self.status["fetch_audit"] = {}
        self.excluded_draft_hashes = set()
        self.previous = read_json(self.previous_directory / "portal-data.json")
        observation_groups(self.previous)
        phase = read_json(self.previous_directory / "phase3c-production-status.json")
        if (phase.get("cutover_active") is not True or phase.get("validation", {}).get("valid") is not True
                or phase.get("production_image_count") != len(self.previous["observations"])):
            raise SyncError("PREVIOUS_PUBLICATION_NOT_HEALTHY")
        snapshot = self.previous_directory / "article-sync-snapshot.json"
        self.previous_snapshot = validate_snapshot(read_json(snapshot), self.previous) if snapshot.exists() else None
        if self.previous_snapshot:
            self.status["last_success_at"] = self.previous_snapshot["last_success_at"]
        from sync_retirement import Retirement
        self.retirement = Retirement(self.previous, self.previous_snapshot, self.previous_directory)
        self.effective_previous = self.previous
        self.article_files = None

    def capture(self, article_files, metadata):
        if not article_files:
            raise SyncError("EMPTY_HARVEST")
        self.article_files, self.metadata = article_files, metadata

    def reconcile(self, portal, shadows):
        if self.article_files is None:
            raise SyncError("HARVEST_NOT_COMPLETED")
        self.articles = inventory(self.article_files, self.metadata, shadows)
        self.status["published_article_count"] = len(self.articles)
        self.status["detected_image_count"] = sum(len(row["images"]) for row in self.articles.values())
        old_groups, new_groups = observation_groups(self.previous), observation_groups(portal)
        self.status.update(previous_photo_count=len(self.previous["observations"]),
                           candidate_gallery_photo_count=len(portal["observations"]),
                           missing_published_photo_keys=len(old_groups.keys() - new_groups.keys()),
                           missing_published_article_ids=len({aid for aid, _ in old_groups} - {aid for aid, _ in new_groups}))
        missing_keys = old_groups.keys() - new_groups.keys()
        missing_draft_keys = {key for key in missing_keys if digest(key[0]) in self.excluded_draft_hashes}
        self.status["missing_photos_in_excluded_drafts"] = sum(len(old_groups[key]) for key in missing_draft_keys)
        self.status["missing_articles_in_excluded_drafts"] = len({aid for aid, _ in missing_draft_keys})
        self.status["missing_articles_from_api_harvest"] = len({digest(aid) for aid, _ in missing_keys}
            - set(self.articles) - self.excluded_draft_hashes)
        before = self.previous_snapshot["articles"] if self.previous_snapshot else None
        differences = compare_inventory(before, self.articles)
        self.status.update({k: v for k, v in differences.items()
                            if k not in {"pending_changes", "deleted_article_hashes"}})
        self.status["deleted_article_hashes"] = differences.get("deleted_article_hashes", [])
        self.status["pending_changes"] = differences.get("pending_changes", [])
        pending_images = [{"article_hash": aid, "url_hash": image["url_hash"],
                           "ordinal": image["ordinal"], "state": image["state"], "reason": image["reason"]}
                          for aid, article in self.articles.items() for image in article["images"]
                          if image["state"] in REVIEW_STATES]
        # Production conflicts can retain a legacy label even when the DOM
        # detector supplies a named mushroom. Keep that independent review signal.
        pending_keys = {(x["article_hash"], x["url_hash"], x["ordinal"]) for x in pending_images}
        for (aid, src), rows in observation_groups(portal).items():
            for ordinal, row in enumerate(rows):
                key = (digest(aid), digest(src), ordinal)
                state = row.get("classification", {}).get("status")
                if state not in SAFE_NEW and key not in pending_keys:
                    pending_images.append({"article_hash": key[0], "url_hash": key[1],
                                           "ordinal": ordinal, "reason": state})
                    pending_keys.add(key)
        self.status["classification_review_count"] = len(pending_images)
        self.status["classification_state_counts"] = dict(Counter(
            image["state"] for article in self.articles.values() for image in article["images"]))
        self.status["pending_classification"] = pending_images
        if before:
            if len(self.articles) < len(before) * .9:
                raise SyncError("ABNORMAL_ARTICLE_DECREASE")
            if differences["deleted_articles"] or differences["deleted_images"]:
                raise SyncError("DELETION_OR_URL_CHANGE_REQUIRES_REVIEW")
        self.effective_previous = self.retirement.prepare(portal, self.articles, self.excluded_draft_hashes,
            Path(__file__).parent / "data")
        result = reconcile_ids(portal, self.effective_previous)
        self.status["retirement"] = self.retirement.status()
        return result

    def finalize(self, output, flags, data_directory):
        output = Path(output)
        portal = read_json(output / "portal-data.json")
        phase = read_json(output / "phase3c-production-status.json")
        status = read_json(output / "portal-data-status.json")
        if (phase.get("cutover_active") is not True or phase.get("validation", {}).get("valid") is not True
                or status.get("build_ok") is not True or not all(flags)
                or phase.get("production_image_count") != len(portal["observations"])):
            raise SyncError("OUTPUT_INTEGRITY_ERROR")
        self.status.update(validate_references(portal, self.previous, data_directory))
        old = {row["observation_id"]: row for row in self.effective_previous["observations"]}
        current = {row["observation_id"]: row for row in portal["observations"]}
        preserved = sum(oid in current and (row["src"], row["article"]["article_id"]) == (
            current[oid]["src"], current[oid]["article"]["article_id"]) for oid, row in old.items())
        if preserved != len(old):
            raise SyncError("ID_COMPATIBILITY_ERROR")
        self.status.update(previous_photo_count=len(self.previous["observations"]), preserved_photo_ids=preserved,
                           gallery_photo_count=len(current))
        for filename in ("index.html", "new-top.html", "records.html", "season.html", "features.html",
                         "research.html", "best-shots.html", "favorite.html"):
            file = output / filename
            if not file.is_file() or file.stat().st_size == 0:
                raise SyncError("OUTPUT_PAGE_MISSING")
        now = datetime.now(timezone.utc).isoformat()
        self.status["retired_output_inspection"] = self.retirement.inspect_output(output, portal, self.articles)
        snapshot = seal_snapshot(self.articles, portal, now, self.retirement.ledger)
        validate_snapshot(snapshot, portal)
        self.status["generated_html_pages"] = sum(1 for _ in output.rglob("*.html"))
        self.status.update(result="SUCCESS", last_success_at=now,
                           bootstrap=self.previous_snapshot is None)
        write_json(output / "article-sync-snapshot.json", snapshot)
        # Public status is counts/error codes only; Phase 2 details remain in report.
        public = {k: v for k, v in self.status.items() if k not in {"pending_changes", "pending_classification", "deleted_article_hashes"}}
        write_json(output / "article-sync-status.json", public)
        write_json(self.report_path, self.status)


def run(previous, output="output", report="cache/article-sync-report.json"):
    """Generate into an isolated candidate; failed builds never replace output."""
    import main
    sync = None
    try:
        sync = SyncRun(previous, report)
        output_path = Path(output).resolve()
        original_path = sync.previous_directory.resolve()
        if sync.retirement.initial and (output_path == original_path or output_path in original_path.parents):
            raise SyncError("RETIREMENT_ORIGINAL_OVERWRITE_FORBIDDEN")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="hatena-sync-", dir=output_path.parent) as temporary:
            stage = Path(temporary) / "site"
            originals = {key: value for key, value in vars(main).items()
                         if isinstance(value, str) and (value == main.OUTPUT_DIR
                         or value.startswith(main.OUTPUT_DIR + os.sep))}
            try:
                for key, value in originals.items():
                    setattr(main, key, str(stage) + value[len(main.OUTPUT_DIR):]) if key != "OUTPUT_DIR" else None
                main.OUTPUT_DIR = str(stage)
                # Legacy audits can print article titles/URLs. Keep daily action logs
                # free of source content and third-party error bodies.
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    main.build_gallery(sync_run=sync)
            finally:
                for key, value in originals.items():
                    setattr(main, key, value)
            # This wrapper never writes gh-pages. The existing deployment step runs
            # only after exit 0, with the approved fresh candidate directory.
            if output_path.exists():
                backup = Path(temporary) / "old-site"
                output_path.rename(backup)
                try:
                    stage.rename(output_path)
                except OSError:
                    backup.rename(output_path)
                    raise
            else:
                stage.rename(output_path)
        print("Article sync candidate validated: SUCCESS")
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, SyncError) else "FETCH_OR_GENERATION_ERROR"
        state = deepcopy(sync.status) if sync else {
            "version": 1, **compare_inventory(None, {}), "last_success_at": None,
            "classification_review_count": None}
        state.update(result="BLOCKED", error_code=code, attempted_at=datetime.now(timezone.utc).isoformat())
        state["fetch_error"] = code if code.startswith(("API_", "ATOM_", "FETCH_")) else None
        state["baseline_error"] = code if code.startswith(("BASELINE_", "SNAPSHOT_", "PREVIOUS_", "PORTAL_")) else None
        state["id_compatibility_error"] = code if code in {
            "ID_COMPATIBILITY_ERROR", "PROTECTED_REFERENCE_ERROR", "DUPLICATE_OCCURRENCE_AMBIGUOUS",
            "REMOVED_OR_REPLACED_PUBLISHED_PHOTO", "PUBLISHED_NAME_CHANGE_REQUIRES_REVIEW"} else None
        write_json(report, state)
        print("Article sync blocked: " + code)
        return 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--output", default="output")
    parser.add_argument("--report", default="cache/article-sync-report.json")
    args = parser.parse_args()
    raise SystemExit(run(args.previous, args.output, args.report))
