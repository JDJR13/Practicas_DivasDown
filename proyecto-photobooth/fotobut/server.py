"""Servidor HTTP de la pantalla (solo libreria estandar): pagina, eventos SSE, MJPEG, fotos y simulador."""
from __future__ import annotations
import json, logging, mimetypes, re, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config as C

log = logging.getLogger("fotobut.server")


def make_handler(machine, hal, camera):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):                           # silencia el log por peticion
            pass

        # ---- utilidades
        def _send(self, code, body: bytes, ctype="application/octet-stream", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path: Path):
            if not path.is_file():
                return self._send(404, b"no encontrado", "text/plain")
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self._send(200, path.read_bytes(), ctype)

        # ---- rutas
        def do_GET(self):
            p = self.path.split("?")[0]
            try:
                if p in ("/", "/index.html"):
                    return self._file(C.WEB_DIR / "index.html")
                if p.startswith("/static/"):
                    rel = p[len("/static/"):]
                    f = (C.WEB_DIR / rel).resolve()
                    if C.WEB_DIR.resolve() not in f.parents:
                        return self._send(403, b"prohibido", "text/plain")
                    return self._file(f)
                if p == "/api/state":
                    return self._send(200, json.dumps(machine.snapshot()).encode(), "application/json")
                if p == "/api/ipc":          # latencia ida y vuelta del socket AF_UNIX medida por vision_gui (clase 11)
                    r = sorted(getattr(hal, "rtt_us", []))
                    out = {"n": len(r), "link": getattr(hal, "link", None)}
                    if r:
                        out.update(mediana_us=round(r[len(r) // 2], 1), p95_us=round(r[int(len(r) * .95)], 1), max_us=round(r[-1], 1))
                    return self._send(200, json.dumps(out).encode(), "application/json")
                if p == "/oled.png":
                    return self._file(C.TMP_DIR / "oled.png")
                if p == "/events":
                    return self._sse()
                if p == "/preview.mjpg":
                    return self._mjpeg()
                m = re.fullmatch(r"/photo/([0-9a-f-]+)/(foto[1-9]\.jpg)", p)
                if m:
                    return self._file(C.TMP_DIR / m.group(1) / m.group(2))
                m = re.fullmatch(r"/strip/([0-9a-f-]+)\.jpg", p)
                if m:
                    return self._file(C.TMP_DIR / m.group(1) / "tira.jpg")
                self._send(404, b"no encontrado", "text/plain")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            if self.path == "/api/sim" and getattr(hal, "is_sim", False):
                n = int(self.headers.get("Content-Length", 0))
                try:
                    d = json.loads(self.rfile.read(n) or b"{}")
                    hal.sim_set(button=bool(d.get("button")), pot=d.get("pot"),
                                distance=d["distance"] if "distance" in d else "keep", reset=bool(d.get("reset")))
                    return self._send(200, b"{}", "application/json")
                except Exception as e:                       # noqa: BLE001
                    return self._send(400, str(e).encode(), "text/plain")
            self._send(404, b"no encontrado", "text/plain")

        # ---- Server-Sent Events
        def _sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            ver = -1
            try:
                while True:
                    if machine.wait_change(ver, 1.0) or ver == -1:
                        snap = machine.snapshot()
                        ver = snap["v"]
                        self.wfile.write(b"data: " + json.dumps(snap).encode() + b"\n\n")
                    else:
                        self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        # ---- MJPEG de la camara
        def _mjpeg(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    t0 = time.monotonic()
                    jpg = camera.get_jpeg()
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                    self.wfile.write(jpg + b"\r\n")
                    self.wfile.flush()
                    time.sleep(max(0.0, 1 / 15 - (time.monotonic() - t0)))
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    return H


def serve(machine, hal, camera, host=C.UI_HOST, port=C.UI_PORT):
    httpd = ThreadingHTTPServer((host, port), make_handler(machine, hal, camera))
    httpd.daemon_threads = True
    log.info("Interfaz en http://%s:%d", host, port)
    return httpd
