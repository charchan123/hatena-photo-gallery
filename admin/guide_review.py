"""Local review records. This module has no publication or classification writer."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import secrets
import sqlite3
from contextlib import closing
from threading import RLock
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

from PIL import Image

from .core import ROOT
from .draft_store import _fingerprint

CATALOG = Path(__file__).with_name("guide-review") / "catalog.json"
PUBLIC_PORTAL = "https://charchan123.github.io/hatena-photo-gallery/portal-data.json"
IMAGE_HOSTS = {"cdn-ak.f.st-hatena.com", "cdn.image.st-hatena.com"}
MAX_IMAGE = 20 * 1024 * 1024
MAX_EVENTS = 5000
PHOTO_ID = re.compile(r"obs-[0-9a-f]{64}")
HASH = re.compile(r"[0-9a-f]{64}")
KINDS = ("name", "manuscript", "food", "features")
SCOPES = {"all", "photo", "legacy"}
PHOTO_KEYS = {"id", "url", "article_id", "article", "occurrence", "article_revision", "name", "classification", "classification_revision", "capture"}
EVENT_KEYS = {"revision", "item", "kind", "decision", "scope", "basis", "photos", "image_hashes", "note", "reviewer", "origin", "at"}
DECISIONS = {"confirmed", "held", "reset", "note"}


class ReviewError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def text(value, limit=2000, required=False):
    return isinstance(value, str) and len(value) <= limit and (not required or bool(value.strip()))


def identifier(value, pattern):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def allowed_url(value, hosts):
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and parsed.netloc in hosts and not parsed.fragment
    except (TypeError, ValueError):
        return False


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download(url, limit):
    with build_opener(NoRedirect()).open(Request(url, headers={"Cache-Control": "no-cache"}), timeout=10) as response:
        data = response.read(limit + 1)
    require(0 < len(data) <= limit, "ファイルサイズが許容範囲外です")
    return data


def published_portal():
    return json.loads(download(PUBLIC_PORTAL, 15 * 1024 * 1024))


def fetch_photo(url):
    require(allowed_url(url, IMAGE_HOSTS), "写真の配信先を確認できません")
    data = download(url, MAX_IMAGE)
    with Image.open(BytesIO(data)) as picture:
        require(picture.format in {"JPEG", "PNG", "WEBP"} and
                picture.width * picture.height <= 45_000_000, "画像の形式または大きさを確認できません")
        content_type = Image.MIME[picture.format]
        picture.load()
    return data, content_type


def item_id(name):
    return hashlib.sha256(name.encode("utf-8")).hexdigest()


def build_items(catalog, portal):
    require(catalog.get("version") == 1 and portal.get("version") == 1, "確認資料の形式が変わりました")
    by_name = defaultdict(list)
    occurrences = Counter()
    seen = {}
    for row in portal["observations"]:
        key = row["observation_id"]
        require(identifier(key, PHOTO_ID) and key not in seen, "公開写真IDを一意に確認できません")
        seen[key] = row
        article = row["article"]
        occurrence = (article["article_id"], row["src"])
        occurrences[occurrence] += 1
        by_name[row["gallery_name"]].append(dict(
            id=key, url=row["src"], article_id=article["article_id"], article=article["url"],
            occurrence=occurrences[occurrence], article_revision=article.get("updated") or article.get("published") or "",
            name=row["gallery_name"], classification=row["classification"]["status"],
            classification_revision=_fingerprint(row["classification"]),
            capture=row.get("capture", {}).get("date") or ""))
    result = {}
    subjects = {s.get("gallery_name"): s for s in portal.get("subjects", [])}
    for row in catalog["items"]:
        name = row["name"]
        key = item_id(name)
        require(key not in result, "掲載名が重複しています")
        archived = {p["id"]: p for p in row["photos"]}
        photos = []
        for photo in by_name[name]:
            original = archived.get(photo["id"])
            match = original and all((original["src"] == photo["url"], original["article"] == photo["article"],
                                      original["status"] == photo["classification"], original["date"] == photo["capture"],
                                      not original["article_id"] or original["article_id"] == photo["article_id"],
                                      not original.get("article_revision") or original["article_revision"] == photo["article_revision"]))
            article = seen[photo["id"]]["article"]
            photos.append({"identity": photo, "evidence": original if match else None,
                           "published": article.get("published") or ""})
        draft = row["draft"]
        subject = subjects.get(name, {})
        source_urls = {s.get("URL") for s in draft["sources"]} | {s.get("url") for s in draft["preview"]["sources"]}
        refs = portal.get("reference_data", {})
        current_sources = [source for group in (refs.get("sources", {}).get("sources", []),
                                                refs.get("guide_expansion", {}).get("sources", []))
                           for source in group if source.get("url") in source_urls]
        editorial = {"draft": draft, "source_records": current_sources,
                     "master_id": subject.get("mushroom_master_id")}
        legacy = sorted(row.get("legacy_scope", []))
        require(not legacy or (name == "センニンタケ" and len(set(legacy)) == 3
                               and all(identifier(photo, PHOTO_ID) for photo in legacy)),
                "旧承認の対象資料に不整合があります")
        food = draft["fields"]["食毒"]
        reviewable = {
            "manuscript": bool(draft["fields"]["特徴"]),
            "food": bool(food and not any(word in food for word in ("未審査", "未承認", "転用しない", "未確認"))),
            "features": False,
        }
        name_basis = _fingerprint([row["question"], row["group"], row["reason"]])
        content_basis = {kind: _fingerprint([kind, editorial]) for kind in KINDS[1:]}
        result[key] = {**row, "id": key, "photos": photos, "legacy_ids": legacy,
                       "reviewable": reviewable, "name_basis": name_basis, "content_basis": content_basis,
                       "view_basis": {"name": _fingerprint([name_basis, photos, legacy]), **content_basis}}
    return result


def validate_event(event, revision, items):
    require(isinstance(event, dict) and set(event) == EVENT_KEYS, "確認記録の構造が不正です")
    require(type(event["revision"]) is int and event["revision"] == revision, "確認記録の改訂番号が不正です")
    require(isinstance(event["item"], str) and event["item"] in items, "対象外の確認記録があります")
    item = items[event["item"]]
    require(event["kind"] in KINDS and event["decision"] in DECISIONS and identifier(event["basis"], HASH),
            "承認種別・状態・根拠の形式が不正です")
    require(text(event["note"]) and text(event["reviewer"], 80, True) and
            event["origin"] == "localhost-admin" and isinstance(event["at"], str), "確認者またはメモが不正です")
    try:
        moment = datetime.fromisoformat(event["at"])
    except ValueError as error:
        raise ReviewError("確認日時が不正です") from error
    require(moment.tzinfo is not None, "確認日時のタイムゾーンがありません")
    photos, hashes, scope = event["photos"], event["image_hashes"], event["scope"]
    require(isinstance(photos, list) and isinstance(hashes, dict), "写真の記録が不正です")
    ids = set()
    for photo in photos:
        require(isinstance(photo, dict) and set(photo) == PHOTO_KEYS and identifier(photo["id"], PHOTO_ID)
                and photo["id"] not in ids and photo["name"] == item["name"]
                and type(photo["occurrence"]) is int and 0 < photo["occurrence"] <= 10000
                and all(text(photo[key], 1200) for key in PHOTO_KEYS - {"occurrence"})
                and allowed_url(photo["url"], IMAGE_HOSTS)
                and allowed_url(photo["article"], {"exsudoporus-ruber.hatenablog.jp"})
                and identifier(photo["classification_revision"], HASH)
                and bool(photo["article_id"]), "写真の識別情報が不正です")
        ids.add(photo["id"])
    if scope == "legacy":
        require(event["kind"] == "name" and ids == set(item["legacy_ids"]) and len(ids) == 3,
                "旧承認の対象はセンニンタケの指定3枚です")
    if event["kind"] != "name":
        require(scope == "editorial" and not photos and not hashes, "原稿と写真の承認範囲が混在しています")
    else:
        require(scope in SCOPES and (scope != "photo" or len(photos) == 1), "名称確認の範囲が不正です")
        if event["decision"] == "confirmed":
            require(bool(ids) and set(hashes) == ids and all(identifier(val, HASH) for val in hashes.values()),
                    "画像ハッシュが欠落しています")
        else:
            require(not hashes, "確認前の記録に画像確認結果が含まれています")


def validate_backup(doc, items):
    require(isinstance(doc, dict) and set(doc) == {"version", "target", "revision", "events", "checksum"}
            and type(doc["version"]) is int and doc["version"] == 1
            and doc["target"] == "kinoko-guide-review"
            and type(doc["revision"]) is int and isinstance(doc["events"], list)
            and 0 <= len(doc["events"]) == doc["revision"] <= MAX_EVENTS, "バックアップの版・対象・改訂番号が違います")
    payload = {key: value for key, value in doc.items() if key != "checksum"}
    require(doc["checksum"] == _fingerprint(payload), "バックアップの整合性を確認できません")
    for idx, event in enumerate(doc["events"], 1):
        validate_event(event, idx, items)


class GuideReview:
    def __init__(self, root=ROOT, portal_loader=published_portal, image_loader=fetch_photo, catalog=CATALOG):
        self.path = Path(root) / "admin/local-state/guide-review.sqlite3"
        self.portal_loader = portal_loader
        self.image_loader = image_loader
        self.catalog = catalog
        self.lock = RLock()
        self.items = None
        self.proofs = {}

    def refresh(self):
        with self.lock:
            previous = self.items
            self.items = None
            current = build_items(json.loads(self.catalog.read_text(encoding="utf-8")), self.portal_loader())
            self.items = {key: previous[key] if previous and previous.get(key) == item else item
                          for key, item in current.items()}
            if previous != self.items:
                self.proofs = {key: proof for key, proof in self.proofs.items()
                               if key[0] in self.items and any(row["identity"] == proof["identity"]
                               for row in self.items[key[0]]["photos"])}

    def open(self):
        require(not self.path.is_symlink() and not self.path.parent.is_symlink(), "確認記録の保存先を確認してください")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS events (
                revision INTEGER PRIMARY KEY, payload TEXT NOT NULL, local INTEGER NOT NULL CHECK(local IN (0,1)))""")
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def load(self, db, with_trust=False):
        events = []
        rows = db.execute("SELECT revision, payload, local FROM events ORDER BY revision LIMIT ?", (MAX_EVENTS + 1,))
        for idx, (revision, payload, local) in enumerate(rows, 1):
            require(idx == revision and idx <= MAX_EVENTS, "保存済み確認記録の改訂番号が不正です")
            event = json.loads(payload)
            validate_event(event, idx, self.items)
            events.append(event | {"local": bool(local)} if with_trust else event)
        return events

    def snapshot(self, events):
        doc = {"version": 1, "target": "kinoko-guide-review", "revision": len(events), "events": events}
        return {**doc, "checksum": _fingerprint(doc)}

    def records(self, with_trust=False):
        with self.lock:
            if self.items is None:
                self.refresh()
            with closing(self.open()) as db:
                return self.load(db, with_trust)

    def current_proof(self, item, photo):
        proof = self.proofs.get((item["id"], photo["id"]))
        if proof and proof["identity"] == photo and monotonic() - proof["issued"] < 3600:
            return proof

    def status(self, item, records):
        photos = {p["identity"]["id"]: p["identity"] for p in item["photos"]}
        states, reasons = {}, {}
        for event in records:
            if event["kind"] != "name" or event["decision"] == "note":
                continue
            targets = {p["id"]: p for p in event["photos"]}
            if event["decision"] == "reset":
                for key in (list(states) if event["scope"] == "all" else targets):
                    states.pop(key, None)
                    reasons[key] = "corrected"
                continue
            if event["scope"] == "all":
                states.clear()
                reasons.clear()
            changed_set = event["scope"] == "all" and targets.keys() != photos.keys()
            for key, photo in targets.items():
                proof = self.current_proof(item, photo)
                active = photos.get(key)
                reason = None
                if event["decision"] == "confirmed" and not event["local"]:
                    reason = "restored"
                elif changed_set or active is None:
                    reason = "membership"
                elif any(active[field] != photo[field] for field in
                         ("article_id", "article", "occurrence", "article_revision")):
                    reason = "article"
                elif active != photo or event["basis"] != item["name_basis"]:
                    reason = "updated"
                elif event["decision"] == "confirmed" and proof and proof["sha"] != event["image_hashes"][key]:
                    reason = "image"
                if reason:
                    states[key], reasons[key] = "stale", reason
                elif event["decision"] == "held":
                    states[key] = "held"
                else:
                    states[key] = "confirmed" if proof else "verify"
                    reasons.pop(key, None)
        current = {key: states.get(key, "pending") for key in photos}
        if "stale" in states.values() or "verify" in current.values():
            status = "recheck"
        elif photos and all(value == "confirmed" for value in current.values()):
            status = "confirmed"
        elif "confirmed" in current.values():
            status = "individual"
        elif "held" in current.values():
            status = "held"
        else:
            status = "pending"
        editorial, editorial_reasons = {}, {}
        for kind in KINDS[1:]:
            event = next((e for e in reversed(records) if e["kind"] == kind), None)
            editorial[kind] = (("stale" if event["basis"] != item["content_basis"][kind] or
                                (event["decision"] == "confirmed" and not event["local"]) else event["decision"])
                               if event and event["decision"] != "reset" else "pending")
            if event and editorial[kind] == "stale":
                editorial_reasons[kind] = "restored" if not event["local"] else "manuscript"
            elif event and event["decision"] == "reset":
                editorial_reasons[kind] = "corrected"
        return {"status": status, "photo_states": current, "photo_reasons": reasons, "editorial": editorial,
                "editorial_reasons": editorial_reasons, "publication": "locked"}

    def state(self, selected=None):
        with self.lock:
            events = self.records(with_trust=True)
            grouped = defaultdict(list)
            for event in events:
                grouped[event["item"]].append(event)
            statuses = {key: self.status(item, grouped[key]) for key, item in self.items.items()}
            rows = [{key: item[key] for key in ("id", "name", "group", "scope", "priority", "priority_candidate")}
                    | {"count": len(item["photos"]), "status": statuses[item["id"]]["status"],
                       "manuscript": statuses[item["id"]]["editorial"]["manuscript"]} for item in self.items.values()]
            detail = None
            if selected is not None:
                require(selected in self.items, "確認対象が見つかりません")
                detail = self.items[selected] | statuses[selected] | {"history": grouped[selected]}
            return {"revision": len(events), "rows": rows, "item": detail}

    def photo(self, key, observation):
        with self.lock:
            if self.items is None:
                self.refresh()
            item = self.items.get(key)
            require(item is not None, "確認対象がありません")
            photo = next((row["identity"] for row in item["photos"] if row["identity"]["id"] == observation), None)
            require(photo is not None, "対象の写真は現在掲載されていません")
        try:
            data, mime = self.image_loader(photo["url"])
        except (OSError, ValueError):
            with self.lock:
                self.proofs.pop((key, observation), None)
            raise
        sha = hashlib.sha256(data).hexdigest()
        ticket = secrets.token_urlsafe(24)
        with self.lock:
            require(self.items.get(key) is item, "確認対象を再取得してください")
            old = self.current_proof(item, photo)
            if old and old["sha"] == sha:
                ticket = old["ticket"]
            self.proofs[(key, observation)] = {"identity": photo, "sha": sha, "ticket": ticket, "issued": monotonic()}
        return data, mime, ticket

    def change(self, body, *, restore=False):
        with self.lock:
            self.refresh()
            with closing(self.open()) as db:
                db.execute("BEGIN IMMEDIATE")
                current = self.load(db)
                require(type(body.get("revision")) is int and body["revision"] == len(current),
                        "別の画面で保存されました。再取得して確認してください")
                if restore:
                    require(set(body) == {"revision", "backup"}, "取り込み形式が不正です")
                    incoming = body["backup"]
                    validate_backup(incoming, self.items)
                    common = min(len(current), incoming["revision"])
                    require(incoming["events"][:common] == current[:common], "別系統の記録です。現在の履歴を保持しました")
                    additions = incoming["events"][len(current):]
                else:
                    additions = [self.make_event(body, len(current) + 1)]
                for event in additions:
                    db.execute("INSERT INTO events VALUES (?, ?, ?)", (event["revision"], json.dumps(event, ensure_ascii=False), int(not restore)))
                db.execute("COMMIT")
                return {"revision": len(current) + len(additions), "saved": len(additions)}

    def check_confirmed_images(self, item, identity, keys, tickets):
        for key in keys:
            proof = self.current_proof(item, identity[key])
            require(proof and tickets[key] == proof["ticket"], "画像を再読み込みしてから確認してください")
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                checks = list(pool.map(self.image_loader, [identity[key]["url"] for key in keys]))
        except (OSError, ValueError):
            for key in keys:
                self.proofs.pop((item["id"], key), None)
            raise
        hashes = {key: hashlib.sha256(result[0]).hexdigest() for key, result in zip(keys, checks)}
        for key, sha in hashes.items():
            proof = self.current_proof(item, identity[key])
            if not proof or proof["sha"] != sha:
                self.proofs.pop((item["id"], key), None)
                raise ReviewError("画像が更新されました。再取得して目視確認してください")
        return hashes

    def make_event(self, body, revision):
        require(set(body) == {"revision", "item", "kind", "decision", "scope", "photos", "tickets", "reviewer", "note", "ack", "view_basis"}
                and type(body["item"]) is str and body["item"] in self.items
                and body["kind"] in KINDS and body["decision"] in DECISIONS and revision <= MAX_EVENTS,
                "対象・操作・記録上限を確認してください")
        item = self.items[body["item"]]
        kind, decision, scope = body["kind"], body["decision"], body["scope"]
        require(body["view_basis"] == item["view_basis"][kind],
                "写真・原稿・出典の情報が更新されました。再取得して確認してください")
        keys, tickets = body["photos"], body["tickets"]
        require(isinstance(keys, list) and isinstance(tickets, dict)
                and all(identifier(key, PHOTO_ID) for key in keys) and len(set(keys)) == len(keys), "写真の指定が不正です")
        identity = {row["identity"]["id"]: row["identity"] for row in item["photos"]}
        hashes = {}
        if kind == "name":
            require(scope in SCOPES and set(keys) <= identity.keys(), "写真の確認範囲が変わりました")
            expected = set(item["legacy_ids"]) if scope == "legacy" else identity.keys()
            if scope != "photo":
                require(set(keys) == expected, "写真の確認範囲が変わりました")
            if decision == "confirmed":
                require(scope != "all" or item["group"] in {"A", "B"}, "この項目は写真ごとに確認してください")
                require(body["ack"] is True and set(tickets) == set(keys), "表示した写真の確認操作が必要です")
                hashes = self.check_confirmed_images(item, identity, keys, tickets)
            basis = item["name_basis"]
        else:
            require(scope == "editorial" and not keys and not tickets, "原稿の確認範囲が不正です")
            if decision == "confirmed":
                require(body["ack"] is True and text(body["note"], 2000, True), "審査した根拠を記入してください")
                require(item["reviewable"][kind], "承認に必要な内容と根拠資料が揃っていません")
            basis = item["content_basis"][kind]
        event = {"revision": revision, "item": item["id"], "kind": kind, "decision": decision,
                 "scope": scope, "basis": basis, "photos": [identity[key] for key in keys],
                 "image_hashes": hashes, "note": body["note"], "reviewer": body["reviewer"],
                 "origin": "localhost-admin", "at": datetime.now(timezone.utc).isoformat()}
        validate_event(event, revision, self.items)
        return event
