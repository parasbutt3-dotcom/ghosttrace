"""Tiny ActivityWatch-compatible mock server (stdlib only) for E2E smoke tests."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

BUCKET = "aw-watcher-window_e2e"

BUCKETS = {
    BUCKET: {
        "id": BUCKET,
        "type": "currentwindow",
        "client": "ghosttrace-e2e",
        "hostname": "e2e-host",
        "created": "2026-01-01T00:00:00+00:00",
        "last_updated": "2026-01-01T00:00:00+00:00",
    }
}

EVENTS = {
    BUCKET: [
        {
            "id": 1,
            "timestamp": "2026-01-01T12:00:00+00:00",
            "duration": 5.0,
            "data": {"app": "MockApp", "title": "Mock Window Title"},
        }
    ]
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/api/0/buckets":
            self._respond(BUCKETS)
            return
        prefix = "/api/0/buckets/"
        suffix = "/events"
        if path.startswith(prefix) and path.endswith(suffix):
            bid = path[len(prefix):-len(suffix)] if len(suffix) else path[len(prefix):]
            self._respond(EVENTS.get(bid, []))
            return
        self.send_response(404)
        self.end_headers()

    def _respond(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        return


def main():
    port = int(os.environ.get("PORT", "5600"))
    httpd = HTTPServer(("127.0.0.1", port), Handler)
    print(f"mock activitywatch listening on {port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()