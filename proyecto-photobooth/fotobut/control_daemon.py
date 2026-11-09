#!/usr/bin/env python3
"""PROCESO 1 · control_daemon: dueno del hardware (boton GPIO17, MCP3008 por SPI, STM32 por UART, buzzer PWM, BMP280 y OLED por I2C).

Hilos (clases 8 y 9):
  H_boton    SCHED_FIFO 80   antirrebote 20 ms y aviso inmediato a vision_gui           (dentro de PiHAL)
  H_sensores nice -5         muestrea pot/LDR/distancia a 20 Hz y publica en memoria compartida
  H_oled     nice +10        1 Hz: lee el BMP280 y dibuja el OLED (mutex_i2c)
  H_socket   nice 0          atiende a vision_gui: ordenes (beep, simulador, estado para el OLED, ping)
Recursos compartidos: estado_cabina (mutex_estado), bus I2C (mutex_i2c), socket de salida (mutex_sock), shm (semaforo POSIX).
"""
from __future__ import annotations
import argparse, logging, signal, threading, time

from . import config as C
from . import ipc
from .sched import set_prio

log = logging.getLogger("fotobut.control")


class EstadoCabina:
    """struct estado_cabina del Avance 1 (clase 9): lo escriben H_sensores y H_oled, lo lee H_socket/H_oled."""
    def __init__(self):
        self.mutex_estado = threading.Lock()             # [C9-mutex_estado] protege TODOS los campos de abajo
        self.pot = 512
        self.ldr = 512
        self.dist: int | None = None
        self.dist_seq = 0
        self.uart_alive = False
        self.temp_c: float | None = None
        self.cpu_c: float | None = None
        self.ram_used = self.ram_total = 0
        self.ip = ""
        self.alert = False
        self.bmp_ok = self.oled_ok = False
        self.v_state, self.v_shot, self.v_sessions = "ATTRACT", 0, 0   # estado de vision_gui (para el OLED)


