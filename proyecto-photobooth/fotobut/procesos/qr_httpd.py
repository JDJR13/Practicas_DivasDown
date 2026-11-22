#!/usr/bin/env python3
"""PROCESO 3 · qr_httpd: sirve las tiras al celular (puerto 8080). Corre aparte de la pantalla: si vision_gui se cae, las
descargas siguen; si este proceso muere, la cabina sigue funcionando y systemd lo levanta (aislamiento de fallos, Avance 1)."""
import logging, os

from fotobut.servicios import config as C
from fotobut.comunicacion.share import serve_share


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s qr_httpd: %(message)s")
    logging.getLogger("fotobut.config").info(C.resumen_conf())                 # [C22-config] de donde salieron los valores
    for aviso in C.CONF_AVISOS:
        logging.getLogger("fotobut.config").warning(aviso)
    from fotobut.servicios.sched import set_prio
    set_prio("qr_httpd", nice=10)                        # [C8-T5] baja prioridad: nunca compite con la camara ni el boton
    httpd = serve_share()
    import urllib.request
    from fotobut.servicios.vigia import Vigia

    def responde() -> bool:                              # [C22-watchdog] la senal de vida depende de que el servidor conteste
        with urllib.request.urlopen(f"http://127.0.0.1:{C.SHARE_PORT}/salud", timeout=3) as r:
            return r.status == 200
    Vigia("qr_httpd", {"servidor de descargas (/salud)": responde}, gracia_s=10).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
