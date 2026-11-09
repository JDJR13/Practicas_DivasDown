#!/usr/bin/env python3
"""El Fotobut - lanzador de desarrollo: arranca los 3 procesos y los vigila (en la cabina lo hace systemd).
   python3 run.py --sim      sin hardware (teclado/raton)       python3 run.py      cabina real en la Raspberry Pi
Los 3 procesos:  control_daemon (hardware) <-IPC-> vision_gui (pantalla :8000)     qr_httpd (descargas :8080)"""
import argparse, logging, signal, subprocess, sys, time

PROCS = [("control_daemon", "fotobut.control_daemon"), ("vision_gui", "fotobut.vision_gui"), ("qr_httpd", "fotobut.qr_httpd")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 para abrir la interfaz desde otra PC (solo desarrollo)")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s run: %(message)s")
    sim = ["--sim"] if a.sim else []
    extra = {"fotobut.vision_gui": ["--host", a.host, "--port", str(a.port)]}
    kids: dict[str, subprocess.Popen] = {}

    def start(name: str, mod: str) -> None:
        args = sim if mod != "fotobut.qr_httpd" else []
        kids[name] = subprocess.Popen([sys.executable, "-m", mod, *args, *extra.get(mod, [])])
        logging.info("%s arrancado (pid %d)", name, kids[name].pid)

    def stop(*_):
        for p in kids.values():
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    for name, mod in PROCS:
        start(name, mod)
        time.sleep(0.4 if name == "control_daemon" else 0)
    try:
        while True:                                       # como Restart=always de systemd
            for name, mod in PROCS:
                if kids[name].poll() is not None:
                    logging.warning("%s murio (codigo %s): lo reinicio", name, kids[name].returncode)
                    time.sleep(1)
                    start(name, mod)
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop()


if __name__ == "__main__":
    main()
