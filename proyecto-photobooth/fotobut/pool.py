"""Pool estatico de 3 bloques de foto Full HD (clase 10) con productor-consumidor y semaforos (clase 9).

  Productor: hilo de la maquina de estados (H_maquina/H_captura) -> put()  tras cada foto
  Consumidor: H_compositor -> get() x3 -> arma la tira -> release()        (duerme en sem_llenos: 0 % de CPU)
Los 3 bloques se reservan UNA vez al arrancar (6,220,800 bytes c/u): sin malloc/free por sesion y sin fragmentacion.
"""
from __future__ import annotations
import logging, threading
import numpy as np
from PIL import Image

from . import config as C

log = logging.getLogger("fotobut.pool")
SLOT_BYTES = C.CAP_W * C.CAP_H * 3                # [C20-tipos] 1920*1080*3 = 6,220,800 bytes por bloque (uint8: 1 byte por canal)


class FramePool:
    def __init__(self, n: int = C.SHOTS):
        self.n = n
        self.slots = [np.zeros((C.CAP_H, C.CAP_W, 3), np.uint8) for _ in range(n)]      # [C10-pool] reservado al arrancar
        self.meta: list = [None] * n
        self.sem_libres = threading.Semaphore(n)         # [C9-sem_libres] bloques disponibles (inicia en 3)
        self.sem_llenos = threading.Semaphore(0)         # [C9-sem_llenos] bloques con foto (inicia en 0)
        self.mutex_pool = threading.Lock()               # [C9-mutex_pool] protege los indices cabeza/cola
        self._head = self._tail = 0

    def put(self, img: Image.Image, meta, timeout: float = 5.0) -> int:
        """Productor. Bloquea si los 3 bloques estan ocupados (compositor atrasado)."""
        if not self.sem_libres.acquire(timeout=timeout):
            raise TimeoutError("pool lleno: el compositor no libero bloques")
        with self.mutex_pool:
            i, self._head = self._head, (self._head + 1) % self.n
        if img.size != (C.CAP_W, C.CAP_H):
            img = img.resize((C.CAP_W, C.CAP_H))
        np.copyto(self.slots[i], np.asarray(img.convert("RGB")))
        self.meta[i] = meta
        self.sem_llenos.release()
        return i

    def put_marker(self, timeout: float = 1.0) -> bool:
        """Marca de "sesion cancelada" (boton de reset): ocupa un bloque sin copiar imagen (meta = None) para despertar al
        consumidor, que al verla libera las fotos que ya tenia. Sigue el mismo protocolo de semaforos que put()."""
        if not self.sem_libres.acquire(timeout=timeout):
            return False
        with self.mutex_pool:
            i, self._head = self._head, (self._head + 1) % self.n
        self.meta[i] = None
        self.sem_llenos.release()
        return True

    def get(self):
        """Consumidor. Duerme hasta que haya una foto completa: jamas lee un bloque a medio escribir."""
        self.sem_llenos.acquire()
        with self.mutex_pool:
            i, self._tail = self._tail, (self._tail + 1) % self.n
        return i, self.slots[i], self.meta[i]

    def release(self, i: int) -> None:
        self.sem_libres.release()

    def reset(self) -> None:
        """Recuperacion ante un productor/consumidor atascado: devuelve el pool a su estado inicial."""
        with self.mutex_pool:
            self.sem_libres = threading.Semaphore(self.n)
            self.sem_llenos = threading.Semaphore(0)
            self._head = self._tail = 0
        log.warning("pool reiniciado")
