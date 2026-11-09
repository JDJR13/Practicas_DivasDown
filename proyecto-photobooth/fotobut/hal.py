"""Capa de hardware (HAL). SimHAL para desarrollar sin cabina; PiHAL para la Raspberry Pi 4.

Interfaz comun:  read() -> Inputs;  beep(freq_hz, ms);  close()
"""
from __future__ import annotations
import os, re, threading, time, random, logging
from dataclasses import dataclass
from typing import Optional

from . import config as C
from .sched import set_prio, name_thread

log = logging.getLogger("fotobut.hal")


@dataclass
class Inputs:
    button_presses: int = 0          # pulsaciones nuevas desde la ultima lectura
    pot: int = 512                   # MCP3008 CH0, 0-1023
    ldr: int = 512                   # MCP3008 CH1, 0-1023
    distance: Optional[int] = None   # cm (None = sin dato / ERR)
    dist_seq: int = 0                # aumenta con cada muestra nueva de distancia
    uart_ok: bool = False            # llego alguna trama del STM32 recientemente
    reset_presses: int = 0           # pulsaciones nuevas del boton azul (reset)


class SimHAL:
    """Simulador: el navegador (teclado o /api/sim) mueve el boton, el potenciometro y la distancia."""
    is_sim = True

    def __init__(self):
        self._lock = threading.Lock()
        self._presses = self._resets = 0
        self._pot = 100
        self._dist: Optional[int] = None      # None = nadie enfrente
        self._seq, self._last_sample = 0, 0.0
        self.beeps: list[tuple[int, int]] = []
        self.on_press = None                  # callback(t_ns, ms_antirrebote): control_daemon lo usa para avisar de inmediato
        self.on_reset = None                  # igual, para el boton azul

    def sim_set(self, button: bool = False, pot: Optional[int] = None, distance="keep", reset: bool = False) -> None:
        if button and self.on_press:
            self.on_press(time.monotonic_ns(), 0)
        if reset and self.on_reset:
            self.on_reset(time.monotonic_ns(), 0)
        with self._lock:
            if button:
                self._presses += 1
            if reset:
                self._resets += 1
            if pot is not None:
                self._pot = max(0, min(1023, int(pot)))
            if distance != "keep":
                self._dist = None if distance is None else int(distance)

    def read(self) -> Inputs:
        with self._lock:
            now = time.monotonic()
            if now - self._last_sample >= 0.1:                # 10 Hz como el STM32
                self._last_sample, self._seq = now, self._seq + 1
            d = self._dist
            if d is not None:
                d = max(2, d + random.choice((-1, 0, 0, 1)))
            p, self._presses = self._presses, 0
            r, self._resets = self._resets, 0
            return Inputs(p, self._pot, 600, d, self._seq, True, r)

    def beep(self, freq_hz: int, ms: int, ref_ns: int = 0, debounce_ms: int = 0) -> None:
        self.beeps.append((freq_hz, ms))
        self.beeps = self.beeps[-20:]
        if ref_ns:
            log.info("MEDICION latencia_boton_tono ms=%.3f desde_flanco_ms=%.3f",
                     (time.monotonic_ns() - ref_ns) / 1e6, (time.monotonic_ns() - ref_ns) / 1e6 + debounce_ms)

    def status(self) -> dict:
        return {"button": True, "reset": True, "spi": True, "uart": True}

    def close(self) -> None:
        pass


