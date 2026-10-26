"""Serve only viewer code and the published ground truth on 127.0.0.1."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from games import GAME, GAMES, source_frames

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PUBLIC = ROOT / "evaluation" / "gt" / f"{GAME}_possession_gt_public.csv"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/styles.css": ("styles.css", "text/css; charset=utf-8"),
          **{f"/{name}.mjs": (f"{name}.mjs", "text/javascript; charset=utf-8")
             for name in ("app", "core", "worker")}}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "worker-src 'self'; media-src blob:; img-src 'self'; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'none'")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlsplit(self.path).path
        try:
            if route == "/config.json":
                meta = json.loads(PUBLIC.with_name(PUBLIC.stem + "_meta.json").read_text(encoding="utf-8"))
                window = meta["public_window"]
                body = json.dumps({"frames": source_frames(), "fps": GAMES[GAME]["fps"],
                    "publicWindow": [window["first_video_frame"], window["last_video_frame"]]}).encode()
                content_type = "application/json"
            elif route == "/public-ground-truth.csv":
                body, content_type = PUBLIC.read_bytes(), "text/csv; charset=utf-8"
            elif route in STATIC:
                name, content_type = STATIC[route]
                body = (WEB / name).read_bytes()
            else:
                self.send_error(404)
                return
        except OSError:
            self.send_error(500, "Viewer resource unavailable")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Local: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