class ControlDaemon:
    def __init__(self, sim: bool):
        self.sim = sim
        self.est = EstadoCabina()
        self.mutex_i2c = threading.Lock()                # [C9-mutex_i2c]
        self.stop = False
        if sim:
            from .hal import SimHAL
            self.hal = SimHAL()
        else:
            from .hal import PiHAL
            self.hal = PiHAL()
        self.hal.on_press = self._on_press
        self.shm = ipc.SharedStatus(writer=True)
        self.srv = ipc.ControlServer(C.SOCK_PATH, self._on_command, self._hello_flags)
        self.bmp = self.oled = None
        if not sim:
            self._open_i2c()

    # ---------- hardware ----------
    def _open_i2c(self) -> None:
        try:
            from .i2c import I2CBus, BMP280, SSD1306
            bus = I2CBus(C.I2C_BUS)
            for name, mk in (("BMP280", lambda: BMP280(bus, C.BMP_ADDR)), ("OLED", lambda: SSD1306(bus, C.OLED_ADDR))):
                try:
                    obj = mk()
                    if name == "BMP280": self.bmp = obj
                    else: self.oled = obj
                except Exception as e:                   # noqa: BLE001
                    log.warning("%s no disponible: %s", name, e)
        except Exception as e:                           # noqa: BLE001
            log.warning("I2C no disponible: %s", e)

    def _hello_flags(self) -> int:
        st = self.hal.status()
        f = ipc.FL_SIM if self.sim else 0
        return f | (ipc.FL_BTN_HW if st.get("button") else 0) | (ipc.FL_SPI_HW if st.get("spi") else 0) | (ipc.FL_UART_HW if st.get("uart") else 0)

    # ---------- boton: lo llama H_boton al validar la pulsacion ----------
    def _on_press(self, t_ns: int, debounce_ms: int) -> None:
        self.srv.send(ipc.pack(ipc.EV_BUTTON, a=debounce_ms, ref_ns=t_ns))   # [C11-socket] evento al instante, sin esperar el muestreo

    # ---------- ordenes de vision_gui ----------
    def _on_command(self, m: dict, srv: ipc.ControlServer) -> None:
        t = m["type"]
        if t == ipc.CMD_BEEP:
            self.hal.beep(m["a"], m["b"], m["ref_ns"], int(m["flags"]))
        elif t == ipc.CMD_PING:
            srv.send(ipc.pack(ipc.EV_PONG, ref_ns=m["ref_ns"]))
        elif t == ipc.CMD_STATE:
            try:
                state, shot, ses = m["payload"].decode().split("|")
                with self.est.mutex_estado:              # [C9-mutex_estado]
                    self.est.v_state, self.est.v_shot, self.est.v_sessions = state, int(shot), int(ses)
            except Exception:                            # noqa: BLE001
                pass
        elif t == ipc.CMD_SIM and self.sim:
            f = m["flags"]
            self.hal.sim_set(button=bool(f & ipc.F_SIM_BUTTON), pot=m["a"] if f & ipc.F_SIM_POT else None,
                             distance=(None if f & ipc.F_SIM_NODIST else m["b"]) if f & (ipc.F_SIM_DIST | ipc.F_SIM_NODIST) else "keep")

    # ---------- hilos ----------
    def h_sensores(self, hz: int = 20) -> None:
        set_prio("H_sensores", nice=-5)                  # [C8-T3] muestreo SPI del potenciometro/LDR (periodo 50 ms)
        nxt = time.monotonic()
        while not self.stop:
            inp = self.hal.read()
            with self.est.mutex_estado:                  # [C9-mutex_estado] una sola escritura coherente del struct
                e = self.est
                e.pot, e.ldr, e.dist, e.dist_seq, e.uart_alive = inp.pot, inp.ldr, inp.distance, inp.dist_seq, inp.uart_ok
                fl = ((ipc.FL_SIM if self.sim else 0) | (ipc.FL_UART_ALIVE if e.uart_alive else 0) | (ipc.FL_BMP if e.bmp_ok else 0)
                      | (ipc.FL_OLED if e.oled_ok else 0) | (ipc.FL_ALERT if e.alert else 0) | self._hello_flags() & ~ipc.FL_SIM)
                args = (fl, e.pot, e.ldr, e.dist, e.dist_seq, e.temp_c, e.cpu_c, e.ram_used, e.ram_total, e.ip)
            self.shm.publish(*args)                      # [C11-shm] fuera del mutex_estado: el semaforo ya serializa a los lectores
            nxt += 1.0 / hz
            time.sleep(max(0.0, nxt - time.monotonic()))
            if nxt < time.monotonic() - 1:               # nos atrasamos mucho (suspension): reanclar
                nxt = time.monotonic()

    def _get_snap(self) -> dict:
        with self.est.mutex_estado:
            return {"state": self.est.v_state, "shot": self.est.v_shot, "distance": self.est.dist, "sessions": self.est.v_sessions}

    def _on_info(self, info: dict) -> None:
        with self.est.mutex_estado:                      # [C9-mutex_estado]
            e = self.est
            e.temp_c, e.cpu_c, e.ram_used, e.ram_total = info["temp_c"], info["cpu_c"], info["ram_used"] or 0, info["ram_total"] or 0
            e.ip, e.alert, e.bmp_ok, e.oled_ok = info["ip"], info["alert"], info["bmp_ok"], info["oled_ok"]

    def run(self) -> None:
        from .telemetry import Telemetry
        Telemetry(self._get_snap, self._on_info, self.bmp, self.oled, sim=self.sim, mutex_i2c=self.mutex_i2c).start()
        threading.Thread(target=self.srv.serve_forever, name="H_socket", daemon=True).start()
        log.info("control_daemon listo (sim=%s) socket=%s shm=%s", self.sim, C.SOCK_PATH, C.SHM_PATH)
        self.h_sensores()

    def close(self) -> None:
        self.stop = True
        self.hal.close()
        self.shm.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s control: %(message)s")
    d = ControlDaemon(a.sim)
    signal.signal(signal.SIGTERM, lambda *_: (d.close(), raise_exit()))
    try:
        d.run()
    except KeyboardInterrupt:
        pass
    finally:
        d.close()


def raise_exit():
    raise SystemExit(0)


if __name__ == "__main__":
    main()
