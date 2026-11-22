#!/usr/bin/env python3
"""PROCESO 4 · monitor: caja negra y panel de mantenimiento de El Fotobut.

- Cada 10 s toma una muestra de salud (temperatura, RAM, disco, voltaje, estado de los 3 servicios y de la cabina) y la
  guarda en la caja negra (microSD). Los cambios importantes (un servicio se reinicio, el STM32 dejo de mandar tramas,
  bajo voltaje...) se anotan como eventos con nivel y hora.
- Sirve un panel web en 127.0.0.1:9000 para ver la salud, leer los registros, descargar un respaldo y reiniciar un
  servicio. NO esta expuesto a la red: se entra con un tunel SSH (ssh -L 9000:127.0.0.1:9000 usuario@cabina), de modo
  que la unica puerta de administracion es SSH con llave. Ver docs/RECUPERACION.md.
Corre aparte y con prioridad baja: si muere, la cabina sigue; si la cabina muere, el monitor lo deja anotado.
"""
from __future__ import annotations
import io, json, logging, os, re, shutil, signal, subprocess, tarfile, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fotobut.servicios import config as C
from fotobut.servicios.caja_negra import CajaNegra

log = logging.getLogger("fotobut.monitor")
SERVICIOS = {"control": "fotobut-control", "vision": "fotobut-vision", "qr": "fotobut-qr"}
CPU_ALERTA_C, DISCO_MIN_MB = 75.0, 300


def _run(cmd: list[str], timeout: float = 4.0) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def sistema() -> dict:
    d: dict = {}
    try:
        d["cpu_c"] = round(int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000, 1)
    except (OSError, ValueError):
        d["cpu_c"] = None
    try:
        m = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
        d["ram_mb"], d["ram_total_mb"] = (m["MemTotal"] - m["MemAvailable"]) // 1024, m["MemTotal"] // 1024
    except (OSError, ValueError, KeyError, IndexError):
        pass
    try:
        d["carga"] = round(os.getloadavg()[0], 2)
        d["encendida_s"] = int(float(open("/proc/uptime").read().split()[0]))
    except (OSError, ValueError):
        pass
    try:
        C.FINAL_DIR.mkdir(parents=True, exist_ok=True)
        d["disco_libre_mb"] = shutil.disk_usage(C.FINAL_DIR).free // (1024 * 1024)
    except OSError:
        pass
    v = _run(["vcgencmd", "get_throttled"], 2)           # 0x0 = sin problemas; bit 0 = bajo voltaje AHORA, bit 16 = ocurrio
    if v and "=" in v:
        try:
            d["voltaje"] = int(v.strip().split("=")[1], 16)
        except ValueError:
            pass
    return d


def servicios() -> dict:
    """Estado de cada unidad segun systemd (vacio si no hay systemd, p. ej. en el simulador)."""
    out = {}
    for corto, unidad in SERVICIOS.items():
        txt = _run(["systemctl", "show", unidad, "-p", "ActiveState", "-p", "SubState", "-p", "MainPID", "-p", "NRestarts"])
        if not txt:
            continue
        kv = dict(l.split("=", 1) for l in txt.strip().splitlines() if "=" in l)
        if kv.get("ActiveState") in (None, "") or kv.get("LoadState") == "not-found":
            continue
        out[corto] = {"activo": kv.get("ActiveState"), "sub": kv.get("SubState"),
                      "pid": int(kv.get("MainPID", "0") or 0), "reinicios": int(kv.get("NRestarts", "0") or 0)}
    return out


