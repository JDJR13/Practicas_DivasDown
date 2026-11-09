"""RemoteHAL: lo que ve vision_gui del hardware. Misma interfaz que SimHAL/PiHAL (read, beep, status, sim_set), pero los datos
llegan por IPC: pot/LDR/distancia/temperatura por MEMORIA COMPARTIDA y el boton por SOCKET AF_UNIX (clase 11)."""
from __future__ import annotations
import logging, threading, time
from typing import Optional

from . import config as C
from . import ipc
from .hal import Inputs

log = logging.getLogger("fotobut.remote_hal")


class RemoteHAL:
    def __init__(self, sim: bool = False):
        self.is_sim = sim
        self._lock = threading.Lock()                    # [C9-mutex_estado] protege presses/ultimo boton entre H_ipc_rx y la maquina
        self._presses = self._resets = 0
        self.last_edge = (0, 0)                          # (ref_ns, ms de antirrebote) de la ultima pulsacion
        self.on_button = None                            # callback: despierta la maquina de estados al instante
        self.link = False
        self.hello_flags = 0
        self.rtt_us: list[float] = []
        self._shm: Optional[ipc.SharedStatus] = None
        self._tel: dict = {}
        self.client = ipc.ControlClient(C.SOCK_PATH, self._on_msg, self._on_link)
        threading.Thread(target=self.client.run, name="H_ipc_rx", daemon=True).start()

    # ---------- eventos del socket ----------
    def _on_msg(self, m: dict) -> None:
        t = m["type"]
        if t == ipc.EV_BUTTON:
            with self._lock:
                self._presses += 1
                self.last_edge = (m["ref_ns"], m["a"])
            if self.on_button:
                self.on_button()
        elif t == ipc.EV_RESET:                          # boton azul: la maquina cancela la sesion y vuelve al inicio
            with self._lock:
                self._resets += 1
            if self.on_button:
                self.on_button()
        elif t == ipc.EV_HELLO:
            self.hello_flags = m["flags"]
            self.is_sim = bool(m["flags"] & ipc.FL_SIM)
        elif t == ipc.EV_PONG:
            self.rtt_us.append((time.monotonic_ns() - m["ref_ns"]) / 1e3)
            self.rtt_us = self.rtt_us[-1000:]

    def _on_link(self, up: bool) -> None:
        self.link = up
        if up:
            self._close_shm()                            # control_daemon pudo reiniciar: reabrir shm y semaforo (objeto nuevo)
        if self.on_button:
            self.on_button()

    def _close_shm(self) -> None:
        if self._shm:
            self._shm.close()
            self._shm = None

    # ---------- interfaz HAL ----------
    def _snap(self) -> Optional[dict]:
        if self._shm is None:
            try:
                self._shm = ipc.SharedStatus(writer=False)
            except OSError:
                return None
        return self._shm.snapshot()

    def read(self) -> Inputs:
        s = self._snap()
        with self._lock:
            p, self._presses = self._presses, 0
            r, self._resets = self._resets, 0
        fresh = bool(s) and self.link and (ipc.now_ms() - s["t_ms"]) < 1000     # datos viejos = control_daemon colgado
        if not fresh:
            self._tel = {}
            return Inputs(p, 512, 512, None, 0, False, r)
        fl = s["flags"]
        self._tel = {"temp_c": s["temp_c"], "cpu_c": s["cpu_c"], "ram_used": s["ram_used"], "ram_total": s["ram_total"], "ip": s["ip"],
                     "alert": bool(fl & ipc.FL_ALERT), "bmp_ok": bool(fl & ipc.FL_BMP), "oled_ok": bool(fl & ipc.FL_OLED)}
        return Inputs(p, s["pot"], s["ldr"], s["dist"], s["dist_seq"], bool(fl & ipc.FL_UART_ALIVE), r)

    def telemetry(self) -> dict:
        return self._tel

    def beep(self, freq_hz: int, ms: int, ref_ns: int = 0, debounce_ms: int = 0) -> None:
        self.client.send(ipc.pack(ipc.CMD_BEEP, flags=min(255, debounce_ms), a=freq_hz, b=ms, ref_ns=ref_ns))

    def notify_state(self, state: str, shot: int, sessions: int) -> None:
        self.client.send(ipc.pack(ipc.CMD_STATE, payload=f"{state}|{shot}|{sessions}".encode()))

    def ping(self) -> None:
        self.client.send(ipc.pack(ipc.CMD_PING, ref_ns=time.monotonic_ns()))

    def sim_set(self, button: bool = False, pot: Optional[int] = None, distance="keep", reset: bool = False) -> None:
        fl = (ipc.F_SIM_BUTTON if button else 0) | (ipc.F_SIM_POT if pot is not None else 0) | (ipc.F_SIM_RESET if reset else 0)
        b = 0
        if distance != "keep":
            if distance is None: fl |= ipc.F_SIM_NODIST
            else: fl |= ipc.F_SIM_DIST; b = int(distance)
        self.client.send(ipc.pack(ipc.CMD_SIM, flags=fl, a=int(pot or 0), b=b))

    def status(self) -> dict:
        f = self.hello_flags
        return {"link": self.link, "button": bool(f & ipc.FL_BTN_HW) or self.is_sim, "spi": bool(f & ipc.FL_SPI_HW) or self.is_sim,
                "uart": bool(f & ipc.FL_UART_HW) or self.is_sim}

    def close(self) -> None:
        self._close_shm()
