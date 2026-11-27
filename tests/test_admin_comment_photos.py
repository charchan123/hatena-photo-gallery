from research_ui import build_research_cases

from admin.comment_photos import entries


def row(n, article, name="不明"):
    return dict(observation_id=f"obs-{n}", gallery_name=name,
                article=dict(article_id=article, url=f"https://exsudoporus-ruber.hatenablog.jp/entry/{article}"),
                src=f"https://cdn-ak.f.st-hatena.com/photos/{n}.jpg")


def test_permanent_id_and_complete_scope_include_identified_without_name_matching():
    portal = {"version": 1, "observations": [row(1, "one"), row(2, "two"), row(3, "one")]}
    cases = {c["article"]["article_id"]: c for c in build_research_cases(portal)}
    permanent = ["research-1111111111111111", "research-2222222222222222"]
    registry = {"version": 1, "cases": [
        dict(id=key, label="不明", article_identity=["article_id", article],
             observation_ids=members, render_ids=[key, cases[article]["case_id"]])
        for key, article, members in zip(permanent, ["one", "two"], [["obs-1", "obs-3"], ["obs-2"]])
    ]}
    identified = {"identifications": [{"case_id": cases["one"]["case_id"], "status": "identified"}]}
    found = entries(portal, registry, identified)
    assert found[permanent[0]]["phase"] == "identified"
    assert found[permanent[0]]["render_id"] != permanent[0]
    assert {p["src"].rsplit("/", 1)[-1] for p in found[permanent[0]]["photos"]} == {"1.jpg", "3.jpg"}
    assert found[permanent[1]]["photo_count"] == 1
    portal["observations"].append(row(4, "one"))
    pending = entries(portal, registry, identified)
    assert pending[permanent[0]]["photos"] == []
    portal["observations"][1]["src"] = "https://untrusted.example/2.jpg"
    assert entries(portal, registry, identified)[permanent[1]]["photo_status"] == "unavailable"
