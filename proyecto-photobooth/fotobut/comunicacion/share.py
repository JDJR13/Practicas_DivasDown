"""Servidor de descarga para el celular (puerto 8080). Es la UNICA parte de la cabina expuesta a la red, asi que se
trata como superficie de ataque: solo sirve /s/<id>, /strip, /photo, /dl y las fuentes; todo lo demas es 404.

Defensas (ver docs/SEGURIDAD.md):
  - rutas por lista blanca con expresiones regulares completas: no hay forma de pedir un archivo arbitrario
  - el id de sesion lleva 64 bits al azar: no se puede adivinar la tira de otra persona; ademas caduca (SHARE_TTL_S)
  - limite de peticiones y de errores 404 por IP (frena la enumeracion de ids y los escaneres)
  - limite de conexiones simultaneas (global y por IP) y tiempo maximo por conexion (frena slowloris)
  - solo GET y HEAD; cabeceras de seguridad (CSP, nosniff, no-frame); no revela versiones
"""
from __future__ import annotations
import logging, re, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fotobut.servicios import config as C

log = logging.getLogger("fotobut.share")
ID = r"[0-9]{4,6}-[0-9a-f]{16}"
MAX_PATH = 96                    # la ruta valida mas larga mide ~45 caracteres
MAX_FILE = 12 * 1024 * 1024      # nunca se sirve algo mayor (una tira pesa < 1 MB)
MAX_CONN, MAX_CONN_IP = 48, 8    # conexiones simultaneas: total y por IP
RATE_N, RATE_S = 60, 10          # peticiones por IP por ventana (una pagina completa son ~8)
MISS_N, MISS_S, BAN_S = 15, 60, 120   # 15 errores 404 en 60 s -> esa IP queda bloqueada 120 s
LOCAL = ("127.0.0.1", "::1")

SEC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; font-src 'self'; "
                               "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "Cache-Control": "private, no-store",
}

PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tu tira · El Fotobut</title>
<style>
@font-face{font-family:Poppins;font-weight:700;src:url(/f/Poppins-Bold.ttf)}
@font-face{font-family:Poppins;font-weight:500;src:url(/f/Poppins-Medium.ttf)}
@font-face{font-family:Lora;font-style:italic;src:url(/f/Lora-Italic-Variable.ttf)}
:root{--deep:#0C1320;--green:#1B2A44;--mint:#E2B659;--cream:#F7EEDC;--orange:#C8744A}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 0,#22324F,#0C1320 60%);min-height:100vh;color:var(--cream);
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
<small>EL FOTOBUT · DIVASDOWN · FSE UNAM · TU ENLACE CADUCA EN UNAS HORAS</small></body></html>"""

_MSG = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui;background:#0C1320;color:#F7EEDC;text-align:center;padding:60px 20px"><h2>__T__</h2>
<p>__P__</p></body>"""
NOTFOUND = _MSG.replace("__T__", "No encontramos esa tira").replace("__P__", "Escanea de nuevo el código QR de la pantalla de la cabina.")
HOME = _MSG.replace("__T__", "El Fotobut").replace("__P__", "Para ver tu tira, escanea el código QR que aparece en la pantalla de la cabina.")
BUSY = _MSG.replace("__T__", "Demasiadas peticiones").replace("__P__", "Espera un momento y vuelve a intentarlo.")


class Limites:
    """Contadores por IP protegidos por un candado. Memoria acotada: nunca guarda mas de MAX_IPS direcciones."""
    MAX_IPS = 256

    def __init__(self, clock=time.monotonic):
        self.clock, self.lock = clock, threading.Lock()
        self.req: dict[str, list[float]] = {}            # ip -> [inicio de ventana, cuenta]
        self.miss: dict[str, list[float]] = {}
        self.ban: dict[str, float] = {}                  # ip -> hasta cuando
        self.conn: dict[str, int] = {}
        self.total = 0

    def _poda(self, d: dict) -> None:
        if len(d) > self.MAX_IPS:
            for k in list(d)[: len(d) // 2]:             # los diccionarios conservan el orden: se van los mas viejos
                del d[k]

    def permitir(self, ip: str) -> bool:
        if ip in LOCAL:
            return True
        now = self.clock()
        with self.lock:
            if self.ban.get(ip, 0) > now:
                return False
            self.ban.pop(ip, None)
            w = self.req.get(ip)
            if not w or now - w[0] > RATE_S:
                self.req[ip] = [now, 1]
                self._poda(self.req)
                return True
            w[1] += 1
            return w[1] <= RATE_N

    def fallo(self, ip: str) -> None:
        """Anota un 404. Muchos seguidos = alguien probando ids o rutas: se bloquea la IP un rato."""
        if ip in LOCAL:
            return
        now = self.clock()
        with self.lock:
            w = self.miss.get(ip)
            if not w or now - w[0] > MISS_S:
                self.miss[ip] = [now, 1]
                self._poda(self.miss)
                return
            w[1] += 1
            if w[1] >= MISS_N:
                self.ban[ip] = now + BAN_S
                self._poda(self.ban)
                del self.miss[ip]
                log.warning("SEGURIDAD: %s bloqueada %d s por %d peticiones invalidas (posible escaneo de ids)", ip, BAN_S, MISS_N)

    def abrir(self, ip: str) -> bool:
        with self.lock:
            if self.total >= MAX_CONN or (ip not in LOCAL and self.conn.get(ip, 0) >= MAX_CONN_IP):
                return False
            self.total += 1
            self.conn[ip] = self.conn.get(ip, 0) + 1
            return True

    def cerrar(self, ip: str) -> None:
        with self.lock:
            self.total = max(0, self.total - 1)
            n = self.conn.get(ip, 1) - 1
            if n <= 0:
                self.conn.pop(ip, None)
            else:
                self.conn[ip] = n


def _dentro(path: Path, base: Path) -> bool:
    """El archivo real (sin enlaces simbolicos) esta dentro de la carpeta permitida."""
    try:
        return base.resolve() in path.resolve().parents
    except OSError:
        return False


def _vigente(p: Path) -> bool:
    try:
        return time.time() - p.stat().st_mtime < C.SHARE_TTL_S
    except OSError:
        return False


def _strip_path(sid: str) -> tuple[Path, Path] | None:
    """(archivo de la tira, carpeta que lo contiene) si existe y no ha caducado: primero la RAM, luego la microSD."""
    for p, base in ((C.TMP_DIR / sid / "tira.jpg", C.TMP_DIR), (C.FINAL_DIR / f"{sid}.jpg", C.FINAL_DIR)):
        if p.is_file() and _dentro(p, base) and _vigente(p):
            return p, base
    return None


def make_handler(lim: Limites):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version, sys_version = "Fotobut", ""       # no revelar "BaseHTTP/x Python/y"
        timeout = 8                                       # segundos por lectura: una conexion lenta no ocupa un hilo para siempre

        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype: str, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in SEC_HEADERS.items():
                self.send_header(k, v)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            if code >= 400:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def send_error(self, code, message=None, explain=None):   # errores del analizador HTTP: respuesta minima, sin eco
            try:
                self._send(code if isinstance(code, int) else 400, b"", "text/plain")
            except Exception:                            # noqa: BLE001
                pass

        def _404(self):
            lim.fallo(self.client_address[0])
            self._send(404, NOTFOUND.encode(), "text/html; charset=utf-8")

        def _file(self, path: Path | None, base: Path, ctype="image/jpeg", dl_name: str | None = None):
            try:
                if not path or not path.is_file() or not _dentro(path, base) or path.stat().st_size > MAX_FILE:
                    return self._404()
                data = path.read_bytes()
            except OSError:
                return self._404()
            extra = {"Content-Disposition": f'attachment; filename="{dl_name}"'} if dl_name else None
            self._send(200, data, ctype, extra)

        def _no(self):
            self._send(405, b"", "text/plain", {"Allow": "GET, HEAD"})

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_TRACE = do_CONNECT = _no

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            ip = self.client_address[0]
            try:
                if len(self.path) > MAX_PATH:
                    lim.fallo(ip)
                    return self._send(414, b"", "text/plain")
                if not lim.permitir(ip):
                    return self._send(429, BUSY.encode(), "text/html; charset=utf-8", {"Retry-After": "30"})
                p = self.path.split("?")[0]
                if p == "/salud":                                    # la usan el vigia y el monitor
                    return self._send(200, b"ok", "text/plain")
                if p in ("/", "/index.html"):                        # sin id no se muestra ninguna tira
                    return self._send(200, HOME.encode(), "text/html; charset=utf-8")
                m = re.fullmatch(rf"/s/({ID})", p)
                if m:
                    sid = m.group(1)
                    if not _strip_path(sid):
                        return self._404()
                    photos = [i for i in (1, 2, 3) if (C.TMP_DIR / sid / f"foto{i}_f.jpg").is_file()]
                    extra = ""
                    if photos:
                        cells = "".join(f'<a href="/dl/photo/{sid}/{i}.jpg" download><img src="/photo/{sid}/{i}.jpg" alt="Foto {i}">Descargar foto {i}</a>' for i in photos)
                        extra = f'<h2>Fotos sueltas</h2><div class="grid">{cells}</div>'
                    return self._send(200, PAGE.replace("__ID__", sid).replace("__PHOTOS__", extra).encode(), "text/html; charset=utf-8")
                m = re.fullmatch(rf"/(strip|dl/strip)/({ID})\.jpg", p)
                if m:
                    sp = _strip_path(m.group(2))
                    dl = f"fotobut-{m.group(2)[:4]}.jpg" if m.group(1) == "dl/strip" else None
                    return self._file(sp[0], sp[1], dl_name=dl) if sp else self._404()
                m = re.fullmatch(rf"/(photo|dl/photo)/({ID})/([1-3])\.jpg", p)
                if m:
                    f = C.TMP_DIR / m.group(2) / f"foto{m.group(3)}_f.jpg"
                    dl = f"fotobut-{m.group(2)[:4]}-foto{m.group(3)}.jpg" if m.group(1) == "dl/photo" else None
                    return self._file(f if _vigente(f) else None, C.TMP_DIR, dl_name=dl)
                m = re.fullmatch(r"/f/([A-Za-z0-9\-]+\.ttf)", p)
                if m:
                    return self._file(C.WEB_DIR / "fonts" / m.group(1), C.WEB_DIR, "font/ttf")
                self._404()
            except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                self.close_connection = True

    return H


class ServidorAcotado(ThreadingHTTPServer):
    """ThreadingHTTPServer con tope de conexiones: si se supera, la conexion nueva se cierra de inmediato (no se crea hilo)."""
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, addr, lim: Limites):
        self.lim = lim
        super().__init__(addr, make_handler(lim))

    def process_request(self, request, client_address):
        ip = client_address[0]
        if not self.lim.abrir(ip):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:                                # noqa: BLE001  (no se pudo crear el hilo)
            self.lim.cerrar(ip)
            self.shutdown_request(request)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.lim.cerrar(client_address[0])

    def handle_error(self, request, client_address):     # sin trazas por cada cliente que corta la conexion
        pass


def serve_share(host=C.SHARE_HOST, port=C.SHARE_PORT):
    httpd = ServidorAcotado((host, port), Limites())
    log.info("Descargas en http://%s:%d", host, port)
    return httpd
