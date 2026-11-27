"""Loopback-only trial of the integrated admin using an independent review store."""
import argparse
from pathlib import Path
import sys
from tempfile import mkdtemp
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from admin.comment_trial import read_fixture
from admin.guide_review import GuideReview
from admin.server import AdminServer, Handler


class TrialHandler(Handler):
    def do_GET(self):
        if self.path == "/api/state" and self._local_request():
            # The integrated page only needs the initial navigation shell. Avoid
            # Git, GitHub, Cloudflare and other management actions in the trial.
            return self._json({"csrf": self.server.csrf_token,
                               "trial": {"pages": ["dashboard", "guide-review", "comments"]}})
        if self.path == "/api/comments/status" and self._local_request():
            return self._json({"configured": True, "trial": True, "message": "試験データを表示しています。本番のコメント操作は利用できません。"})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/comments/request":
            return super().do_POST()
        import secrets
        if not self._local_request() or not secrets.compare_digest(
                self.headers.get("X-CSRF-Token", ""), self.server.csrf_token):
            return self._json({"error": "localhost CSRF validation failed"}, 403)
        try:
            request = self._body()
            action, values = request["action"], request["values"]
            if action not in {"cases", "comments", "history"}:
                return self._json({"message": "試験データは閲覧専用です。"}, 403)
            if values.get("q") == "接続失敗":
                return self._json({"message": "試験用の接続失敗です。"}, 503)
            return self._json(read_fixture(self.server.guide_review.portal_loader(), action, values))
        except (OSError, ValueError, TypeError, KeyError, StopIteration):
            return self._json({"message": "試験データを取得できません。"}, 503)


class TrialServer(AdminServer):
    def __init__(self, port, state_root, review=None):
        from http.server import ThreadingHTTPServer
        import secrets
        ThreadingHTTPServer.__init__(self, ("127.0.0.1", port), TrialHandler)
        self.guide_trial = True
        self.csrf_token = secrets.token_urlsafe(32)
        self.guide_review = review or GuideReview(root=state_root, trial=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--fresh", action="store_true", help="Use a new, isolated trial profile")
    args = parser.parse_args()
    root = (Path(mkdtemp(prefix="KinokoGuideReviewTrialFresh-", dir=Path.home())) if args.fresh
            else Path.home() / "KinokoGuideReviewTrial")
    with TrialServer(args.port, root) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print("管理室の実機試験 " + url, flush=True)
        print("試験記録の保存先 " + str(root), flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        server.serve_forever()


if __name__ == "__main__":
    main()
