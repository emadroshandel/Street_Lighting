#!/usr/bin/env python3
# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
"""
Street Lighting — local application server.

A small HTTP server from the Python standard library serves the browser
interface from ./web and a JSON API backed by the `streetlight` package.

    python server.py                 # start and open a browser
    python server.py --port 8810     # choose the port
    python server.py --no-browser    # headless
    python server.py --lan           # also reachable from other computers on the network
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# Only these parts of the folder are served. Everything else (References/, _work/, saved projects,
# .git) stays private even with --lan.
PUBLIC_DIRS = ("web", "examples", "docs", "streetlight")
PUBLIC_FILES = ("index.html",)
MAX_BODY = 64 * 1024 * 1024          # largest accepted request (a big DXF or photometric file)
LAN = False                          # set by --lan

from streetlight import APP_NAME, APP_VERSION  # noqa: E402
from streetlight.api import ROUTES, clean       # noqa: E402

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")


class Handler(BaseHTTPRequestHandler):
    server_version = "StreetLighting/%s" % APP_VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.environ.get("STREETLIGHT_VERBOSE"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code, obj):
        self._send(code, json.dumps(clean(obj), allow_nan=False).encode("utf-8"))

    def _host_ok(self):
        """Refuse requests whose Host is not this computer (DNS-rebinding protection), unless --lan."""
        if LAN:
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def _origin_ok(self):
        """A POST must come from this application's own page, not from another web site."""
        origin = self.headers.get("Origin")
        if not origin:
            return True                      # same-origin fetch from older browsers, or curl
        o = urlparse(origin)
        return o.netloc == self.headers.get("Host", "")

    @staticmethod
    def _public_path(path):
        """Absolute file path for a URL path inside the public folders, or None."""
        rel = os.path.normpath(path.lstrip("/"))
        if rel.startswith("..") or os.path.isabs(rel):
            return None
        top = rel.split(os.sep, 1)[0]
        if not (top in PUBLIC_DIRS or rel in PUBLIC_FILES):
            return None
        full = os.path.realpath(os.path.join(BASE, rel))
        root = os.path.realpath(BASE)
        if os.path.commonpath([full, root]) != root or not os.path.isfile(full):
            return None
        if "__pycache__" in full.split(os.sep):
            return None
        return full

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            return self._json(200, dict(ok=True, app=APP_NAME, version=APP_VERSION, server=True))
        if path in ("/", "", "/web"):
            self.send_response(302)
            self.send_header("Location", "/web/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/web/":
            path = "/web/index.html"
        full = self._public_path(path)
        if full is None:
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            data = f.read()
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, data, ctype)

    def do_POST(self):
        path = urlparse(self.path).path
        fn = ROUTES.get(path)
        if fn is None:
            return self._json(404, dict(error="Unknown endpoint " + path))
        if not self._host_ok() or not self._origin_ok():
            return self._json(403, dict(error="Requests are accepted only from this application."))
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json(400, dict(error="Bad Content-Length."))
        if n < 0 or n > MAX_BODY:
            self.close_connection = True
            return self._json(413, dict(error="The request is larger than %d MB." % (MAX_BODY // 2 ** 20)))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json(400, dict(error="The request was not valid JSON."))
        if not isinstance(payload, dict):
            return self._json(400, dict(error="The request must be a JSON object."))
        try:
            return self._json(200, fn(payload))
        except (ValueError, KeyError, ZeroDivisionError, TypeError, IndexError) as exc:
            msg = str(exc) if isinstance(exc, ValueError) else _friendly(exc)
            return self._json(400, dict(error=msg))
        except Exception as exc:                                   # pragma: no cover
            traceback.print_exc()
            return self._json(500, dict(error="%s: %s" % (type(exc).__name__, exc)))


def _friendly(exc):
    """A message a user can act on for errors that come from incomplete or inconsistent input."""
    if isinstance(exc, KeyError):
        return "A required value is missing or unknown: %s." % exc
    if isinstance(exc, ZeroDivisionError):
        return "A value that must be greater than zero is zero (check sizes, voltages, radii and heights)."
    if isinstance(exc, TypeError):
        return "A value is empty or has the wrong type; fill in every field and try again."
    return "The input could not be read (%s: %s)." % (type(exc).__name__, exc)


def free_port(preferred=8810):
    for port in [preferred] + list(range(preferred + 1, preferred + 50)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def main():
    ap = argparse.ArgumentParser(description=APP_NAME + " local server")
    ap.add_argument("--port", type=int, default=8810)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--lan", action="store_true", help="listen on all interfaces")
    a = ap.parse_args()
    global LAN
    LAN = a.lan
    port = free_port(a.port)
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = "http://127.0.0.1:%d/" % port
    print("%s %s — %s  (Ctrl+C to stop)" % (APP_NAME, APP_VERSION, url))
    if a.lan:
        try:
            ip = socket.gethostbyname(socket.gethostname())
            print("On the local network: http://%s:%d/" % (ip, port))
        except OSError:
            pass
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
