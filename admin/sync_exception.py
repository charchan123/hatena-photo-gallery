"""Fail-closed, audit-only exception request. This file NEVER authorizes a sync.

A request PR stores identity-bound evidence for a later, separate migration.
No generator, registry, classification, or publication code reads these requests.
"""
import re

from article_sync import digest, payload_hash

DIGEST = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^sync-[0-9a-f]{64}$")
OPERATIONS = {"propose_name", "exclude", "delete"}
STATE = "REQUEST_ONLY_NOT_APPLIED"


class RequestError(ValueError):
    """A stable error code; do not put private article data in exceptions."""


def _name(value):
    return (isinstance(value, str) and len(value) <= 120
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))


def validate_request(request):
    """Strict schema and digest check; assertions are not bypassable with -O."""
    try:
        if not isinstance(request, dict) or set(request) != {
                "version", "request_id", "state", "source", "identity", "proposal"}:
            raise ValueError()
        if type(request["version"]) is not int or request["version"] != 1 or request["state"] != STATE:
            raise ValueError()
        source, identity, proposal = (request[key] for key in ("source", "identity", "proposal"))
        if not isinstance(source, dict) or set(source) != {
                "main_sha", "publication_sha", "snapshot_sha256", "inventory_sha256", "bundle_sha256"}:
            raise ValueError()
        # Git commit IDs are SHA-1; snapshot/bundle identifiers are SHA-256.
        for k in ("main_sha", "publication_sha"):
            if not isinstance(source[k], str) or not re.fullmatch(r"[0-9a-f]{40}", source[k]):
                raise ValueError()
        for k in ("snapshot_sha256", "inventory_sha256", "bundle_sha256"):
            if not isinstance(source[k], str) or not DIGEST.fullmatch(source[k]):
                raise ValueError()
        if not isinstance(identity, dict) or set(identity) != {
                "candidate_id", "article_hash", "url_hash", "ordinal",
                "observation_id", "old_name", "candidate_name", "fingerprint"}:
            raise ValueError()
        if not ID.fullmatch(identity["candidate_id"]):
            raise ValueError()
        if not all(isinstance(identity[k], str) and DIGEST.fullmatch(identity[k])
                   for k in ("article_hash", "url_hash", "fingerprint")):
            raise ValueError()
        if type(identity["ordinal"]) is not int or identity["ordinal"] < 0:
            raise ValueError()
        if identity["candidate_id"] != "sync-" + payload_hash(
                [identity["article_hash"], identity["url_hash"], identity["ordinal"]]):
            raise ValueError()
        if identity["observation_id"] is not None and (
                not isinstance(identity["observation_id"], str)
                or not re.fullmatch(r"obs-[0-9a-f]{64}|obs-[A-Za-z0-9_-]{1,100}", identity["observation_id"])):
            raise ValueError()
        if any(v is not None and not _name(v) for v in
               (identity["old_name"], identity["candidate_name"])):
            raise ValueError()
        if not isinstance(proposal, dict) or set(proposal) != {
                "operation", "proposed_name", "decided_at", "note_sha256", "application"}:
            raise ValueError()
        if proposal["operation"] not in OPERATIONS or proposal["application"] != STATE:
            raise ValueError()
        if not _name(proposal["proposed_name"]) or (
                proposal["operation"] == "propose_name" and not proposal["proposed_name"].strip()):
            raise ValueError()
        if proposal["operation"] != "propose_name" and proposal["proposed_name"] != "":
            raise ValueError()
        from datetime import datetime
        if not isinstance(proposal["decided_at"], str) or datetime.fromisoformat(
                proposal["decided_at"]).tzinfo is None:
            raise ValueError()
        if not isinstance(proposal["note_sha256"], str) or not DIGEST.fullmatch(proposal["note_sha256"]):
            raise ValueError()
        payload = {k: v for k, v in request.items() if k != "request_id"}
        if request["request_id"] != payload_hash(payload):
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise RequestError("SYNC_REQUEST_INVALID") from None
    return request


def build_request(review, candidate_id, main_sha):
    """Bind a locally reviewed exception to the exact current live/public evidence."""
    if not review.live or not review.publication or not review.bundle_id:
        raise RequestError("LIVE_REVIEW_REQUIRED")
    row = next((row for row in review.rows if row["candidate_id"] == candidate_id), None)
    decision = review.decisions.get(candidate_id)
    if row is None or decision is None or decision.get("decision") not in OPERATIONS:
        raise RequestError("EXPLICIT_EXCEPTION_REVIEW_REQUIRED")
    if (decision.get("bundle_id") != review.bundle_id
            or decision.get("base_snapshot_sha256") != review.publication["article-sync-snapshot.json"]["sha256"]
            or decision.get("inventory_sha256") != review.inventory_hash
            or decision.get("fingerprint") != row["fingerprint"]):
        raise RequestError("STALE_EXCEPTION_REVIEW")
    if decision["decision"] == "propose_name" and not (
            isinstance(decision.get("proposed_name"), str) and decision["proposed_name"].strip()):
        raise RequestError("PROPOSED_NAME_REQUIRED")
    # Never create a migration request for a normally auto-addable new image.
    if row.get("auto_eligible") or (
            row["change_type"] == "automatically_added_photo"):
        raise RequestError("NORMAL_SYNC_NEEDS_NO_APPROVAL")
    # A URL match requires a separately demonstrated old/new identity pairing.
    if decision["decision"] == "delete" and not row.get("protected_existing"):
        raise RequestError("DELETE_REQUIRES_PUBLISHED_ID")
    if decision["decision"] == "exclude" and row.get("protected_existing"):
        raise RequestError("PROTECTED_PHOTO_REQUIRES_DELETE_REVIEW")
    if not isinstance(main_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", main_sha):
        raise RequestError("MAIN_SHA_INVALID")
    evidence = {
        "version": 1,
        "state": STATE,
        "source": {
            "main_sha": main_sha,
            "publication_sha": review.publication["publication_sha"],
            "snapshot_sha256": review.publication["article-sync-snapshot.json"]["sha256"],
            "inventory_sha256": review.inventory_hash,
            "bundle_sha256": review.bundle_id,
        },
        "identity": {
            "candidate_id": row["candidate_id"],
            "article_hash": row["article_hash"],
            "url_hash": row["url_hash"],
            "ordinal": row["ordinal"],
            "observation_id": row["observation_id"],
            "old_name": row["current_name"],
            "candidate_name": row["candidate_name"],
            "fingerprint": row["fingerprint"],
        },
        "proposal": {
            "operation": decision["decision"],
            "proposed_name": decision["proposed_name"],
            "decided_at": decision["decided_at"],
            # Human notes stay local; only a non-reversible digest leaves the machine.
            "note_sha256": digest(decision["comment"]),
            "application": STATE,
        },
    }
    return validate_request({**evidence, "request_id": payload_hash(evidence)})
