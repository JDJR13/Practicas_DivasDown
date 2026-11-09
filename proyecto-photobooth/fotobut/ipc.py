"""IPC entre los 3 procesos de El Fotobut (clase 11) y su sincronizacion (clase 9).

  control_daemon  <== socket AF_UNIX SOCK_SEQPACKET ==>  vision_gui     (eventos y ordenes, mensajes fijos de 64 bytes)
  control_daemon  ---- memoria compartida /dev/shm/pb_status ---->  vision_gui   (potenciometro, LDR, distancia, temperatura a 20 Hz)
  qr_httpd no habla con nadie por IPC: solo lee los archivos de la sesion (aislamiento de fallos).

Tamanos fijos (clase 20): MSG = 64 bytes (sizeof de la struct), SHM = 58 bytes usados de 128.
"""
from __future__ import annotations
import ctypes, logging, math, mmap, os, socket, struct, threading, time
from typing import Optional

from . import config as C

log = logging.getLogger("fotobut.ipc")

# ----------------------------------------------------------------------------------------------------------------
# [C11-socket] Mensaje de control: struct de 64 bytes exactos  (tipo, flags, seq, a, b, ref_ns, payload[48])
# ----------------------------------------------------------------------------------------------------------------
MSG_FMT = "<BBHHHq48s"                                    # [C20-tipos] u8,u8,u16,u16,u16,i64,48 bytes: anchos fijos, little-endian, SIN padding
MSG_SIZE = struct.calcsize(MSG_FMT)                      # 64
assert MSG_SIZE == 64

EV_HELLO, EV_BUTTON, EV_PONG, EV_RESET = 1, 2, 3, 4      # control_daemon -> vision_gui (EV_RESET = boton azul)
CMD_BEEP, CMD_SIM, CMD_STATE, CMD_PING = 10, 11, 12, 13  # vision_gui -> control_daemon
F_SIM_BUTTON, F_SIM_POT, F_SIM_DIST, F_SIM_NODIST, F_SIM_RESET = 1, 2, 4, 8, 16
_seq = 0
_seq_lock = threading.Lock()


def pack(tipo: int, flags: int = 0, a: int = 0, b: int = 0, ref_ns: int = 0, payload: bytes = b"") -> bytes:
    global _seq
    with _seq_lock:
        _seq = (_seq + 1) & 0xFFFF
        s = _seq
    return struct.pack(MSG_FMT, tipo, flags, s, a & 0xFFFF, b & 0xFFFF, ref_ns, payload[:48])


def unpack(data: bytes) -> dict:
    t, fl, seq, a, b, ref, pl = struct.unpack(MSG_FMT, data)
    return {"type": t, "flags": fl, "seq": seq, "a": a, "b": b, "ref_ns": ref, "payload": pl.rstrip(b"\0")}


class ControlServer:
    """Lado de control_daemon: escucha en el socket y atiende a UN cliente (vision_gui). Si este muere y vuelve, se reemplaza."""

    def __init__(self, path: str, on_command, hello_flags=lambda: 0):
        self.path, self.on_command, self.hello_flags = path, on_command, hello_flags
        self.client: Optional[socket.socket] = None
        self.mutex_sock = threading.Lock()               # [C9-mutex_sock] un solo hilo escribe al cliente a la vez
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            os.unlink(path)
        except FileNotFoundError:
            pass
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)   # [C11-socket] bidireccional, con limites de mensaje
        self.srv.bind(path)
        os.chmod(path, 0o660)
        self.srv.listen(1)

    def serve_forever(self) -> None:                     # hilo H_socket
        from .sched import set_prio
        set_prio("H_socket", nice=0)
        while True:
            c, _ = self.srv.accept()
            with self.mutex_sock:
                old, self.client = self.client, c
            if old:
                try: old.close()
                except OSError: pass
            log.info("vision_gui conectado")
            self.send(pack(EV_HELLO, flags=self.hello_flags()))
            self._rx(c)

    def _rx(self, c: socket.socket) -> None:
        while True:
            try:
                data = c.recv(MSG_SIZE)
            except OSError:
                data = b""
            if len(data) != MSG_SIZE:                    # cierre limpio o mensaje truncado
                log.warning("vision_gui desconectado")
                with self.mutex_sock:
                    if self.client is c:
                        self.client = None
                try: c.close()
                except OSError: pass
                return
            try:
                self.on_command(unpack(data), self)
            except Exception:                            # noqa: BLE001
                log.exception("orden IPC")

    def send(self, data: bytes) -> bool:
        with self.mutex_sock:
            c = self.client
            if c is None:
                return False
            try:
                c.send(data)
                return True
            except OSError:
                self.client = None
                return False


