"""Maquina de estados de El Fotobut (logica pura, sin GUI).

ATTRACT -> READY -> COUNTDOWN -> CAPTURE -> (COUNTDOWN x3) -> PROCESSING -> RESULT -> READY/ATTRACT
SLEEP tras SLEEP_AFTER_S sin presencia. Entradas: boton (GPIO17), potenciometro (filtro), distancia (STM32).
"""
from __future__ import annotations
import logging, os, secrets, threading, time
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import config as C
from .qr import make_qr
from .strip import compose
from .filters import apply_filter
from .oled import local_ip
from .pool import FramePool
from .sched import set_prio


def share_host() -> tuple[str, bool]:
    """(host para el QR, punto de acceso activo?). Si la Pi tiene la IP del AP, el QR usa esa; si no, su IP actual."""
    import os, socket
    if os.environ.get("FOTOBUT_FAKE_AP"):                      # solo para pruebas en el simulador
        return C.AP_IP, True
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((C.AP_IP, 0))
        s.close()
        return C.AP_IP, True
    except OSError:
        return local_ip(), False

log = logging.getLogger("fotobut.machine")


def pot_to_filter(pot: int, cur: int | None) -> int:
    """Potenciometro 0-1023 -> indice de filtro, con histeresis para que no parpadee en los limites."""
    n = len(C.FILTERS)
    raw = pot / (1024 / n)
    idx = min(n - 1, int(raw))
    if cur is not None and idx != cur and abs(raw - (cur + 0.5)) < 0.5 + 0.15:
        return cur
    return idx


