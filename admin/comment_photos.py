"""Resolve the admin's comment photos using the public research binding registry."""
import json
from collections import Counter

from research_comments import prepare
from research_ui import _article_identity, build_research_cases

from .core import ROOT
from .guide_review import IMAGE_HOSTS, allowed_url

ARTICLE_HOSTS = {"exsudoporus-ruber.hatenablog.jp"}


def entries(portal, registry=None, identifications=None):
    if registry is None:
        registry = json.loads((ROOT / "comments/cases.json").read_text(encoding="utf-8"))
    if identifications is None:
        identifications = json.loads((ROOT / "data/research-identifications.json").read_text(encoding="utf-8"))
    identified = {row["case_id"] for row in identifications["identifications"] if row["status"] == "identified"}
    cases = build_research_cases(portal)
    binding = prepare(cases, registry)
    observations = portal.get("observations", [])
    counted = Counter(row.get("observation_id") for row in observations)
    by_id = {row["observation_id"]: row for row in observations if counted[row.get("observation_id")] == 1}
    active_members = {photo.get("observation_id") for case in cases for photo in case["photos"]}
    by_render = {case["case_id"]: case for case in cases}
    catalog = {}
    for render_id, permanent in binding["bindings"].items():
        case = by_render[render_id]
        members = [photo["observation_id"] for photo in case["photos"]]
        raw = [by_id.get(key) for key in members]
        catalog[permanent] = describe(raw, render_id, "identified" if render_id in identified else "active")

    for old in binding["archived"]:
        members = old["observation_ids"]
        raw = [by_id.get(key) for key in members]
        matches = not active_members.intersection(members) and all(
            row and list(_article_identity(row.get("article")) or ()) == old["article_identity"] for row in raw
        )
        catalog[old["id"]] = describe(raw if matches else [], None, "archived")
    return catalog


def describe(observations, render_id, phase):
    result = {"render_id": render_id, "phase": phase, "photos": [], "photo_count": len(observations)}
    if not observations or not all(row and allowed_url(row.get("src"), IMAGE_HOSTS) for row in observations):
        result["photo_status"] = "unavailable"
        return result
    for row in observations:
        article = row["article"]
        url = article.get("url")
        result["photos"].append({
            "src": row["src"], "date": row.get("capture", {}).get("date"),
            "article_url": url if allowed_url(url, ARTICLE_HOSTS) else None,
            "article_title": article.get("title"),
        })
    result["photo_status"] = "matched"
    return result
