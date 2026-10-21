"""127.0.0.1-only HTTP server for きのこブログ管理室."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
from urllib.parse import unquote, parse_qs, urlsplit
import urllib.request
import webbrowser

from best_shot_ui import BestShotConfigError, validate_best_shot_config

from research_ui import build_research_cases
from research_identifications import split_research_cases
from . import comments_client
from .core import ChangeSet, DATA, ROOT, notice_window, read_json
from .draft_store import DraftRecoveryError, DraftStore
from .git_workflow import (GitWorkflowError, create_pull_request,
                           create_knowledge_pull_request, repository_status, run)
from .knowledge import (preview_promotion, reset_review_state,
                        scan_knowledge_batches, set_candidate_decision)

from .sync import SyncReview, ReviewError, latest_actions
from article_sync import SyncError
from . import sync_exception, sync_adoption
from .deletions import DeletionReview, MESSAGES as DELETION_MESSAGES

BIND_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 8765
STATIC = Path(__file__).with_name("static")


def load_portal_data():
    local = ROOT / "output" / "portal-data.json"
    if local.is_file():
        return read_json(local), "local output"
    url = "https://charchan123.github.io/hatena-photo-gallery/portal-data.json"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.load(response)
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("unexpected portal schema")
        return data, "published gh-pages (read-only)"
    except Exception as error:
        raise RuntimeError("portal-data.jsonを取得できませんでした。先にmain.pyを実行してください") from error


class AdminServer(ThreadingHTTPServer):
    allow_reuse_address = True
    def __init__(self, address, handler):
        if address[0] != BIND_ADDRESS:
            raise ValueError("Admin Console may bind only to 127.0.0.1")
        super().__init__(address, handler)
        self.portal, self.portal_source = load_portal_data()
        self.draft_store = DraftStore()
        self.draft = self.draft_store.recover(ChangeSet(self.portal))
        self.draft_lock = threading.RLock()
        self.sync_review = SyncReview()
        self.deletion_review = DeletionReview()
        self.csrf_token = secrets.token_urlsafe(32)


class Handler(BaseHTTPRequestHandler):
    server_version = "KinokoAdmin/1"
    def _local_request(self):
        host = self.headers.get("Host", "").split(":", 1)[0]
        client = self.client_address[0]
        origin = self.headers.get("Origin")
        allowed_origin = not origin or origin in {f"http://127.0.0.1:{self.server.server_port}",
                                                 f"http://localhost:{self.server.server_port}"}
        return host in {"127.0.0.1", "localhost"} and client in {"127.0.0.1", "::1"} and allowed_origin

    def _json(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https: data:; style-src 'self'; script-src 'self'")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 <= length <= 1_000_000: raise ValueError("request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if not self._local_request(): return self._json({"error": "localhost only"}, 403)
        path = self.path.split("?", 1)[0]
        if path == "/api/deletions/state":
            try:
                review = self.server.deletion_review
                return self._json(review.dashboard() if review.publication else review.refresh())
            except Exception as error:
                code = str(error) if isinstance(error, (SyncError, ReviewError)) else "DELETION_REVIEW_UNAVAILABLE"
                return self._json({"error": code, "message": DELETION_MESSAGES.get(code, "削除の検出結果を取得できませんでした。承認は行っていません。")}, 400)
        if path.startswith("/api/sync/"):
            try:
                review = self.server.sync_review
                if not review.publication: review.refresh()
                if path == "/api/sync/state":
                    value = review.dashboard()
                    value["latest_action"] = latest_actions()
                    return self._json(value)
                if path == "/api/sync/candidates":
                    query = parse_qs(urlsplit(self.path).query)
                    if set(query) - {"q", "group", "page"}: raise ReviewError("INVALID_FILTER")
                    return self._json(review.page(query.get("q", [""])[0], query.get("group", [""])[0], int(query.get("page", ["1"])[0])))
                return self._json({"error":"not found"},404)
            except Exception as error:
                return self._json({"error": str(error) if isinstance(error,(ReviewError,SyncError)) else "SYNC_REVIEW_UNAVAILABLE"},400)
        if path == "/api/comments/status":
            from research_comments import prepare
            from research_ui import build_research_cases
            value = comments_client.status()
            binding = prepare(build_research_cases(self.server.portal))
            value.update(pending_cases=binding['pending'], archived_threads=len(binding['archived']))
            if binding['pending'] or binding['archived']:
                value['message'] += f" 紐付け確認待ち{len(binding['pending'])}件・履歴保管{len(binding['archived'])}件。対応表を手動確認してください。"
            return self._json(value)
        if path == "/api/state":
            draft = self.server.draft
            open_cases, identified = split_research_cases(draft.portal, draft.identifications, draft.master)
            observations = draft.portal.get("observations", [])
            try: repo = repository_status()
            except GitWorkflowError: repo = {"branch": "取得できませんでした", "dirty": None, "gh_authenticated": False}
            knowledge = scan_knowledge_batches(origin_main_sha=repo.get("origin_main_sha"))
            state = {"csrf": self.server.csrf_token, "portal_source": self.server.portal_source,
                     "best_shots": draft.best_shots,
                     "best_shot_dates": validate_best_shot_config(draft.best_shots, draft.portal),
                     "notices": [{**e, **notice_window(e)} for e in draft.notices["events"]],
                     "draft_saved": self.server.draft_store.saved,
                     "draft_restored": self.server.draft_store.restored,
                     "cases": open_cases, "identified": identified, "observations": observations,
                     "master": draft.master.get("entries", []), "preview": draft.preview(), "repo": repo,
                     "production_mode": draft.portal.get("production_mode", "取得できませんでした"),
                     "portal_observation_count": len(observations),
                     "feature_facets": read_json(DATA / "feature-facets.json"),
                     "knowledge": knowledge,
                     "counts": {"best_shots": len(draft.best_shots["entries"]),
                                "annual_years": len(draft.best_shots["annual_best"]), "research_open": len(open_cases),
                                "research_identified": len(identified),
                                "active_notices": sum(notice_window(e)["active"] for e in draft.notices["events"]),
                                "master": len(draft.master.get("entries", [])),
                                "sources": len(read_json(DATA / "sources.json").get("sources", [])),
                                "knowledge_batches": len(knowledge),
                                "knowledge_pending": sum(row.get("pending_count", 0) for row in knowledge)}}
            return self._json(state)
        if path == "/": path = "/index.html"
        relative = unquote(path).lstrip("/")
        if "/" in relative or ".." in relative or relative not in {"index.html", "admin.css", "admin.js", "deletions.js", "comments.js"}:
            return self._json({"error": "not found"}, 404)
        data = (STATIC / relative).read_bytes(); mime = {"html":"text/html", "css":"text/css", "js":"text/javascript"}[relative.rsplit(".",1)[1]]
        self.send_response(200); self.send_header("Content-Type", mime + "; charset=utf-8"); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        if not self._local_request(): return self._json({"error": "localhost only"}, 403)
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf_token):
            return self._json({"error": "CSRF validation failed"}, 403)
        try:
            body = self._body(); draft = self.server.draft
            actions = {
                "/api/best-shot/add": lambda: draft.add_best_shot(body["entry"], annual=body.get("annual", False), add_notice=body.get("add_notice", False), occurred_at=body.get("occurred_at")),
                "/api/best-shot/update": lambda: draft.update_best_shot(body["selection_id"], body["changes"]),
                "/api/best-shot/delete": lambda: draft.delete_best_shot(body["selection_id"]),
                "/api/best-shot/annual": lambda: draft.set_annual(body["year"], body.get("selection_id")),
                "/api/notice/add": lambda: draft.add_notice(body["section"], body["kind"], body["summary"], body.get("occurred_at")),
                "/api/notice/update": lambda: draft.update_notice(body["index"], body["event"]),
                "/api/notice/delete": lambda: draft.delete_notice(body["index"]),
                "/api/identify": lambda: draft.identify(next(c for c in build_research_cases(draft.portal) if c["case_id"] == body["case_id"]), body["identified_name"], body.get("note", ""), summary=body.get("summary", "1種の正体が判明")),
                "/api/reopen": lambda: draft.reopen(body["identification_id"]),
            }
            if self.path.startswith("/api/deletions/"):
                review = self.server.deletion_review
                if self.path == "/api/deletions/refresh":
                    if set(body) != {"live"} or type(body["live"]) is not bool: raise SyncError("DELETION_APPROVAL_INVALID")
                    result = review.refresh(live=body["live"])
                elif self.path == "/api/deletions/decision": result = review.decide(body)
                elif self.path == "/api/deletions/preview":
                    if body: raise SyncError("DELETION_APPROVAL_INVALID")
                    result = review.preview_changes()
                elif self.path == "/api/deletions/pr": result = review.create_pr(body)
                else: return self._json({"error":"not found"},404)
            elif self.path.startswith("/api/sync/"):
                review = self.server.sync_review
                if self.path == "/api/sync/refresh":
                    if set(body) - {"live"} or type(body.get("live",False)) is not bool: raise ReviewError("INVALID_REFRESH")
                    result = review.refresh(fetch=True, with_live=body.get("live", False))
                elif self.path == "/api/sync/decision": result = review.decide(body)
                elif self.path == "/api/sync/preview":
                    if body: raise ReviewError("INVALID_INPUT")
                    result = review.preview()
                elif self.path == "/api/sync/adoption-preview": result = sync_adoption.preview(review,body)
                elif self.path == "/api/sync/adoption-approve": result = sync_adoption.approve(review,body)
                elif self.path == "/api/sync/adoption-pr": result = sync_adoption.create_pull_request(review,body)
                elif self.path == "/api/sync/exception-preview": result = sync_exception.preview(review,body)
                elif self.path == "/api/sync/exception-approve": result = sync_exception.approve(review,body)
                elif self.path == "/api/sync/exception-pr": result = sync_exception.create_pull_request(review,body)
                elif self.path == "/api/sync/pr":
                    if body: raise ReviewError("INVALID_INPUT")
                    raise ReviewError("INDIVIDUAL_MIGRATION_REQUIRED")
                else: return self._json({"error":"not found"},404)
            elif self.path == "/api/comments/request":
                if not isinstance(body, dict) or set(body) != {"action", "values"}:
                    raise comments_client.CommentsError("コメント操作の入力が不正です")
                result = comments_client.request(body["action"], body["values"])
            elif self.path == "/api/validate": result = draft.validate()
            elif self.path == "/api/pr":
                # Serialize publication with edits; publish precisely the durable,
                # validated snapshot, never an edit that failed to autosave.
                with self.server.draft_lock:
                    validation = draft.validate()
                    if draft.files() == self.server.draft_store.baseline:
                        raise GitWorkflowError("変更がありません。変更予定を確認してください")
                    self.server.draft_store.verify_saved(draft)
                    result = create_pull_request(
                        draft.files(), validation, body.get("operation", "changes"),
                        baseline=self.server.draft_store.baseline)
            elif self.path == "/api/knowledge/decision": result = set_candidate_decision(body["batch_id"], body["candidate_id"], body["human_decision"], body.get("note", ""))
            elif self.path == "/api/knowledge/reset": result = reset_review_state(body["batch_id"])
            elif self.path == "/api/knowledge/preview": result = preview_promotion(body["batch_id"], origin_main_sha=repository_status().get("origin_main_sha"))
            elif self.path == "/api/knowledge/pr": result = create_knowledge_pull_request(body["batch_id"])
            elif self.path in actions:
                # A single durable transaction across compound Best Shot / notice
                # operations. A failed disk write must not acknowledge the edit.
                with self.server.draft_lock:
                    original = deepcopy(draft.files())
                    try:
                        result = actions[self.path]() or {"ok": True}
                        self.server.draft_store.save(draft)
                    except Exception:
                        draft.best_shots = original["data/best-shots.json"]
                        draft.notices = original["data/update-notices.json"]
                        draft.identifications = original["data/research-identifications.json"]
                        raise
            else: return self._json({"error": "not found"}, 404)
            return self._json(result)
        except Exception as error:
            code = str(error)
            if self.path == "/api/comments/request":
                message = str(error) if isinstance(error, comments_client.CommentsError) else "コメント操作に失敗しました。入力を保持して再確認してください"
                return self._json({"error":"COMMENTS_OPERATION_FAILED","message":message},400)
            if self.path.startswith("/api/deletions/"):
                code = str(error) if isinstance(error, (SyncError, ReviewError)) else "DELETION_OPERATION_FAILED"
                return self._json({"error":code,"message":DELETION_MESSAGES.get(code,"削除操作に失敗しました。入力内容と保存済みの判断は保持しています。再取得して確認してください。")},400)
            if self.path == "/api/pr":
                # Do not pretend a failed git/gh operation succeeded.
                # The local autosaved draft is unchanged and may be retried.
                if isinstance(error, GitWorkflowError):
                    message = str(error)
                elif isinstance(error, BestShotConfigError):
                    message = error.user_message
                elif isinstance(error, DraftRecoveryError):
                    message = str(error)
                elif isinstance(error, OSError):
                    message = (f"下書きの保存状態を確認できません: {error}。保存済み下書きは保持しています。"
                               "空き容量・書き込み権限を確認してから再実行してください")
                else:
                    message = (f"変更内容の検証に失敗しました: {error}。下書きは保持しています。"
                               "入力内容を確認して再検証してください")
                return self._json({"error": "PR_CREATION_FAILED", "message": message}, 400)
            if self.path.startswith("/api/best-shot/"):
                message = (error.user_message if isinstance(error, BestShotConfigError)
                           else "ベストショットの保存に失敗しました。入力内容と変更予定を確認してください")
                fields = ({error.field: message} if isinstance(error, BestShotConfigError) and error.field else {})
                return self._json({"error": code, "message": message, "field_errors": fields}, 400)
            if self.path.startswith("/api/sync/") and not isinstance(error,(ReviewError,SyncError)):
                code = "SYNC_OPERATION_FAILED"
            return self._json({"error": code}, 400)

    def log_message(self, fmt, *args):
        if self.path.startswith(("/api/sync/", "/api/deletions/")): return
        print(f"[{datetime.now(timezone.utc).isoformat()}] {self.client_address[0]} {fmt % args}")


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=DEFAULT_PORT); parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv); server = AdminServer((BIND_ADDRESS, args.port), Handler)
    url = f"http://{BIND_ADDRESS}:{args.port}/"; print(f"きのこブログ管理室: {url}")
    if not args.no_browser: webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__": main()