class Machine:
    def __init__(self, hal, camera, clock=time.monotonic):
        self.hal, self.camera, self.clock = hal, camera, clock
        self.lock = threading.RLock()                        # [C9-mutex_estado] protege el estado de la cabina (maquina vs hilos HTTP)
        self.cond = threading.Condition(self.lock)           # notifica a los clientes SSE cuando cambia algo
        self.wake = threading.Event()                        # un evento (boton) despierta el bucle sin esperar los 50 ms
        self.version = 0
        self.state = "ATTRACT"
        self._t_state = clock()
        self._last_activity = clock()
        self.filter_idx = 0
        self._pot_ema: float | None = None
        self._pot_last_active = 0
        self.consec = 0
        self.distance: int | None = None
        self.uart_ok = False
        self.pot = 0
        self.shot = 0
        self.count = C.COUNT_FROM
        self.photos: list[str] = []
        self.sid: str | None = None
        self.strip_url: str | None = None
        self.qr_wifi = self.qr_url = None
        self.pool = FramePool(C.SHOTS)                       # [C10-pool] 3 bloques Full HD reservados al arrancar
        self._worker = threading.Thread(target=self._h_compositor, name="H_compositor", daemon=True)   # consumidor
        self._worker.start()
        self._strip_ready = False
        self._t_cap3: float | None = None
        self._tick_t: list[float] = []
        self._press_ref = (0, 0)
        self._counter = self._load_counter()
        self.sessions_done = 0
        self._last_key = None
        self.extra: dict = {}
        self.ap_active = False
        self.share_url: str | None = None
        self.last_done_sid: str | None = None

    # ---------- utilidades ----------
    def _load_counter(self) -> int:
        try:
            return int((C.FINAL_DIR / "contador.txt").read_text().strip())
        except Exception:                                    # noqa: BLE001
            return 0

    def _save_counter(self) -> None:
        try:
            C.FINAL_DIR.mkdir(parents=True, exist_ok=True)
            (C.FINAL_DIR / "contador.txt").write_text(str(self._counter))
        except Exception as e:                               # noqa: BLE001
            log.warning("No se pudo guardar el contador: %s", e)

    def _go(self, state: str) -> None:
        log.info("%s -> %s", self.state, state)
        self.state, self._t_state = state, self.clock()
        notify = getattr(self.hal, "notify_state", None)     # el OLED (en control_daemon) muestra el estado de la cabina
        if notify:
            notify(state, self.shot, self.sessions_done)

    def _age(self) -> float:
        return self.clock() - self._t_state

    def timeout_s(self) -> float | None:
        return {"READY": C.READY_TIMEOUT_S, "RESULT": C.RESULT_TIMEOUT_S}.get(self.state)

    # ---------- bucle principal ----------
    def step(self) -> None:
        inp = self.hal.read()
        with self.lock:                                      # [C9-mutex_estado] toda la decision ocurre con el estado bloqueado
            act = self._decide(inp)
        if act == "capture":                                 # la camara tarda cientos de ms: se hace FUERA del candado
            self._capture()

    def _decide(self, inp):
        now = self.clock()
        self.uart_ok = inp.uart_ok
        press = inp.button_presses > 0
        if press:
            self._press_ref = getattr(self.hal, "last_edge", (0, 0))

        # potenciometro -> filtro (con suavizado)
        self._pot_ema = inp.pot if self._pot_ema is None else 0.6 * self._pot_ema + 0.4 * inp.pot
        self.pot = int(self._pot_ema)
        if abs(self.pot - self._pot_last_active) > 14:
            self._pot_last_active = self.pot
            if self.state in ("READY", "ATTRACT", "SLEEP"):
                self._last_activity = now
        if self.state not in ("COUNTDOWN", "CAPTURE", "PROCESSING"):
            self.filter_idx = pot_to_filter(self.pot, self.filter_idx)

        # presencia: 5 lecturas seguidas (500 ms a 10 Hz) dentro de 30-120 cm
        if inp.dist_seq != getattr(self, "_seq", None):
            self._seq = inp.dist_seq
            self.distance = inp.distance
            ok = inp.distance is not None and C.PRESENCE_MIN_CM <= inp.distance <= C.PRESENCE_MAX_CM
            self.consec = self.consec + 1 if ok else 0
            if ok:
                self._last_activity = now
        wake = self.consec >= C.PRESENCE_SAMPLES
        if press:
            self._last_activity = now

        s = self.state
        if s == "SLEEP":
            if wake or press:
                self._go("READY")
        elif s == "ATTRACT":
            if wake or press:
                self._go("READY")
            elif now - self._last_activity > C.SLEEP_AFTER_S:
                self._go("SLEEP")
        elif s == "READY":
            if press:
                self._start_session()
            elif now - self._last_activity > C.READY_TIMEOUT_S:
                self._go("ATTRACT")
        elif s == "COUNTDOWN":
            c = C.COUNT_FROM - int(self._age())
            if c != self.count and c >= 1:
                self.count = c
                self._tick()
            if self._age() >= C.COUNT_FROM:
                return "capture"
        elif s == "CAPTURE":
            if self._age() >= C.REVIEW_S:
                if self.shot < C.SHOTS:
                    self.shot += 1
                    self.count = C.COUNT_FROM
                    self._tick(first=True)
                    self._go("COUNTDOWN")
                else:
                    self._begin_processing()
        elif s == "PROCESSING":
            if self._strip_ready and self._age() >= C.PROCESSING_MIN_S:
                if self._t_cap3 is not None:
                    log.info("MEDICION composicion captura3_a_QR_ms=%.0f (requisito <= 2500)", (self.clock() - self._t_cap3) * 1000)
                    self._t_cap3 = None
                self._go("RESULT")
        elif s == "RESULT":
            if press:
                self._last_activity = now
                self._go("READY")
            elif self._age() > C.RESULT_TIMEOUT_S:
                self._go("ATTRACT")

        self._publish()
        return None

    # ---------- sesion ----------
    def _start_session(self) -> None:
        self._counter += 1
        self._save_counter()
        self.sid = f"{self._counter:04d}-{secrets.token_hex(4)}"
        self.photos, self.strip_url, self._strip_ready = [], None, False
        self.qr_wifi = self.qr_url = None
        self.shot, self.count = 1, C.COUNT_FROM
        (C.TMP_DIR / self.sid).mkdir(parents=True, exist_ok=True)
        ref, deb = self._press_ref                           # el primer tono lleva la marca del boton: mide boton -> tono
        self._tick(first=True, ref=ref, deb=deb)
        self._prune()
        self._go("COUNTDOWN")

    def _tick(self, first: bool = False, ref: int = 0, deb: int = 0) -> None:
        """Tono de la cuenta regresiva y medicion de su intervalo (requisito del Avance 1: 1000 ms +-10 ms)."""
        t = self.clock()
        if first:
            self._tick_t = []
        elif self._tick_t:
            d = (t - self._tick_t[-1]) * 1000.0
            log.info("MEDICION cuenta_regresiva intervalo_ms=%.2f error_ms=%+.2f", d, d - 1000.0)
        self._tick_t.append(t)
        self.hal.beep(C.TICK_HZ, C.TICK_MS, ref, deb)

    def _capture(self) -> None:
        """Productor (H_maquina/H_captura): saca la foto, la deja en /tmp para la revision y la entrega al pool."""
        sid, shot = self.sid, self.shot
        path = C.TMP_DIR / sid / f"foto{shot}.jpg"
        img = None
        try:
            self.camera.capture(path)
            img = Image.open(path)
            img.load()
        except Exception as e:                               # noqa: BLE001
            log.error("Fallo la captura: %s", e)
            img = Image.new("RGB", (C.CAP_W, C.CAP_H), (40, 40, 40))   # marcador: el conteo de bloques no se desincroniza
        self.hal.beep(C.SHUTTER_HZ, C.SHUTTER_MS)            # sonido de obturador
        fid = C.FILTERS[self.filter_idx]["id"]
        try:
            self.pool.put(img, (sid, fid, shot))             # [C9-sem_libres] espera bloque libre; despierta al compositor
        except TimeoutError:
            log.error("Pool lleno: se reinicia")
            self.pool.reset()
            self.pool.put(img, (sid, fid, shot))
        with self.lock:                                      # [C9-mutex_estado]
            self.photos.append(f"/photo/{sid}/foto{shot}.jpg")
            if shot == C.SHOTS:
                self._t_cap3 = self.clock()
            self._go("CAPTURE")
            self._publish()

    def _begin_processing(self) -> None:
        self._go("PROCESSING")

    def _h_compositor(self) -> None:
        """Consumidor (T4, nice 0). Duerme en sem_llenos; con 3 fotos arma la tira, la guarda con fsync y libera los bloques."""
        set_prio("H_compositor", nice=0)                     # [C8-T4]
        while True:
            frames = []
            for _ in range(C.SHOTS):
                frames.append(self.pool.get())               # [C9-sem_llenos] 0 % de CPU mientras espera
            t0 = time.monotonic()
            sid, fid, _ = frames[0][2]
            try:
                imgs = [Image.fromarray(f[1]) for f in frames]
                strip = compose(imgs, fid, sid)
                tmp_path = C.TMP_DIR / sid / "tira.jpg"
                strip.save(tmp_path, "JPEG", quality=90)
                self._persist(sid, tmp_path, fid)
                for i, im in enumerate(imgs, 1):              # fotos sueltas con el filtro elegido (solo en RAM)
                    apply_filter(im, fid).save(C.TMP_DIR / sid / f"foto{i}_f.jpg", "JPEG", quality=90)
                host, ap = share_host()
                share = f"http://{host}:{C.SHARE_PORT}/s/{sid}"
                qw = make_qr(f"WIFI:T:WPA;S:{C.WIFI_SSID};P:{C.WIFI_PASS};;") if ap else None
                qu = make_qr(share)
                with self.lock:                              # [C9-mutex_estado]
                    self.ap_active, self.share_url, self.qr_wifi, self.qr_url = ap, share, qw, qu
                    self.strip_url, self.last_done_sid = f"/strip/{sid}.jpg", sid
                    self.sessions_done += 1
            except Exception as e:                           # noqa: BLE001
                log.exception("No se pudo armar la tira: %s", e)
            finally:
                for f in frames:
                    self.pool.release(f[0])                  # [C9-sem_libres] devuelve los 3 bloques
            log.info("MEDICION composicion compositor_ms=%.0f", (time.monotonic() - t0) * 1000)
            with self.lock:
                self._strip_ready = True
                self._publish()

    def _persist(self, sid: str, src: Path, fid: str) -> None:
        """Guarda la tira final en la microSD con fsync (diseno de la clase 15) y anota una linea de telemetria."""
        try:
            C.FINAL_DIR.mkdir(parents=True, exist_ok=True)
            dst = C.FINAL_DIR / f"{sid}.jpg"
            with open(dst, "wb") as f:
                f.write(src.read_bytes())
                f.flush()
                os.fsync(f.fileno())
            with open(C.FINAL_DIR / "sesiones.log", "a") as f:
                f.write(f"{datetime.now():%Y-%m-%dT%H:%M:%S},{sid},{fid}\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:                               # noqa: BLE001
            log.error("No se pudo escribir en %s: %s", C.FINAL_DIR, e)

    def _prune(self) -> None:
        """Libera RAM: conserva solo las ultimas MAX_TMP_SESSIONS sesiones en /tmp (la tira final sigue en la microSD)."""
        try:
            import shutil
            dirs = sorted((d for d in C.TMP_DIR.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)
            for d in dirs[C.MAX_TMP_SESSIONS:]:
                if d.name != self.sid:
                    shutil.rmtree(d, ignore_errors=True)
        except Exception as e:                               # noqa: BLE001
            log.warning("No se pudo limpiar /tmp: %s", e)

    # ---------- estado para la interfaz ----------
    def snapshot(self) -> dict:
        with self.lock:                                      # [C9-mutex_estado] lectura coherente (sin "lecturas desgarradas")
            return self._snapshot()

    def _snapshot(self) -> dict:
        f = C.FILTERS[self.filter_idx]
        tel = getattr(self.hal, "telemetry", None)
        if tel:
            self.extra = tel()
        return {
            "v": self.version, "state": self.state, "age_ms": int(self._age() * 1000),
            "shot": self.shot, "shots": C.SHOTS, "count": self.count, "count_from": C.COUNT_FROM,
            "review_s": C.REVIEW_S, "timeout_s": self.timeout_s(),
            "filter_idx": self.filter_idx, "filters": [{"id": x["id"], "name": x["name"], "css": x["css"]} for x in C.FILTERS],
            "filter_css": f["css"], "pot": self.pot, "distance": self.distance, "present": self.consec >= 1,
            "uart_ok": self.uart_ok, "sim": bool(getattr(self.hal, "is_sim", False)),
            "sid": self.sid, "photos": list(self.photos), "strip_url": self.strip_url,
            "qr_wifi": self.qr_wifi, "qr_url": self.qr_url, "ap_active": self.ap_active, "share_url": self.share_url,
            "wifi": {"ssid": C.WIFI_SSID, "pass": C.WIFI_PASS}, "sessions": self.sessions_done,
            "cam_sim": bool(getattr(self.camera, "is_sim", False)), "hw": self.hal.status() if hasattr(self.hal, "status") else {},
            "telemetry": self.extra,
        }

    def _publish(self) -> None:
        """Avisa a los clientes (SSE) solo cuando cambia algo relevante."""
        key = (self.state, self.shot, self.count, self.filter_idx, self.pot // 16, self.distance,
               self.uart_ok, len(self.photos), self.strip_url, self.consec >= 1)
        if key != self._last_key:
            self._last_key = key
            with self.cond:
                self.version += 1
                self.cond.notify_all()

    def wait_change(self, version: int, timeout: float) -> bool:
        with self.cond:
            if self.version == version:
                self.cond.wait(timeout)
            return self.version != version

    def run_forever(self, hz: int = 20) -> None:
        """Hilo H_maquina. Duerme hasta el siguiente evento: boton (wake.set), o el proximo segundo de la cuenta regresiva."""
        from .sched import name_thread
        name_thread("H_maquina")
        while True:
            try:
                self.step()
            except Exception:                                # noqa: BLE001
                log.exception("Error en el ciclo principal")
            wait = 1.0 / hz
            if self.state == "COUNTDOWN":                    # despertar justo en el siguiente segundo (precision +-10 ms)
                wait = min(wait, max(0.0005, 1.0 - (self._age() % 1.0)))
            self.wake.wait(wait)
            self.wake.clear()
