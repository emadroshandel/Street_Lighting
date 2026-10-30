#!/usr/bin/env python3
# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""
Street Lighting — desktop mode.

Starts the local server in a background thread and shows the interface in a
native window using pywebview.  Without pywebview the default browser is
opened instead, so this entry point always works:

    python desktop.py
    pip install pywebview      # optional, for the native window
"""
from __future__ import annotations

import base64
import os
import sys
import threading
import time

import server


class DesktopApi:
    """Called from the page (window.pywebview.api): saving files from the desktop window.

    pywebview windows do not perform browser downloads, so Save, Picture, DXF and CSV
    hand the file content to Python, which asks where to put it with a native dialog.
    """

    def __init__(self):
        self._window = None   # private: pywebview does not expose names starting with _

    def save_file(self, name, data, is_data_url=False):
        import webview  # type: ignore
        name = os.path.basename(str(name or "file")) or "file"
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None)
        if kind is None:
            kind = webview.SAVE_DIALOG
        try:
            res = self._window.create_file_dialog(kind, save_filename=name)
        except Exception as exc:  # noqa: BLE001 - report to the page
            return dict(saved=False, error=str(exc))
        if not res:
            return dict(saved=False)                # cancelled
        path = res if isinstance(res, str) else res[0]
        try:
            if is_data_url:
                payload = str(data).split(",", 1)[1]
                with open(path, "wb") as f:
                    f.write(base64.b64decode(payload))
            else:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(str(data))
        except Exception as exc:  # noqa: BLE001
            return dict(saved=False, error=str(exc))
        return dict(saved=True, path=path)


def main():
    port = server.free_port(8810)
    holder = {}

    def run():
        from http.server import ThreadingHTTPServer
        httpd = ThreadingHTTPServer(("127.0.0.1", port), server.Handler)
        holder["s"] = httpd
        httpd.serve_forever()

    threading.Thread(target=run, daemon=True).start()
    time.sleep(0.6)
    url = "http://127.0.0.1:%d/" % port
    print("%s %s — %s" % (server.APP_NAME, server.APP_VERSION, url))
    try:
        import webview  # type: ignore
    except ImportError:
        print("pywebview is not installed — opening the default browser instead.")
        print("For a native desktop window:  pip install pywebview")
        import webbrowser
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped.")
        return
    bridge = DesktopApi()
    bridge._window = webview.create_window("%s %s — road lighting design" % (server.APP_NAME, server.APP_VERSION),
                                          url, js_api=bridge, width=1560, height=980, min_size=(1100, 720),
                                          confirm_close=False)
    try:
        webview.start()
    finally:
        s = holder.get("s")
        if s:
            s.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()
