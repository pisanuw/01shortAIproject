#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CatalogHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        # Keep standard logs concise and explicit.
        super().log_message(fmt, *args)

    def end_headers(self) -> None:
        # Local development should always reflect latest file edits.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local static development server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "4173")),
        help="Port to serve on (default: 4173 or PORT env var)",
    )
    args = parser.parse_args()

    httpd = ThreadingHTTPServer(("", args.port), CatalogHandler)
    print(f"Serving on http://localhost:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