def _get(url: str, timeout: float = 2.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def cabina() -> dict:
    """Lo que dice vision_gui (por su API local) y si el servidor de descargas contesta."""
    d: dict = {"vision_ok": False, "qr_ok": False}
    try:
        s = json.loads(_get(f"http://127.0.0.1:{C.UI_PORT}/api/state"))
        tel, hw = s.get("telemetry") or {}, s.get("hw") or {}
        d.update(vision_ok=True, estado=s.get("state"), sesiones=s.get("sessions"), stm32=bool(s.get("uart_ok")),
                 enlace=hw.get("link"), dist=s.get("distance"), temp_c=tel.get("temp_c"), sim=bool(s.get("sim")),
                 camara=not s.get("cam_sim"), ap=bool(s.get("ap_active")))
    except Exception:                                    # noqa: BLE001
        pass
    try:
        d["qr_ok"] = _get(f"http://127.0.0.1:{C.SHARE_PORT}/salud") == b"ok"
    except Exception:                                    # noqa: BLE001
        pass
    return d


class Monitor:
    def __init__(self, caja: CajaNegra | None = None):
        self.caja = caja or CajaNegra()
        self.ultima: dict = {}
        self.prev: dict | None = None
        self.lock = threading.Lock()

    def arranque(self) -> None:
        """Deja anotado como se encontro la cabina: sirve para reconstruir que paso antes de un apagon."""
        ant, sis = self.caja.ultimo(), sistema()
        up = sis.get("encendida_s", 0)
        if ant and time.time() - ant.get("t", 0) > up + 5:       # la ultima linea es de ANTES de este encendido
            self.caja.evento("WARN", f"la Raspberry Pi se reinicio o estuvo apagada; ultimo registro a las {ant.get('h', '?')}"
                             + (f" (cabina en {ant['estado']})" if ant.get("estado") else ""), apagada_s=int(time.time() - ant["t"] - up))
        self.caja.evento("INFO", f"monitor en marcha; la Pi lleva encendida {up} s")
        self.caja.purgar()

    def tick(self) -> dict:
        m = {**sistema(), **cabina(), "srv": servicios()}
        self._eventos(m)
        self.caja.muestra(m)
        with self.lock:
            self.ultima, self.prev = m, m
        return m

    def _eventos(self, m: dict) -> None:
        p, ev = self.prev, self.caja.evento
        if p is None:
            return
        for n, s in m["srv"].items():
            a = p["srv"].get(n)
            if not a:
                continue
            if s["reinicios"] > a["reinicios"]:
                ev("WARN", f"{SERVICIOS[n]} se reinicio (van {s['reinicios']}); systemd lo levanto de nuevo", servicio=n, pid=s["pid"])
            if s["activo"] != a["activo"]:
                ev("ERROR" if s["activo"] in ("failed", "inactive") else "INFO", f"{SERVICIOS[n]}: {a['activo']} -> {s['activo']}", servicio=n)
        pares = [("vision_ok", "la pantalla (vision_gui) dejo de responder", "la pantalla (vision_gui) volvio a responder"),
                 ("qr_ok", "el servidor de descargas dejo de responder", "el servidor de descargas volvio a responder")]
        if m.get("vision_ok") and p.get("vision_ok"):
            pares += [("stm32", "el STM32 dejo de mandar tramas (sensor de distancia)", "el STM32 volvio a mandar tramas"),
                      ("enlace", "vision_gui perdio a control_daemon (socket)", "vision_gui se reconecto con control_daemon"),
                      ("camara", "la camara no esta disponible", "la camara volvio")]
        for k, mal, bien in pares:
            if bool(m.get(k)) != bool(p.get(k)):
                ev("INFO" if m.get(k) else "ERROR", bien if m.get(k) else mal)
        c, c0 = m.get("cpu_c") or 0, p.get("cpu_c") or 0
        if (c > CPU_ALERTA_C) != (c0 > CPU_ALERTA_C):
            ev("WARN" if c > CPU_ALERTA_C else "INFO", f"temperatura del CPU {c:.0f} C ({'alta' if c > CPU_ALERTA_C else 'normal'})")
        if (m.get("voltaje", 0) & 1) != (p.get("voltaje", 0) & 1):
            ev("WARN" if m.get("voltaje", 0) & 1 else "INFO", "bajo voltaje en la alimentacion" if m.get("voltaje", 0) & 1 else "voltaje normal")
        libre, libre0 = m.get("disco_libre_mb", 1e9), p.get("disco_libre_mb", 1e9)
        if (libre < DISCO_MIN_MB) != (libre0 < DISCO_MIN_MB) and libre < DISCO_MIN_MB:
            ev("WARN", f"poco espacio en la microSD: {libre} MB libres")
        if m.get("sesiones") is not None and p.get("sesiones") is not None and m["sesiones"] > p["sesiones"]:
            ev("INFO", f"sesion terminada (van {m['sesiones']} desde que arranco la pantalla)")

    def run(self) -> None:
        self.arranque()
        n = 0
        while True:
            t0 = time.monotonic()
            try:
                self.tick()
            except Exception:                            # noqa: BLE001
                log.exception("muestra de salud")
            n += 1
            if n % 8640 == 0:                            # una vez al dia
                self.caja.purgar()
            time.sleep(max(1.0, C.CAJA_NEGRA_PERIODO_S - (time.monotonic() - t0)))

    # ---------- acciones del panel ----------
    def reiniciar(self, corto: str) -> tuple[bool, str]:
        """Pide a un servicio que termine (SIGTERM); systemd lo levanta en 1 s (Restart=always). No requiere ser root:
        los procesos son del mismo usuario. Asi el panel no necesita ningun privilegio de administrador."""
        if corto not in SERVICIOS:
            return False, "servicio desconocido"
        s = servicios().get(corto)
        if not s or s["pid"] <= 1:
            return False, "systemd no reporta ese servicio en marcha (¿simulador?)"
        try:
            os.kill(s["pid"], signal.SIGTERM)
        except OSError as e:
            return False, f"no se pudo: {e}"
        self.caja.evento("WARN", f"reinicio de {SERVICIOS[corto]} pedido desde el panel de mantenimiento", servicio=corto, pid=s["pid"])
        return True, "reiniciando"

    def registro(self, corto: str, n: int) -> str:
        unidades = [SERVICIOS[corto]] if corto in SERVICIOS else ["fotobut-monitor"] if corto == "monitor" else list(SERVICIOS.values())
        cmd = ["journalctl", "--no-pager", "-o", "short-iso", "-n", str(max(10, min(n, 1000)))]
        for u in unidades:
            cmd += ["-u", u]
        return _run(cmd, 8) or "(journalctl no disponible: en el simulador los registros salen en la terminal)"

    def respaldo(self) -> bytes:
        """tar.gz con todo lo necesario para diagnosticar o revivir la cabina en otra tarjeta: caja negra, punto de control,
        registro de sesiones y los ultimos registros de systemd. Las fotos NO van (son de los usuarios)."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            def agrega(nombre: str, datos: bytes) -> None:
                ti = tarfile.TarInfo(nombre)
                ti.size, ti.mtime = len(datos), int(time.time())
                tar.addfile(ti, io.BytesIO(datos))
            for p in sorted(self.caja.dir.glob("*.jsonl")):
                tar.add(p, arcname=f"respaldo/caja_negra/{p.name}")
            for nombre in ("estado.json", "sesiones.log", "contador.txt"):
                p = C.FINAL_DIR / nombre
                if p.is_file():
                    tar.add(p, arcname=f"respaldo/sesiones/{nombre}")
            agrega("respaldo/journal.txt", self.registro("todos", 1000).encode())
            agrega("respaldo/LEEME.txt", b"Respaldo de El Fotobut. Para restaurar en otra tarjeta: tools/mantenimiento/restaurar.sh respaldo.tar.gz\n")
        return buf.getvalue()


PANEL = Path(__file__).resolve().parents[2] / "web" / "panel.html"


def make_handler(mon: Monitor, puerto: int):
    hosts = {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}

    class H(BaseHTTPRequestHandler):
        protocol_version, server_version, sys_version, timeout = "HTTP/1.1", "Fotobut", "", 15

        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json", extra=None):
            self.send_response(code)
            for k, v in {"Content-Type": ctype, "Content-Length": str(len(body)), "Cache-Control": "no-store",
                         "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                         "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                                                    "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'none'",
                         **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode())

        def _host_ok(self) -> bool:
            # Aunque solo escucha en 127.0.0.1, una pagina maliciosa abierta en la laptop del operador podria intentar
            # hablarle (DNS rebinding / peticiones cruzadas). Se exige que el Host sea exactamente el local.
            return self.headers.get("Host", "") in hosts

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, b"", "text/plain")
            p, _, q = self.path.partition("?")
            qs = dict(x.split("=", 1) for x in q.split("&") if "=" in x)
            try:
                if p == "/":
                    return self._send(200, PANEL.read_bytes(), "text/html; charset=utf-8")
                if p == "/api/resumen":
                    with mon.lock:
                        u = dict(mon.ultima)
                    return self._json({"ahora": time.strftime("%Y-%m-%d %H:%M:%S"), "muestra": u,
                                       "eventos": mon.caja.leer(24 * C.CAJA_NEGRA_DIAS, "e", 60)[::-1],
                                       "serie": [{k: r.get(k) for k in ("t", "cpu_c", "ram_mb", "temp_c")} for r in mon.caja.leer(1, "m", 400)]})
                if p == "/api/registro":
                    n = int(qs.get("n", "200")) if qs.get("n", "200").isdigit() else 200
                    return self._send(200, mon.registro(re.sub(r"[^a-z]", "", qs.get("servicio", "todos")), n).encode(), "text/plain; charset=utf-8")
                if p == "/respaldo.tar.gz":
                    return self._send(200, mon.respaldo(), "application/gzip",
                                      {"Content-Disposition": f'attachment; filename="fotobut-respaldo-{time.strftime("%Y%m%d-%H%M")}.tar.gz"'})
                self._send(404, b"", "text/plain")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            # Cabecera propia + JSON: un formulario de otra pagina no puede mandarlas sin permiso CORS, que aqui nunca se da.
            if not self._host_ok() or self.headers.get("X-Fotobut") != "panel" or "application/json" not in self.headers.get("Content-Type", ""):
                return self._send(403, b"", "text/plain")
            n = int(self.headers.get("Content-Length", "0") or 0)
            if n > 1024:
                return self._send(413, b"", "text/plain")
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, b"", "text/plain")
            if self.path == "/api/reiniciar":
                ok, msg = mon.reiniciar(str(d.get("servicio", "")))
                return self._json({"ok": ok, "msg": msg}, 200 if ok else 409)
            self._send(404, b"", "text/plain")

    return H


def serve_panel(mon: Monitor, host=C.ADMIN_HOST, port=C.ADMIN_PORT):
    httpd = ThreadingHTTPServer((host, port), make_handler(mon, port))
    httpd.daemon_threads = True
    httpd.handle_error = lambda *a: None                 # sin trazas por clientes que cortan la conexion
    return httpd


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s monitor: %(message)s")
    logging.getLogger("fotobut.config").info(C.resumen_conf())                 # [C22-config] de donde salieron los valores
    for aviso in C.CONF_AVISOS:
        logging.getLogger("fotobut.config").warning(aviso)
    from fotobut.servicios.sched import set_prio
    from fotobut.servicios.vigia import Vigia, Latido
    set_prio("monitor", nice=15)
    os.umask(0o027)
    mon = Monitor()
    try:
        httpd = serve_panel(mon)
        threading.Thread(target=httpd.serve_forever, name="H_panel", daemon=True).start()
        log.info("panel de mantenimiento en http://%s:%d (solo local; usar tunel SSH)", C.ADMIN_HOST, C.ADMIN_PORT)
    except OSError as e:
        log.error("no se pudo abrir el panel: %s (la caja negra sigue funcionando)", e)
    lat = Latido()
    orig = mon.tick
    mon.tick = lambda: (lat.toc(), orig())[1]            # type: ignore[method-assign]
    Vigia("monitor", {"muestreo de salud": lambda: lat.edad() < 60}).start()
    try:
        mon.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