class ControlClient:
    """Lado de vision_gui: conecta (con reintentos) y entrega cada mensaje al callback. Reconecta solo si control_daemon reinicia."""

    def __init__(self, path: str, on_message, on_link=lambda up: None):
        self.path, self.on_message, self.on_link = path, on_message, on_link
        self.sock: Optional[socket.socket] = None
        self.up = False
        self.mutex_sock = threading.Lock()               # [C9-mutex_sock]

    def run(self) -> None:                               # hilo H_ipc_rx
        from .sched import set_prio
        set_prio("H_ipc_rx", nice=-5)
        delay = 0.2
        while True:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            try:
                s.connect(self.path)
            except OSError:
                s.close()
                time.sleep(delay)
                delay = min(2.0, delay * 1.5)            # espera creciente: no satura el CPU mientras control_daemon no vuelve
                continue
            delay = 0.2
            with self.mutex_sock:
                self.sock, self.up = s, True
            log.info("conectado a control_daemon")
            self.on_link(True)
            while True:
                try:
                    data = s.recv(MSG_SIZE)
                except OSError:
                    data = b""
                if len(data) != MSG_SIZE:
                    break
                try:
                    self.on_message(unpack(data))
                except Exception:                        # noqa: BLE001
                    log.exception("mensaje IPC")
            with self.mutex_sock:
                self.sock, self.up = None, False
            try: s.close()
            except OSError: pass
            log.warning("se perdio control_daemon: reintentando")
            self.on_link(False)

    def send(self, data: bytes) -> bool:
        with self.mutex_sock:
            s = self.sock
            if s is None:
                return False
            try:
                s.send(data)
                return True
            except OSError:
                return False


# ----------------------------------------------------------------------------------------------------------------
# [C9-semaforo] Semaforo POSIX con nombre (sem_open) usado desde Python con ctypes
# ----------------------------------------------------------------------------------------------------------------
class _Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


class Sem:
    def __init__(self, name: str, create: bool, value: int = 1):
        self._libc = ctypes.CDLL(None, use_errno=True)
        L = self._libc
        L.sem_open.restype = ctypes.c_void_p
        L.sem_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
        L.sem_timedwait.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Timespec)]
        L.sem_post.argtypes = [ctypes.c_void_p]
        L.sem_close.argtypes = [ctypes.c_void_p]
        self.name = name.encode()
        if create:
            try:
                L.sem_unlink(self.name)                  # empieza limpio: un duenio muerto pudo dejarlo en 0
            except Exception:                            # noqa: BLE001
                pass
        h = L.sem_open(self.name, os.O_CREAT, 0o660, value)
        if h in (None, ctypes.c_void_p(-1).value):
            raise OSError(ctypes.get_errno(), "sem_open")
        self.h = h

    def wait(self, timeout_s: float) -> bool:
        """sem_wait con plazo: si el duenio murio con el semaforo tomado (kill -9) el lector NO se queda bloqueado."""
        ts = _Timespec()
        t = time.time() + timeout_s                      # sem_timedwait usa CLOCK_REALTIME absoluto
        ts.tv_sec, ts.tv_nsec = int(t), int((t % 1) * 1e9)
        return self._libc.sem_timedwait(self.h, ctypes.byref(ts)) == 0

    def post(self) -> None:
        self._libc.sem_post(self.h)

    def close(self) -> None:
        self._libc.sem_close(self.h)


