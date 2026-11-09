"""Servidor de descarga para el celular (puerto 8080). Solo expone /s/<id>, /strip, /photo, /dl: nada de la cabina."""
from __future__ import annotations
import logging, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config as C

log = logging.getLogger("fotobut.share")
ID = r"[0-9]{4}-[0-9a-f]{8}"

PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tu tira · El Fotobut</title>
<style>
@font-face{font-family:Poppins;font-weight:700;src:url(/f/Poppins-Bold.ttf)}
@font-face{font-family:Poppins;font-weight:500;src:url(/f/Poppins-Medium.ttf)}
@font-face{font-family:Lora;font-style:italic;src:url(/f/Lora-Italic-Variable.ttf)}
:root{--deep:#0b2e22;--green:#15503b;--mint:#8EE3B0;--cream:#FFF6E3;--orange:#FF6A3D}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 0,#1d6b4f,#0b2e22 60%);min-height:100vh;color:var(--cream);
font-family:Poppins,system-ui,sans-serif;text-align:center;padding:24px 18px 40px}
h1{font-size:30px;margin:6px 0 2px}.sub{font-family:Lora,serif;font-style:italic;color:var(--mint);font-size:19px;margin:0 0 20px}
.strip{display:block;width:min(78vw,320px);margin:0 auto 22px;border-radius:10px;box-shadow:0 14px 40px rgba(0,0,0,.55);transform:rotate(-2deg)}
.btn{display:block;max-width:360px;margin:0 auto 12px;padding:16px;border-radius:50px;background:var(--cream);color:var(--deep);font-weight:700;
font-size:19px;text-decoration:none;box-shadow:0 5px 0 var(--orange)}
h2{font-size:20px;margin:34px 0 12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;max-width:560px;margin:0 auto}
.grid a{color:var(--cream);text-decoration:none;font-size:14px;font-weight:500}.grid img{width:100%;border-radius:8px;display:block;margin-bottom:6px;border:3px solid var(--cream)}
small{display:block;margin-top:30px;opacity:.6;font-size:12px;letter-spacing:.08em}
</style></head><body>
<h1>¡Tu tira está lista!</h1><p class="sub">Mantén presionada la imagen o usa el botón para guardarla</p>
<img class="strip" src="/strip/__ID__.jpg" alt="Tu tira de fotos">
<a class="btn" href="/dl/strip/__ID__.jpg" download>Descargar tira</a>
__PHOTOS__
<small>EL FOTOBUT · DIVASDOWN · FSE UNAM · SESIÓN __ID__</small></body></html>"""

NOTFOUND = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui;background:#0b2e22;color:#FFF6E3;text-align:center;padding:60px 20px"><h2>No encontramos esa tira</h2>
<p>Escanea de nuevo el código QR de la pantalla de la cabina.</p></body>"""


def _strip_path(sid: str) -> Path | None:
    for p in (C.TMP_DIR / sid / "tira.jpg", C.FINAL_DIR / f"{sid}.jpg"):
        if p.is_file():
            return p
    return None


def last_session() -> str | None:
    """Ultima tira hecha: se descubre en el disco (qr_httpd es un proceso aparte y no comparte memoria con vision_gui)."""
    try:
        best = max((d for d in C.TMP_DIR.iterdir() if (d / "tira.jpg").is_file() and re.fullmatch(ID, d.name)),
                   key=lambda d: (d / "tira.jpg").stat().st_mtime)
        return best.name
    except (ValueError, OSError):
        return None


def make_handler():
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype: str, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path: Path | None, ctype="image/jpeg", dl_name: str | None = None):
            if not path or not path.is_file():
                return self._send(404, NOTFOUND.encode(), "text/html; charset=utf-8")
            extra = {"Content-Disposition": f'attachment; filename="{dl_name}"'} if dl_name else None
            self._send(200, path.read_bytes(), ctype, extra)

        def do_GET(self):
            p = self.path.split("?")[0]
            try:
                if p in ("/", "/index.html"):                        # sin id: la ultima tira hecha
                    sid = last_session()
                    if not sid:
                        return self._send(404, NOTFOUND.encode(), "text/html; charset=utf-8")
                    return self._send(302, b"", "text/plain", {"Location": f"/s/{sid}"})
                m = re.fullmatch(rf"/s/({ID})", p)
                if m:
                    sid = m.group(1)
                    if not _strip_path(sid):
                        return self._send(404, NOTFOUND.encode(), "text/html; charset=utf-8")
                    photos = [i for i in (1, 2, 3) if (C.TMP_DIR / sid / f"foto{i}_f.jpg").is_file()]
                    extra = ""
                    if photos:
                        cells = "".join(f'<a href="/dl/photo/{sid}/{i}.jpg" download><img src="/photo/{sid}/{i}.jpg" alt="Foto {i}">Descargar foto {i}</a>' for i in photos)
                        extra = f'<h2>Fotos sueltas</h2><div class="grid">{cells}</div>'
                    return self._send(200, PAGE.replace("__ID__", sid).replace("__PHOTOS__", extra).encode(), "text/html; charset=utf-8")
                m = re.fullmatch(rf"/(strip|dl/strip)/({ID})\.jpg", p)
                if m:
                    dl = f"fotobut-{m.group(2)}.jpg" if m.group(1) == "dl/strip" else None
                    return self._file(_strip_path(m.group(2)), dl_name=dl)
                m = re.fullmatch(rf"/(photo|dl/photo)/({ID})/([1-3])\.jpg", p)
                if m:
                    dl = f"fotobut-{m.group(2)}-foto{m.group(3)}.jpg" if m.group(1) == "dl/photo" else None
                    return self._file(C.TMP_DIR / m.group(2) / f"foto{m.group(3)}_f.jpg", dl_name=dl)
                m = re.fullmatch(r"/f/([A-Za-z0-9\-]+\.ttf)", p)
                if m:
                    return self._file(C.WEB_DIR / "fonts" / m.group(1), "font/ttf")
                self._send(404, NOTFOUND.encode(), "text/html; charset=utf-8")
            except (BrokenPipeError, ConnectionResetError):
                pass

    return H


def serve_share(host=C.SHARE_HOST, port=C.SHARE_PORT):
    httpd = ThreadingHTTPServer((host, port), make_handler())
    httpd.daemon_threads = True
    log.info("Descargas en http://%s:%d", host, port)
    return httpd
