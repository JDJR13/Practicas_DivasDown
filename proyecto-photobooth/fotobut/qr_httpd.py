#!/usr/bin/env python3
"""PROCESO 3 · qr_httpd: sirve las tiras al celular (puerto 8080). Corre aparte de la pantalla: si vision_gui se cae, las
descargas siguen; si este proceso muere, la cabina sigue funcionando y systemd lo levanta (aislamiento de fallos, Avance 1)."""
import logging, os

from fotobut import config as C
from fotobut.share import serve_share


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s qr_httpd: %(message)s")
    from fotobut.sched import set_prio
    set_prio("qr_httpd", nice=10)                        # [C8-T5] baja prioridad: nunca compite con la camara ni el boton
    try:
        serve_share().serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
