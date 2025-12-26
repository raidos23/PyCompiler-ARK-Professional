#!/usr/bin/env python3
"""
WebPageLauncher: simple local server to host WebPage/main.html.
- Serves static files from the WebPage directory
- Also serves parent logo assets under /logo
- Opens the default browser on startup

Usage:
  python WebPageLauncher.py [--host 127.0.0.1] [--port 8765] [--no-browser]
"""
from __future__ import annotations
import argparse
import http.server
import json
import mimetypes
import os
import socketserver
import sys
import threading
import time
import webbrowser
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(ROOT, 'main.html')
LOGO_DIR = os.path.abspath(os.path.join(ROOT, '..', 'logo'))

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("[WebPage] " + (fmt % args) + "\n")

    def end_headers(self):
        # Basic CORS for local testing
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    # Serve index for root path + mount /logo from parent directory
    def do_GET(self):
        if self.path.startswith('/logo/'):
            # Map /logo/* to LOGO_DIR
            rel = self.path[len('/logo/'):]
            fs_path = os.path.join(LOGO_DIR, rel)
            if os.path.isfile(fs_path):
                try:
                    with open(fs_path, 'rb') as f:
                        data = f.read()
                    self.send_response(200)
                    ctype = mimetypes.guess_type(fs_path)[0] or 'application/octet-stream'
                    self.send_header('Content-Type', ctype)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    self.send_error(404, 'File not found')
                return
            else:
                self.send_error(404, 'File not found')
                return

        if self.path in ('/', '/index.html', '/main', '/index'):
            self.path = '/main.html'
        return super().do_GET()


def open_browser(host: str, port: int):
    url = f"http://{host}:{port}/main.html"
    # Wait a bit for the server to start
    for _ in range(20):
        time.sleep(0.1)
    try:
        webbrowser.open(url)
    except Exception as e:
        sys.stderr.write(f"[WebPage] Could not open browser: {e}\n")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Local launcher for WebPage')
    p.add_argument('--host', default='127.0.0.1', help='Host to bind (default: 127.0.0.1)')
    p.add_argument('--port', type=int, default=8765, help='Port to bind (default: 8765)')
    p.add_argument('--no-browser', action='store_true', help='Do not auto-open the browser')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    os.chdir(ROOT)

    with socketserver.TCPServer((args.host, args.port), RequestHandler) as httpd:
        httpd.allow_reuse_address = True
        sys.stderr.write(f"[WebPage] Serving {ROOT} at http://{args.host}:{args.port}\n")

        if not args.no_browser:
            threading.Thread(target=open_browser, args=(args.host, args.port), daemon=True).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sys.stderr.write("\n[WebPage] Shutting down...\n")
        finally:
            httpd.server_close()


if __name__ == '__main__':
    main()
