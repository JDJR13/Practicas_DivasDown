"""Telemetria a 1 Hz: temperatura (BMP280 + CPU), memoria, IP, sesiones -> OLED y /oled.png."""
from __future__ import annotations
import logging, math, threading, time

from . import config as C
from .oled import render, local_ip

log = logging.getLogger("fotobut.telemetry")
TEMP_ALERT_C = 65.0


def _cpu_temp() -> float | None:
    try:
        return int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000.0
    except Exception:                                    # noqa: BLE001
        return None


def _mem_mb() -> tuple[int | None, int | None]:
    try:
        m = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}
        return (m["MemTotal"] - m["MemAvailable"]) // 1024, m["MemTotal"] // 1024
    except Exception:                                    # noqa: BLE001
        return None, None


class Telemetry(threading.Thread):
    """Hilo H_oled (T5 del Avance 1, nice +10). Vive en control_daemon porque es el dueno del bus I2C.
    get_snap() -> dict con state/shot/distance/sessions (los manda vision_gui por el socket); on_info(info) publica el resultado."""
    def __init__(self, get_snap, on_info, bmp=None, oled=None, sim=False, mutex_i2c=None):
        super().__init__(daemon=True, name="H_oled")
        self.get_snap, self.on_info, self.bmp, self.oled, self.sim = get_snap, on_info, bmp, oled, sim
        self.mutex_i2c = mutex_i2c or threading.Lock()   # [C9-mutex_i2c] BMP280 y OLED comparten /dev/i2c-1
        self.png = C.TMP_DIR / "oled.png"
        self.ip, self._ip_t = "sin red", 0.0

    def run(self) -> None:
        from .sched import set_prio
        set_prio("H_oled", nice=10)                      # [C8-T5]
        C.TMP_DIR.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self.tick()
            except Exception:                            # noqa: BLE001
                log.exception("telemetria")
            time.sleep(1.0)

    def tick(self) -> None:
        t0 = time.time()
        temp = None
        if self.sim:
            temp = 31.4 + 0.4 * math.sin(t0 / 7)
        elif self.bmp:
            try:
                with self.mutex_i2c:                     # [C9-mutex_i2c] una transaccion I2C a la vez
                    temp = self.bmp.temperature_c()
            except Exception as e:                       # noqa: BLE001
                log.warning("BMP280: %s", e)
        cpu = (46.0 + 3 * math.sin(t0 / 11)) if self.sim else _cpu_temp()
        ru, rt = _mem_mb()
        if time.monotonic() - self._ip_t > 15:
            self.ip, self._ip_t = local_ip(), time.monotonic()
        snap = self.get_snap()
        info = {"state": snap["state"], "shot": snap["shot"], "temp_c": temp, "cpu_c": cpu, "dist": snap["distance"],
                "sessions": snap["sessions"], "ram_used": ru, "ram_total": rt, "ip": self.ip,
                "alert": temp is not None and temp > TEMP_ALERT_C}
        img = render(info)
        img.convert("RGB").resize((512, 256), 0).save(self.png)
        if self.oled:
            try:
                with self.mutex_i2c:
                    self.oled.show(img)
            except Exception as e:                       # noqa: BLE001
                log.warning("OLED: %s", e)
        info["bmp_ok"], info["oled_ok"] = bool(self.sim or self.bmp), bool(self.sim or self.oled)
        self.on_info(info)
