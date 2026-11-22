"""Perro guardian (watchdog) de systemd para los procesos de El Fotobut (clase 22).

Restart=always solo revive un proceso que MUERE. Si un proceso se queda colgado (lazo infinito, camara que no responde,
bus I2C trabado) sigue existiendo y nadie lo reinicia. Con WatchdogSec= en la unidad, systemd espera una "senal de vida"
(WATCHDOG=1) cada cierto tiempo; si deja de llegar, mata el proceso y lo levanta de nuevo.

Aqui la senal de vida NO se manda a ciegas: cada proceso registra pruebas (por ejemplo "el hilo de la maquina de estados
dio una vuelta hace menos de 8 s") y solo si todas pasan se avisa a systemd. Sin systemd (simulador) no hace nada.
Se usa el protocolo sd_notify directamente (un datagrama al socket Unix de $NOTIFY_SOCKET): no requiere bibliotecas.
"""
from __future__ import annotations
import logging, os, socket, threading, time

log = logging.getLogger("fotobut.vigia")


def notificar(msg: str) -> bool:
    """Manda un mensaje sd_notify (READY=1, WATCHDOG=1, STATUS=...). False si no corremos bajo systemd."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    if addr[0] == "@":                                   # socket abstracto
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.sendto(msg.encode(), addr)
        return True
    except OSError as e:
        log.warning("sd_notify fallo: %s", e)
        return False


class Latido:
    """Marca de vida de un hilo: el hilo llama a .toc() en cada vuelta; el vigia pregunta hace cuanto fue la ultima."""
    def __init__(self) -> None:
        self.t = time.monotonic()

    def toc(self) -> None:
        self.t = time.monotonic()

    def edad(self) -> float:
        return time.monotonic() - self.t


class Vigia(threading.Thread):
    """Hilo H_vigia: cada periodo revisa las pruebas y, si todas pasan, manda WATCHDOG=1.
    pruebas: {nombre: funcion() -> True si esta sano}. gracia_s: tiempo de arranque en el que se avisa sin revisar."""
    def __init__(self, nombre: str, pruebas: dict, gracia_s: float = 30.0):
        super().__init__(daemon=True, name="H_vigia")
        self.nombre, self.pruebas, self.gracia_s = nombre, pruebas, gracia_s
        usec = int(os.environ.get("WATCHDOG_USEC", "0") or 0)
        self.periodo = max(1.0, usec / 2_000_000) if usec else 5.0   # la mitad del plazo que fija WatchdogSec
        self.activo = bool(os.environ.get("NOTIFY_SOCKET"))
        self.fallo: str | None = None
        self._t0 = time.monotonic()

    def revisar(self) -> str | None:
        """Nombre de la primera prueba que falla (None = todo sano)."""
        for nombre, fn in self.pruebas.items():
            try:
                if not fn():
                    return nombre
            except Exception as e:                       # noqa: BLE001
                return f"{nombre} ({e})"
        return None

    def run(self) -> None:
        notificar("READY=1")
        while True:
            malo = None if time.monotonic() - self._t0 < self.gracia_s else self.revisar()
            if malo is None:
                if self.fallo:
                    log.warning("VIGIA %s: '%s' se recupero", self.nombre, self.fallo)
                self.fallo = None
                notificar("WATCHDOG=1")
            elif malo != self.fallo:                     # se deja de avisar: systemd reiniciara el proceso al vencer el plazo
                self.fallo = malo
                log.error("VIGIA %s: '%s' no responde; dejo de mandar la senal de vida para que systemd reinicie el proceso",
                          self.nombre, malo)
                notificar(f"STATUS=colgado: {malo}")
            time.sleep(self.periodo)
