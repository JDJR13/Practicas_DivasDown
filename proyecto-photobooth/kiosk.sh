#!/bin/bash
# Arranca El Fotobut en la Raspberry Pi: servidor Python + Chromium a pantalla completa en el monitor (HDMI).
# Uso:  ./kiosk.sh           (hardware real)       ./kiosk.sh --sim     (simulador, teclado en la Pi)
# Funciona desde SSH: busca la sesion grafica que ya esta abierta en el monitor (Wayland o X11).
cd "$(dirname "$0")"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
FLAGS=""
if [ -z "$WAYLAND_DISPLAY" ] && ls "$XDG_RUNTIME_DIR"/wayland-* >/dev/null 2>&1; then
  export WAYLAND_DISPLAY="$(basename "$(ls "$XDG_RUNTIME_DIR"/wayland-[0-9] 2>/dev/null | head -1)")"
fi
if [ -n "$WAYLAND_DISPLAY" ] && [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
  FLAGS="--ozone-platform=wayland"; echo "Pantalla: Wayland ($WAYLAND_DISPLAY)"
else
  export DISPLAY="${DISPLAY:-:0}"; FLAGS="--ozone-platform=x11"; echo "Pantalla: X11 ($DISPLAY)"
fi
BROWSER=$(command -v chromium-browser || command -v chromium) || { echo "No encuentro Chromium (sudo apt install chromium)"; exit 1; }
if systemctl is-enabled fotobut-vision >/dev/null 2>&1; then
  echo "Servicios systemd instalados: solo abro la pantalla (los 3 procesos ya corren)."
else
  pkill -f "python3 run.py" 2>/dev/null; sleep 0.5
  python3 run.py "$@" > /tmp/fotobut.log 2>&1 &            # modo desarrollo: lanza y vigila los 3 procesos
fi
for i in $(seq 1 60); do curl -s http://127.0.0.1:8000/api/state >/dev/null && break; sleep 0.5; done
curl -s http://127.0.0.1:8000/api/state >/dev/null || { echo "vision_gui no responde. Mira: journalctl -u fotobut-vision -n 30   (o /tmp/fotobut.log)"; exit 1; }
echo "Servidor listo. Abriendo en el monitor… (log: /tmp/fotobut.log)"
exec "$BROWSER" $FLAGS --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
  --autoplay-policy=no-user-gesture-required --overscroll-history-navigation=0 --disable-pinch \
  --user-data-dir=/tmp/fotobut-chromium --password-store=basic --use-fake-ui-for-media-stream \
  --check-for-update-interval=31536000 http://127.0.0.1:8000
