import copy
import json

import pytest

import main
import mushroom_knowledge as knowledge


BATCH_1_LABELS = (
    "ドクツルタケ", "チチアワタケ", "ヒラタケ", "ヤナギマツタケ",
    "チャアミガサタケ", "オオシロカラカサタケ", "アイタケ",
    "マツオウジ", "ウスヒラタケ", "キイロスッポンタケ",
)

BATCH_2_LABELS = (
    "アカヤマドリ", "ヒロメノトガリアミガサタケ", "アミガサタケ", "キクラゲ",
    "ヘビキノコモドキ", "ハナイグチ", "カラカサタケ", "ヤマイグチ",
    "キクバナイグチ", "クロカワ",
)


def write_json(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def repository_data():
    sources = knowledge.load_sources()
    master = knowledge.load_mushroom_master()
    taxonomy = json.loads(knowledge.SUBJECT_TAXONOMY_FILE.read_text(encoding="utf-8"))
    return sources, master, taxonomy


def test_repository_counts_policies_and_links():
    sources, master, taxonomy = repository_data()
    assert len(sources["sources"]) == 25
    assert len(master["entries"]) == 21
    assert len(taxonomy["entries"]) == 28
    assert sum(row["subject_type"] == "mushroom" for row in taxonomy["entries"]) == 25
    assert sum(row["subject_type"] == "non_mushroom" for row in taxonomy["entries"]) == 3
    assert {row["canonical_name"] for row in taxonomy["entries"] if row["verification_status"] == "externally_verified"} == set(BATCH_1_LABELS + BATCH_2_LABELS)
    assert all(row["scientific_name"]["name_status"] == "source_reported" for row in master["entries"])
    assert {row["canonical_name_ja"] for row in master["entries"] if row["food_safety"]["status"] == "poisonous_confirmed"} == {"カエンタケ", "ドクツルタケ", "ヘビキノコモドキ"}
    by_name = {row["canonical_name_ja"]: row for row in master["entries"]}
    assert all(by_name[name]["scientific_name"]["name_status"] == "source_reported" for name in BATCH_2_LABELS)
    assert all(by_name[name]["food_safety"]["status"] == "edibility_reported" for name in ("アカヤマドリ", "キクラゲ", "ハナイグチ", "カラカサタケ", "ヤマイグチ", "キクバナイグチ"))
    assert by_name["ヘビキノコモドキ"]["food_safety"]["status"] == "poisonous_confirmed"
    assert all(by_name[name]["food_safety"]["status"] == "unknown" for name in ("ヒロメノトガリアミガサタケ", "アミガサタケ", "クロカワ"))
    assert "広義アミガサタケ" not in by_name["アミガサタケ"]["aliases_ja"]
    assert "キクラゲ（広義）" not in by_name["キクラゲ"]["aliases_ja"]
    assert not any(row["food_safety"]["status"] in {"safe", "safe_to_eat", "edible_safe", "non_poisonous"} for row in master["entries"])
    assert knowledge.validate_subject_taxonomy_links()


def test_classification_regression_and_uncertain_gallery_name(tmp_path):
    taxonomy = main.load_subject_taxonomy()
    for label in BATCH_1_LABELS + BATCH_2_LABELS:
        assert main.classify_subject_type(label, taxonomy) == ("mushroom", "taxonomy_mushroom", "high")
    for label in ("不明", "おまけ", "カルガモ", "カワラバト", "ソメイヨシノ", "ヒガンバナ"):
        assert main.classify_subject_type(label, taxonomy) == ("review", "taxonomy_unmatched", "low")
    article = tmp_path / "article.html"
    article.write_text('<p>アミガサタケ？</p><img src="x.jpg" alt="legacy">', encoding="utf-8")
    row = main.extract_shadow_metadata([article], taxonomy=taxonomy)[0]
    assert (row["subject_type"], row["classification_confidence"]) == ("mushroom", "high")
    assert (row["gallery_name"], row["detected_label"]) == ("不明", "アミガサタケ？")


def test_duplicate_source_id_is_rejected(tmp_path):
    sources, _, _ = repository_data()
    sources["sources"].append(copy.deepcopy(sources["sources"][0]))
    with pytest.raises(knowledge.MushroomKnowledgeError, match="duplicate source_id"):
        knowledge.load_sources(write_json(tmp_path, "sources.json", sources))


@pytest.mark.parametrize("field", ["mushroom_id", "canonical_name_ja"])
def test_duplicate_mushroom_identity_is_rejected(tmp_path, field):
    sources, master, _ = repository_data()
    master["entries"][1][field] = master["entries"][0][field]
    with pytest.raises(knowledge.MushroomKnowledgeError, match=f"duplicate {field}"):
        knowledge.load_mushroom_master(write_json(tmp_path, "master.json", master), write_json(tmp_path, "sources.json", sources))


def test_missing_source_reference_is_rejected(tmp_path):
    sources, master, _ = repository_data()
    master["entries"][0]["features"]["source_ids"] = ["missing"]
    with pytest.raises(knowledge.MushroomKnowledgeError, match="unknown sources"):
        knowledge.load_mushroom_master(write_json(tmp_path, "master.json", master), write_json(tmp_path, "sources.json", sources))


@pytest.mark.parametrize("status", ["invalid", "safe", "safe_to_eat", "edible_safe", "non_poisonous"])
def test_invalid_and_safe_food_statuses_are_rejected(tmp_path, status):
    sources, master, _ = repository_data()
    master["entries"][0]["food_safety"]["status"] = status
    with pytest.raises(knowledge.MushroomKnowledgeError, match="invalid food status"):
        knowledge.load_mushroom_master(write_json(tmp_path, "master.json", master), write_json(tmp_path, "sources.json", sources))


def test_confirmed_food_status_without_source_is_rejected(tmp_path):
    sources, master, _ = repository_data()
    master["entries"][0]["food_safety"]["source_ids"] = []
    with pytest.raises(knowledge.MushroomKnowledgeError, match="requires source provenance"):
        knowledge.load_mushroom_master(write_json(tmp_path, "master.json", master), write_json(tmp_path, "sources.json", sources))


def test_accepted_name_without_source_is_rejected(tmp_path):
    sources, master, _ = repository_data()
    master["entries"][0]["scientific_name"].update(name_status="accepted_verified", source_ids=[])
    with pytest.raises(knowledge.MushroomKnowledgeError, match="requires source provenance"):
        knowledge.load_mushroom_master(write_json(tmp_path, "master.json", master), write_json(tmp_path, "sources.json", sources))


@pytest.mark.parametrize("mutation,message", [
    (lambda row: row.update(mushroom_master_id="missing"), "broken mushroom_master_id"),
    (lambda row: row.update(subject_type="non_mushroom"), "non-mushroom"),
    (lambda row: row.update(canonical_name="不一致"), "canonical names"),
])
def test_invalid_cross_file_links_are_rejected(tmp_path, mutation, message):
    sources, master, taxonomy = repository_data()
    row = next(row for row in taxonomy["entries"] if row.get("mushroom_master_id") == "kaentake")
    mutation(row)
    with pytest.raises(knowledge.MushroomKnowledgeError, match=message):
        knowledge.validate_subject_taxonomy_links(
            write_json(tmp_path, "taxonomy.json", taxonomy),
            write_json(tmp_path, "master.json", master),
            write_json(tmp_path, "sources.json", sources),
        )
