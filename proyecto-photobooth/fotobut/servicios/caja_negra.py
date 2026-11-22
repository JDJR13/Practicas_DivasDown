"""Caja negra de la cabina: bitacora de salud en la microSD, una linea JSON por registro (formato JSON Lines).

Dos tipos de registro:
  {"k":"m", ...}  muestra periodica (temperatura, RAM, disco, estado de cada servicio, estado de la cabina)
  {"k":"e", ...}  evento con nivel (INFO / WARN / ERROR): un reinicio, un sensor que deja de responder, bajo voltaje...
Un solo proceso escribe (monitor), asi que no hace falta candado entre procesos. Los eventos se escriben con fsync: si
la cabina se apaga de golpe, lo ultimo que paso queda en disco. Un archivo por dia; se conservan CAJA_NEGRA_DIAS dias.
"""
from __future__ import annotations
import json, logging, os, threading, time
from datetime import datetime, timedelta
from pathlib import Path

from fotobut.servicios import config as C

log = logging.getLogger("fotobut.caja")


class CajaNegra:
    def __init__(self, carpeta: Path | None = None):
        self.dir = Path(carpeta or C.ESTADO_DIR) / "caja_negra"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()                     # el hilo del panel (lee/anota reinicios) y el de muestreo
        self._n = 0
        self._revisado: Path | None = None

    def _archivo(self, dia: datetime | None = None) -> Path:
        return self.dir / f"{(dia or datetime.now()):%Y-%m-%d}.jsonl"

    def _escribir(self, reg: dict, sync: bool) -> None:
        reg = {"t": round(time.time(), 1), "h": f"{datetime.now():%Y-%m-%d %H:%M:%S}", **reg}
        with self.lock:
            try:
                arch = self._archivo()
                if arch != self._revisado:               # una vez por archivo: si un apagon dejo la ultima linea a medias,
                    self._revisado = arch                # se cierra con un salto para que no se coma el registro siguiente
                    try:
                        with open(arch, "rb") as g:
                            g.seek(-1, os.SEEK_END)
                            cortada = g.read(1) != b"\n"
                    except OSError:
                        cortada = False
                    if cortada:
                        with open(arch, "a", encoding="utf-8") as g:
                            g.write("\n")
                with open(arch, "a", encoding="utf-8") as f:
                    f.write(json.dumps(reg, ensure_ascii=False, separators=(",", ":")) + "\n")
                    self._n += 1
                    if sync or self._n % 6 == 0:         # las muestras se aseguran en disco una vez por minuto
                        f.flush()
                        os.fsync(f.fileno())
            except OSError as e:
                log.error("caja negra: no se pudo escribir (%s)", e)

    def muestra(self, datos: dict) -> None:
        self._escribir({"k": "m", **datos}, sync=False)

    def evento(self, nivel: str, texto: str, **datos) -> None:
        getattr(log, {"INFO": "info", "WARN": "warning", "ERROR": "error"}.get(nivel, "info"))("EVENTO %s", texto)
        self._escribir({"k": "e", "nivel": nivel, "txt": texto, **datos}, sync=True)

    def leer(self, horas: float = 1.0, tipo: str | None = None, maximo: int = 2000) -> list[dict]:
        """Registros de las ultimas `horas` (los mas recientes al final). Las lineas danadas se saltan."""
        desde, out = time.time() - horas * 3600, []
        dias = sorted({(datetime.now() - timedelta(days=d)).date() for d in range(int(horas // 24) + 2)})
        for d in dias:
            p = self.dir / f"{d:%Y-%m-%d}.jsonl"
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    for linea in f:
                        try:
                            r = json.loads(linea)
                        except ValueError:               # linea cortada por un apagon
                            continue
                        if isinstance(r, dict) and r.get("t", 0) >= desde and (tipo is None or r.get("k") == tipo):
                            out.append(r)
            except OSError:
                continue
        return out[-maximo:]

    def ultimo(self) -> dict | None:
        r = self.leer(horas=24 * C.CAJA_NEGRA_DIAS, maximo=1)
        return r[-1] if r else None

    def purgar(self) -> None:
        limite = f"{datetime.now() - timedelta(days=C.CAJA_NEGRA_DIAS):%Y-%m-%d}"
        for p in self.dir.glob("*.jsonl"):
            if p.stem < limite:
                try:
                    p.unlink()
                except OSError:
                    pass
