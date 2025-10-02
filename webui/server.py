import json
import os
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Optional, List

"""
Web UI server for the gude uploader.

Enhancements:
- Robust asset discovery for both source and PyInstaller one-file builds.
- Optional auto-open of the default browser.
"""

# Ensure repository root is on sys.path so we can import upload.py when running this file directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upload import run_processing_from_options, DeviceResult


class State:
    running: bool = False
    results: List[DeviceResult] = []

def _base_dir() -> Path:
    """Return directory containing index.html/assets, both in src and frozen builds."""
    if getattr(sys, 'frozen', False):
        # In PyInstaller onefile, data files are extracted under _MEIPASS; we keep them under 'webui'
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)).joinpath('webui')
        if base.is_dir():
            return base
        # Fallback to _MEIPASS root
        return Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    return Path(__file__).parent


# Assets/index resolved from base dir
BASE_DIR = _base_dir()
ASSETS_DIR = str(BASE_DIR.joinpath('assets'))


def _json_default(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return str(obj)


def _run_gbl_query_async():
    try:
        State.running = True
        State.results = run_processing_from_options(
            gbl=True,
            status=True,
            onlineupdate=True,
            upload_ini="None",
            version_ini="None"
        )
    finally:
        State.running = False


def _run_update_selected_async(hosts: list[str]):
    try:
        State.running = True
        # Build devices mapping like: { 'hosts': { 'ip1': 'host:port', 'ip2': 'host:port', ... } }
        devices = {'hosts': {}}
        for idx, h in enumerate(hosts, start=1):
            devices['hosts'][f'ip{idx}'] = str(h)

        State.results = run_processing_from_options(
            upload_ini="no_upload.ini",
            version_ini="no_version.ini",
            onlineupdate=True,
            devices=devices,
            forcefw=True,
            status=False,
            gbl=False,
            device_concurrency=2
        )
    finally:
        State.running = False


class Handler(BaseHTTPRequestHandler):
    def _send(self, code=200, headers=None):
        self.send_response(code)
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/' or path == '/index.html':
            return self._serve_index()
        if path.startswith('/assets/'):
            return self._serve_asset(path[len('/assets/'):])
        if path == '/api/devices':
            return self._api_devices()
        if path == '/api/run':
            return self._api_run()
        self._send(404, {"Content-Type": "text/plain; charset=utf-8"})
        self.wfile.write(b'Not Found')

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/api/update':
            return self._api_update()
        self._send(404, {"Content-Type": "text/plain; charset=utf-8"})
        self.wfile.write(b'Not Found')

    def _serve_index(self):
        index_path = str(BASE_DIR.joinpath('index.html'))
        try:
            with open(index_path, 'rb') as f:
                data = f.read()
            self._send(200, {"Content-Type": "text/html; charset=utf-8"})
            self.wfile.write(data)
        except FileNotFoundError:
            self._send(500, {"Content-Type": "text/plain; charset=utf-8"})
            self.wfile.write(b'index.html not found')

    def _serve_asset(self, name: str):
        if not ASSETS_DIR:
            self._send(404, {"Content-Type": "text/plain; charset=utf-8"})
            self.wfile.write(b'Assets directory not found')
            return
        safe_name = os.path.basename(name)
        path = os.path.join(ASSETS_DIR, safe_name)
        # Allow serving of a project-root logo if requested
        if not os.path.isfile(path):
            if safe_name == 'gude_only-logo.svg':
                alt = os.path.join(str(ROOT), 'gude_only-logo.svg')
                if os.path.isfile(alt):
                    path = alt
                else:
                    self._send(404, {"Content-Type": "text/plain; charset=utf-8"})
                    self.wfile.write(b'Asset not found')
                    return
            else:
                self._send(404, {"Content-Type": "text/plain; charset=utf-8"})
                self.wfile.write(b'Asset not found')
                return
        ext = os.path.splitext(path)[1].lower()
        ctype = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.svg': 'image/svg+xml',
        }.get(ext, 'application/octet-stream')
        with open(path, 'rb') as f:
            data = f.read()
        self._send(200, {"Content-Type": f"{ctype}; charset=utf-8" if ctype.startswith(('text/', 'application/javascript')) else ctype})
        self.wfile.write(data)

    def _api_devices(self):
        payload = {
            'running': State.running,
            'results': [asdict(r) for r in State.results],
        }
        data = json.dumps(payload, default=_json_default).encode('utf-8')
        self._send(200, {"Content-Type": "application/json; charset=utf-8"})
        self.wfile.write(data)

    def _api_run(self):
        if State.running:
            # Already running; report accepted
            payload = {'running': True}
            data = json.dumps(payload).encode('utf-8')
            self._send(200, {"Content-Type": "application/json; charset=utf-8"})
            self.wfile.write(data)
            return
        t = threading.Thread(target=_run_gbl_query_async, daemon=True)
        t.start()
        payload = {'running': True}
        data = json.dumps(payload).encode('utf-8')
        self._send(202, {"Content-Type": "application/json; charset=utf-8"})
        self.wfile.write(data)

    def _api_update(self):
        if State.running:
            payload = {'running': True}
            data = json.dumps(payload).encode('utf-8')
            self._send(200, {"Content-Type": "application/json; charset=utf-8"})
            self.wfile.write(data)
            return
        # Read JSON body
        length = int(self.headers.get('Content-Length', '0') or '0')
        raw = self.rfile.read(length) if length > 0 else b'{}'
        try:
            body = json.loads(raw.decode('utf-8')) if raw else {}
        except Exception:
            body = {}
        hosts: list[str] = []
        # Accept either {"hosts": [..]} or a nested devices mapping
        if isinstance(body.get('hosts'), list):
            hosts = [str(x) for x in body['hosts']]
        elif isinstance(body.get('devices'), dict):
            dvc = body['devices'].get('hosts') or {}
            if isinstance(dvc, dict):
                # devices.hosts is mapping ip1->"host:port"
                hosts = [str(v) for _, v in sorted(dvc.items())]
            elif isinstance(dvc, list):
                hosts = [str(x) for x in dvc]

        t = threading.Thread(target=_run_update_selected_async, args=(hosts,), daemon=True)
        t.start()
        payload = {'running': True}
        data = json.dumps(payload).encode('utf-8')
        self._send(202, {"Content-Type": "application/json; charset=utf-8"})
        self.wfile.write(data)


def serve(host: str = '0.0.0.0', port: int = 8000, *, open_browser: bool = False):
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://localhost:{port}"
    print(f"Web UI available at http://{host}:{port}")
    # Open the default browser if requested
    if open_browser:
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            # Non-fatal: continue serving even if browser could not be opened
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == '__main__':
    serve(open_browser=True)