class PiHAL:
    """Hardware real. Cada dispositivo falla de forma independiente (queda sin dato) para no tumbar la interfaz.
    Botones (rojo y azul): lgpio (o /dev/gpiomem como en tu P7) · potenciometro/LDR: spidev · STM32: pyserial · buzzer: PWM0."""
    is_sim = False
    DEBOUNCE_S = 0.02

    def __init__(self):
        self._presses, self._lock = 0, threading.Lock()
        self._resets = 0
        self._dist: Optional[int] = None
        self._seq, self._last_frame = 0, 0.0
        self._stop = False
        self._spi = self._ser = None
        self._read_pin = None                 # lector del boton rojo (GPIO17)
        self._read_reset = None               # lector del boton azul (GPIO27)
        self._beep_lock = threading.Lock()
        self.on_press = None                  # callback(t_ns, ms_antirrebote)
        self.on_reset = None                  # callback(t_ns, ms_antirrebote) del boton azul
        self._lg = self._lg_h = self._mem = None
        self._setup_button()
        self._pwm_prepare()                   # exporta el PWM del buzzer al arrancar (la 1a vez tarda ~100 ms y ensuciaba la latencia)
        try:
            import spidev
            self._spi = spidev.SpiDev()
            self._spi.open(C.SPI_BUS, C.SPI_DEV)
            self._spi.max_speed_hz, self._spi.mode = 1_000_000, 0
        except Exception as e:                       # noqa: BLE001
            log.warning("MCP3008 (SPI) no disponible: %s", e)
            self._spi = None
        try:
            import serial
            self._ser = serial.Serial(C.UART_PORT, C.UART_BAUD, timeout=0.1)
            threading.Thread(target=self._uart_loop, daemon=True).start()
        except Exception as e:                       # noqa: BLE001
            log.warning("UART %s no disponible: %s", C.UART_PORT, e)

    # ---------- botones arcade: rojo GPIO17 (foto) y azul GPIO27 (reset); pull-up interna, activos en bajo ----------
    def _setup_button(self) -> None:
        """[C21-boton] Driver del kernel: gpio-bcm2835 -> /dev/gpiochip0; se usa por lgpio (ioctl del chardev) o /dev/gpiomem (mmap)."""
        self._read_pin = self._claim_input(C.GPIO_BUTTON, "Boton")
        self._read_reset = self._claim_input(C.GPIO_RESET, "Reset")
        if self._read_pin or self._read_reset:
            threading.Thread(target=self._button_loop, daemon=True).start()

    def _claim_input(self, pin: int, name: str):
        """Reclama un pin como entrada con pull-up y devuelve la funcion que lee su nivel (None si no se pudo)."""
        try:
            if self._lg is None:
                os.environ.setdefault("LG_WD", "/tmp")   # lgpio crea sus pipes en este directorio (con ProtectHome no puede ser el home)
                import lgpio
                self._lg_h = lgpio.gpiochip_open(0)
                self._lg = lgpio
            lg, h = self._lg, self._lg_h
            lg.gpio_claim_input(h, pin, lg.SET_PULL_UP)
            log.info("%s GPIO%d via lgpio", name, pin)
            return lambda: lg.gpio_read(h, pin)
        except Exception as e:                       # noqa: BLE001
            log.warning("lgpio no disponible para GPIO%d (%s); uso /dev/gpiomem como en la P7", pin, e)
        try:
            import mmap, struct
            if self._mem is None:
                fd = os.open("/dev/gpiomem", os.O_RDWR | os.O_SYNC)
                self._mem = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
                os.close(fd)
            mm = self._mem
            reg, sh = 4 * (pin // 10), (pin % 10) * 3                          # GPFSELn: entrada = 000
            v = struct.unpack_from("<I", mm, reg)[0] & ~(7 << sh)
            struct.pack_into("<I", mm, reg, v)
            preg, psh = 0xE4 + 4 * (pin // 16), (pin % 16) * 2                 # BCM2711: pull-up = 01
            v = (struct.unpack_from("<I", mm, preg)[0] & ~(3 << psh)) | (1 << psh)
            struct.pack_into("<I", mm, preg, v)
            return lambda: (struct.unpack_from("<I", mm, 0x34)[0] >> pin) & 1
        except Exception as e2:                      # noqa: BLE001
            log.error("%s GPIO%d no disponible: %s", name, pin, e2)
            return None

    def _button_loop(self) -> None:
        """Hilo H_boton (T1 del Avance 1): SCHED_FIFO 80. Antirrebote por software de 20 ms; al validar la pulsacion avisa
        DE INMEDIATO por el callback (no espera al muestreo de 20 Hz) para cumplir latencia boton->tono <= 15 ms.
        El mismo sondeo de 4 ms atiende los dos botones (rojo = foto, azul = reset), cada uno con su antirrebote."""
        set_prio("H_boton", fifo=80)                                           # [C8-T1]
        pressed = 0 if C.BUTTON_ACTIVE_LOW else 1
        btns = []                                                              # [lector, tipo, candidato, estable, t0]
        for rd, kind in ((self._read_pin, "press"), (self._read_reset, "reset")):
            if rd:
                lvl = rd()
                btns.append([rd, kind, lvl, lvl, 0.0])
        while not self._stop:
            now = time.monotonic()
            for b in btns:
                lvl = b[0]()
                if lvl != b[2]:
                    b[2], b[4] = lvl, now
                elif lvl != b[3] and now - b[4] >= self.DEBOUNCE_S:
                    b[3] = lvl
                    if lvl == pressed:
                        self._fire(b[1], now - b[4])
            time.sleep(0.004)

    def _fire(self, kind: str, held_s: float) -> None:
        """Pulsacion validada: la cuenta y avisa al instante a control_daemon (que la manda por el socket)."""
        with self._lock:
            if kind == "reset":
                self._resets += 1
            else:
                self._presses += 1
        cb = self.on_reset if kind == "reset" else self.on_press
        if cb:
            cb(time.monotonic_ns(), int(held_s * 1000))

    # ---------- MCP3008 ----------
    def _adc(self, ch: int) -> int:
        """[C21-mcp3008] Driver spi-bcm2835 + spidev -> /dev/spidev0.0; una transferencia SPI_IOC_MESSAGE de 3 bytes por canal."""
        if not self._spi:
            return 512
        try:
            r = self._spi.xfer2([1, (8 + ch) << 4, 0])
            return ((r[1] & 3) << 8) | r[2]
        except Exception:                            # noqa: BLE001
            return 512

    # ---------- UART con el STM32:  "DIST:123 cm"  |  "DIST:ERR" ----------
    _RX = re.compile(rb"DIST:(?:(\d+) cm|ERR)")

    def _uart_loop(self) -> None:
        """[C21-uart] Driver PL011 (amba-pl011) -> /dev/ttyAMA0 (tty); 115200 8N1 con pyserial; tramas ASCII del STM32."""
        name_thread("H_uart")
        while not self._stop:
            try:
                line = self._ser.readline()
            except Exception:                        # noqa: BLE001
                time.sleep(0.5)
                continue
            m = self._RX.search(line or b"")
            if m:
                with self._lock:
                    self._dist = int(m.group(1)) if m.group(1) else None
                    self._seq += 1
                    self._last_frame = time.monotonic()

    def read(self) -> Inputs:
        with self._lock:
            p, self._presses = self._presses, 0
            r, self._resets = self._resets, 0
            d, seq = self._dist, self._seq
            ok = (time.monotonic() - self._last_frame) < 1.0
        return Inputs(p, self._adc(C.ADC_POT_CH), self._adc(C.ADC_LDR_CH), d if ok else None, seq, ok, r)

    def status(self) -> dict:
        return {"button": self._read_pin is not None, "reset": self._read_reset is not None,
                "spi": self._spi is not None, "uart": self._ser is not None}

    # ---------- buzzer en GPIO18: PWM0 por hardware (sysfs) o, si no, lgpio ----------
    def _pwm_prepare(self) -> None:
        """Exporta pwm0 una sola vez al arrancar: asi el primer pitido no paga el export + espera de 100 ms."""
        try:
            import glob
            chips = sorted(glob.glob("/sys/class/pwm/pwmchip*"))
            if chips and not os.path.exists(chips[0] + "/pwm0"):
                open(chips[0] + "/export", "w").write("0")
                time.sleep(0.1)
        except Exception as e:                       # noqa: BLE001
            log.debug("pwm_prepare: %s", e)

    def beep(self, freq_hz: int, ms: int, ref_ns: int = 0, debounce_ms: int = 0) -> None:
        threading.Thread(target=self._beep, args=(freq_hz, ms, ref_ns, debounce_ms), daemon=True).start()

    def _beep(self, freq_hz: int, ms: int, ref_ns: int = 0, debounce_ms: int = 0) -> None:
        """[C21-buzzer] Driver bcm2835-pwm (modulo pwm_bcm2835) -> /sys/class/pwm/pwmchip0/pwm0 (sysfs): periodo, duty 50 %, enable; 0 % de CPU."""
        name_thread("H_buzzer")
        with self._beep_lock:
            try:
                import glob
                chips = sorted(glob.glob("/sys/class/pwm/pwmchip*"))
                if not chips:
                    raise FileNotFoundError("sin pwmchip")
                base = chips[0]
                if not os.path.exists(base + "/pwm0"):
                    open(base + "/export", "w").write("0")
                    time.sleep(0.1)
                period = int(1e9 / freq_hz)
                w = lambda f, v: open(f"{base}/pwm0/{f}", "w").write(str(v))
                w("enable", 0); w("period", period); w("duty_cycle", period // 2); w("enable", 1)
                if ref_ns:
                    lat = (time.monotonic_ns() - ref_ns) / 1e6
                    log.info("MEDICION latencia_boton_tono ms=%.3f desde_flanco_ms=%.3f", lat, lat + debounce_ms)
                time.sleep(ms / 1000)
                w("enable", 0)
            except Exception as e:                   # noqa: BLE001
                if self._lg and self._lg_h is not None:
                    try:
                        self._lg.tx_pwm(self._lg_h, C.GPIO_BUZZER, freq_hz, 50)
                        if ref_ns:
                            lat = (time.monotonic_ns() - ref_ns) / 1e6
                            log.info("MEDICION latencia_boton_tono ms=%.3f desde_flanco_ms=%.3f", lat, lat + debounce_ms)
                        time.sleep(ms / 1000)
                        self._lg.tx_pwm(self._lg_h, C.GPIO_BUZZER, freq_hz, 0)
                        return
                    except Exception:                # noqa: BLE001
                        pass
                log.debug("buzzer: %s", e)

    def close(self) -> None:
        self._stop = True