# ----------------------------------------------------------------------------------------------------------------
# [C11-shm] Memoria compartida /dev/shm/pb_status (128 bytes, usa 58) + [C9-seqlock]
# ----------------------------------------------------------------------------------------------------------------
SHM_FMT = "<4sHHIQHHhIffHH16s"          # [C20-tipos] 58 bytes sin padding ("<"); en C seria struct __attribute__((packed))          # magic, version, flags, seq, t_ms, pot, ldr, dist, dist_seq, temp_c, cpu_c, ram_used, ram_total, ip
SHM_USED = struct.calcsize(SHM_FMT)     # 58
SHM_SIZE = 128
FL_SIM, FL_BTN_HW, FL_SPI_HW, FL_UART_HW, FL_UART_ALIVE, FL_BMP, FL_OLED, FL_ALERT = (1 << i for i in range(8))
_NAN = float("nan")


def now_ms() -> int:
    return time.monotonic_ns() // 1_000_000              # CLOCK_MONOTONIC es comun a todos los procesos


class SharedStatus:
    def __init__(self, writer: bool, path: str = C.SHM_PATH, sem_name: str = C.SEM_NAME):
        self.writer, self.path, self.sem_name = writer, path, sem_name
        flags = os.O_RDWR | (os.O_CREAT if writer else 0)
        fd = os.open(path, flags, 0o664)
        try:
            if writer:
                os.ftruncate(fd, SHM_SIZE)
            self.mm = mmap.mmap(fd, SHM_SIZE)
        finally:
            os.close(fd)
        self.sem = Sem(sem_name, create=writer, value=1)
        self._seq = 0
        self._slow = False                               # el ultimo sem_wait vencio: no volver a esperar 20 ms por llamada
        if writer:
            self.mm[:SHM_SIZE] = bytes(SHM_SIZE)

    def publish(self, flags: int, pot: int, ldr: int, dist: Optional[int], dist_seq: int,
                temp_c: Optional[float], cpu_c: Optional[float], ram_used: int, ram_total: int, ip: str) -> None:
        """Escritor (control_daemon). Seqlock: seq impar = escribiendo; el lector descarta lecturas impares o desgarradas."""
        got = self.sem.wait(0.05)                        # [C9-semaforo] exclusion mutua con los lectores
        self._seq += 1
        struct.pack_into("<I", self.mm, 8, self._seq)    # seq impar
        struct.pack_into(SHM_FMT, self.mm, 0, b"PBST", 1, flags, self._seq, now_ms(), pot, ldr,
                         -1 if dist is None else int(dist), dist_seq & 0xFFFFFFFF,
                         _NAN if temp_c is None else temp_c, _NAN if cpu_c is None else cpu_c,
                         ram_used & 0xFFFF, ram_total & 0xFFFF, ip.encode()[:16])
        self._seq += 1
        struct.pack_into("<I", self.mm, 8, self._seq)    # seq par = valido
        self.sem.post()                                  # si no lo obtuvimos, el duenio anterior murio tomado: lo reparamos

    def snapshot(self) -> Optional[dict]:
        """Lector (vision_gui). Devuelve None si no hay datos validos todavia."""
        for _ in range(4):
            got = self.sem.wait(0.001 if self._slow else 0.02)
            self._slow = not got
            raw = bytes(self.mm[:SHM_USED])
            if got:
                self.sem.post()
            magic, ver, fl, seq, t_ms, pot, ldr, dist, dseq, temp, cpu, ru, rt, ip = struct.unpack(SHM_FMT, raw)
            if magic != b"PBST":
                return None
            if seq & 1:                                  # el escritor estaba a medias: reintenta
                continue
            if struct.unpack_from("<I", self.mm, 8)[0] != seq:
                continue                                 # cambio durante la lectura: reintenta
            return {"flags": fl, "seq": seq, "t_ms": t_ms, "pot": pot, "ldr": ldr, "dist": None if dist < 0 else dist,
                    "dist_seq": dseq, "temp_c": None if math.isnan(temp) else round(temp, 1),
                    "cpu_c": None if math.isnan(cpu) else round(cpu, 1), "ram_used": ru, "ram_total": rt,
                    "ip": ip.rstrip(b"\0").decode(errors="replace")}
        return None

    def close(self) -> None:
        try: self.mm.close()
        except Exception: pass                           # noqa: BLE001
        try: self.sem.close()
        except Exception: pass                           # noqa: BLE001
