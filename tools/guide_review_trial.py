"""Loopback-only trial of the integrated admin using an independent review store."""
import argparse
from pathlib import Path
import sys
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from admin.guide_review import GuideReview
from admin.server import AdminServer, Handler


class TrialHandler(Handler):
    def do_GET(self):
        if self.path == "/api/state" and self._local_request():
            # The integrated page only needs the initial navigation shell. Avoid
            # Git, GitHub, Cloudflare and other management actions in the trial.
            return self._json({"csrf": self.server.csrf_token,
                               "trial": {"pages": ["dashboard", "guide-review"]}})
        return super().do_GET()


class TrialServer(AdminServer):
    def __init__(self, port, state_root, review=None):
        from http.server import ThreadingHTTPServer
        import secrets
        ThreadingHTTPServer.__init__(self, ("127.0.0.1", port), TrialHandler)
        self.guide_trial = True
        self.csrf_token = secrets.token_urlsafe(32)
        self.guide_review = review or GuideReview(root=state_root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with TrialServer(args.port, Path.home() / "KinokoGuideReviewTrial") as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print("図鑑確認の実機試験 " + url, flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        server.serve_forever()


if __name__ == "__main__":
    main()
