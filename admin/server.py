"""127.0.0.1-only HTTP server for きのこブログ管理室."""

import argparse
from datetime import datetime, timezone
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
from urllib.parse import unquote
import urllib.request
import webbrowser

from research_ui import build_research_cases
from research_identifications import split_research_cases
from .core import ChangeSet, DATA, ROOT, notice_window, read_json
from .git_workflow import (GitWorkflowError, create_pull_request,
                           create_knowledge_pull_request, repository_status, run)
from .knowledge import (preview_promotion, reset_review_state,
                        scan_knowledge_batches, set_candidate_decision)

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
        self.draft = ChangeSet(self.portal)
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
        if length > 1_000_000: raise ValueError("request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if not self._local_request(): return self._json({"error": "localhost only"}, 403)
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            draft = self.server.draft
            open_cases, identified = split_research_cases(draft.portal, draft.identifications, draft.master)
            observations = draft.portal.get("observations", [])
            try: repo = repository_status()
            except GitWorkflowError: repo = {"branch": "取得できませんでした", "dirty": None, "gh_authenticated": False}
            knowledge = scan_knowledge_batches(origin_main_sha=repo.get("origin_main_sha"))
            state = {"csrf": self.server.csrf_token, "portal_source": self.server.portal_source,
                     "best_shots": draft.best_shots, "notices": [{**e, **notice_window(e)} for e in draft.notices["events"]],
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
        if "/" in relative or ".." in relative or relative not in {"index.html", "admin.css", "admin.js"}:
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
            if self.path == "/api/validate": result = draft.validate()
            elif self.path == "/api/pr": result = create_pull_request(draft.files(), draft.validate(), body.get("operation", "changes"))
            elif self.path == "/api/knowledge/decision": result = set_candidate_decision(body["batch_id"], body["candidate_id"], body["human_decision"], body.get("note", ""))
            elif self.path == "/api/knowledge/reset": result = reset_review_state(body["batch_id"])
            elif self.path == "/api/knowledge/preview": result = preview_promotion(body["batch_id"], origin_main_sha=repository_status().get("origin_main_sha"))
            elif self.path == "/api/knowledge/pr": result = create_knowledge_pull_request(body["batch_id"])
            elif self.path in actions: result = actions[self.path]() or {"ok": True}
            else: return self._json({"error": "not found"}, 404)
            return self._json(result)
        except Exception as error:
            return self._json({"error": str(error)}, 400)

    def log_message(self, fmt, *args):
        print(f"[{datetime.now(timezone.utc).isoformat()}] {self.client_address[0]} {fmt % args}")


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=DEFAULT_PORT); parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv); server = AdminServer((BIND_ADDRESS, args.port), Handler)
    url = f"http://{BIND_ADDRESS}:{args.port}/"; print(f"きのこブログ管理室: {url}")
    if not args.no_browser: webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__": main()
