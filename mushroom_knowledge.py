"""Validation helpers for the offline mushroom knowledge masters.

This module is deliberately independent from the production gallery runtime.
"""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
SOURCES_FILE = ROOT / "data" / "sources.json"
MUSHROOM_MASTER_FILE = ROOT / "data" / "mushroom-master.json"
SUBJECT_TAXONOMY_FILE = ROOT / "data" / "subject-taxonomy.json"
RANKS = ("kingdom", "phylum", "class", "subclass", "order", "family", "genus")
NAME_STATUSES = {"source_reported", "accepted_verified", "unknown"}
FOOD_STATUSES = {
    "unknown", "poisonous_confirmed", "edibility_reported",
    "inedible_reported", "conflicting",
}
RECORD_STATUSES = {"partial", "verified_core"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class MushroomKnowledgeError(ValueError):
    """Raised when a knowledge file violates its schema or provenance rules."""


def _read(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise MushroomKnowledgeError(str(error)) from error


def _root(raw, collection):
    if not isinstance(raw, dict):
        raise MushroomKnowledgeError("root must be an object")
    if type(raw.get("version")) is not int or raw["version"] != 1:
        raise MushroomKnowledgeError("version must be integer 1")
    values = raw.get(collection)
    if not isinstance(values, list):
        raise MushroomKnowledgeError(f"{collection} must be a list")
    return values


def _nonempty(value, field):
    if not isinstance(value, str) or not value.strip():
        raise MushroomKnowledgeError(f"{field} must be a non-empty string")


def _date(value, field):
    _nonempty(value, field)
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise MushroomKnowledgeError(f"{field} must be YYYY-MM-DD") from error


def _source_ids(value, known, field, required=False):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MushroomKnowledgeError(f"{field} must be a string list")
    missing = set(value) - known
    if missing:
        raise MushroomKnowledgeError(f"{field} references unknown sources: {sorted(missing)}")
    if required and not value:
        raise MushroomKnowledgeError(f"{field} requires source provenance")


def load_sources(path=SOURCES_FILE):
    """Load and validate the source registry."""
    raw = _read(path)
    sources = _root(raw, "sources")
    seen = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise MushroomKnowledgeError(f"source {index} must be an object")
        source_id = source.get("source_id")
        for field in ("source_id", "organization", "title", "source_type", "url"):
            _nonempty(source.get(field), f"source {index} {field}")
        if source_id in seen:
            raise MushroomKnowledgeError(f"duplicate source_id: {source_id}")
        seen.add(source_id)
        if urlparse(source["url"]).scheme not in {"http", "https"}:
            raise MushroomKnowledgeError(f"source {index} url must use http or https")
        if source.get("record_id") is not None and not isinstance(source["record_id"], str):
            raise MushroomKnowledgeError(f"source {index} record_id must be string or null")
        _date(source.get("accessed_at"), f"source {index} accessed_at")
        if source.get("notes") is not None and not isinstance(source["notes"], str):
            raise MushroomKnowledgeError(f"source {index} notes must be string or null")
    return raw


def _fact(value, known, field, key="value"):
    if not isinstance(value, dict):
        raise MushroomKnowledgeError(f"{field} must be an object")
    fact = value.get(key)
    if fact is not None and (not isinstance(fact, str) or not fact.strip()):
        raise MushroomKnowledgeError(f"{field}.{key} must be a non-empty string or null")
    _source_ids(value.get("source_ids"), known, f"{field}.source_ids", fact is not None)


def load_mushroom_master(path=MUSHROOM_MASTER_FILE, sources_path=SOURCES_FILE):
    """Load and validate mushroom facts and every source reference."""
    known = {source["source_id"] for source in load_sources(sources_path)["sources"]}
    raw = _read(path)
    entries = _root(raw, "entries")
    ids, names = set(), set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise MushroomKnowledgeError(f"entry {index} must be an object")
        mushroom_id = entry.get("mushroom_id")
        _nonempty(mushroom_id, f"entry {index} mushroom_id")
        if not IDENTIFIER.fullmatch(mushroom_id):
            raise MushroomKnowledgeError(f"entry {index} mushroom_id is not ASCII-ish")
        if mushroom_id in ids:
            raise MushroomKnowledgeError(f"duplicate mushroom_id: {mushroom_id}")
        ids.add(mushroom_id)
        name = entry.get("canonical_name_ja")
        _nonempty(name, f"entry {index} canonical_name_ja")
        if name in names:
            raise MushroomKnowledgeError(f"duplicate canonical_name_ja: {name}")
        names.add(name)
        _source_ids(entry.get("name_ja_sources"), known, f"entry {index} name_ja_sources", True)
        aliases = entry.get("aliases_ja")
        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
            raise MushroomKnowledgeError(f"entry {index} aliases_ja must be a string list")
        scientific = entry.get("scientific_name")
        _fact(scientific, known, f"entry {index} scientific_name")
        if scientific.get("name_status") not in NAME_STATUSES:
            raise MushroomKnowledgeError(f"entry {index} has invalid scientific name status")
        if scientific["name_status"] == "accepted_verified" and not scientific["source_ids"]:
            raise MushroomKnowledgeError("accepted_verified requires source provenance")
        taxonomy = entry.get("taxonomy")
        if not isinstance(taxonomy, dict) or set(taxonomy) != set(RANKS):
            raise MushroomKnowledgeError(f"entry {index} taxonomy must contain all ranks")
        for rank in RANKS:
            _fact(taxonomy[rank], known, f"entry {index} taxonomy.{rank}")
        food = entry.get("food_safety")
        if not isinstance(food, dict) or food.get("status") not in FOOD_STATUSES:
            raise MushroomKnowledgeError(f"entry {index} has invalid food status")
        _source_ids(food.get("source_ids"), known, f"entry {index} food_safety.source_ids",
                    food["status"] != "unknown")
        if not isinstance(food.get("notes"), str):
            raise MushroomKnowledgeError(f"entry {index} food_safety.notes must be a string")
        toxins = entry.get("toxins")
        if not isinstance(toxins, list):
            raise MushroomKnowledgeError(f"entry {index} toxins must be a list")
        for toxin in toxins:
            if not isinstance(toxin, dict):
                raise MushroomKnowledgeError("toxin must be an object")
            _nonempty(toxin.get("name"), "toxin.name")
            _source_ids(toxin.get("source_ids"), known, "toxin.source_ids", True)
        for field in ("features", "season", "habitat"):
            _fact(entry.get(field), known, f"entry {index} {field}", "summary")
        verification = entry.get("verification")
        if not isinstance(verification, dict):
            raise MushroomKnowledgeError(f"entry {index} verification must be an object")
        if verification.get("record_status") not in RECORD_STATUSES:
            raise MushroomKnowledgeError(f"entry {index} has invalid record status")
        _date(verification.get("checked_at"), f"entry {index} verification.checked_at")
        if not isinstance(verification.get("notes"), str):
            raise MushroomKnowledgeError(f"entry {index} verification.notes must be a string")
    return raw


def validate_subject_taxonomy_links(taxonomy_path=SUBJECT_TAXONOMY_FILE,
                                      master_path=MUSHROOM_MASTER_FILE,
                                      sources_path=SOURCES_FILE):
    """Validate optional subject-to-knowledge links without changing production."""
    taxonomy = _read(taxonomy_path)
    subjects = _root(taxonomy, "entries")
    mushrooms = load_mushroom_master(master_path, sources_path)["entries"]
    by_id = {entry["mushroom_id"]: entry for entry in mushrooms}
    for index, subject in enumerate(subjects):
        if not isinstance(subject, dict):
            raise MushroomKnowledgeError(f"subject {index} must be an object")
        mushroom_id = subject.get("mushroom_master_id")
        if mushroom_id is None:
            continue
        if subject.get("subject_type") != "mushroom":
            raise MushroomKnowledgeError("non-mushroom subject cannot link to mushroom master")
        if mushroom_id not in by_id:
            raise MushroomKnowledgeError(f"broken mushroom_master_id: {mushroom_id}")
        if subject.get("canonical_name") != by_id[mushroom_id]["canonical_name_ja"]:
            raise MushroomKnowledgeError("subject and mushroom canonical names do not match")
    return True
