#!/usr/bin/env python3
"""
Serve the static site from this folder (so /map.html and /data/... work).

Run (from anywhere):
  python3 web/serve.py

Then open in your browser:
  http://127.0.0.1:8765/map.html
  http://127.0.0.1:8765/index.html

If you see ERR_EMPTY_RESPONSE, the server is not running — start this script and
keep the terminal open. Use another port: PORT=9000 python3 web/serve.py
"""
from __future__ import annotations

import os
import sys

WEB_ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    port = int(os.environ.get("PORT", "8765"))
    os.chdir(WEB_ROOT)

    try:
        from http.server import HTTPServer, SimpleHTTPRequestHandler
    except ImportError:
        print("Python 3 is required.", file=sys.stderr)
        sys.exit(1)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            pass  # optional: comment out to see request logs

    server = HTTPServer(("127.0.0.1", port), QuietHandler)
    print("─" * 56)
    print("  Pesticide exposure — local web server")
    print("─" * 56)
    print(f"  Serving:  {WEB_ROOT}")
    print(f"  URL:      http://127.0.0.1:{port}/map.html")
    print(f"  About:    http://127.0.0.1:{port}/index.html")
    print("─" * 56)
    print("  Keep this terminal open. Press Ctrl+C to stop.")
    print("─" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
