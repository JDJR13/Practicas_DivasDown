#!/bin/bash
# Arranca El Fotobut en la Raspberry Pi: servidor Python + Chromium a pantalla completa en el monitor (HDMI).
# Uso:  ./kiosk.sh           (hardware real)       ./kiosk.sh --sim     (simulador, teclado en la Pi)
# Funciona desde SSH: busca la sesion grafica que ya esta abierta en el monitor (Wayland o X11).
cd "$(dirname "$0")"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
FLAGS=""
# Chromium se abre por X11 (Xwayland, DISPLAY=:0) si existe: en Raspberry Pi OS trixie con labwc, Chromium en Wayland
# nativo llego a quedarse sin ventana visible (pantalla negra o solo el escritorio) y por X11 si se muestra.
# Para forzar uno:  FOTOBUT_PANTALLA=wayland ./kiosk.sh   o   FOTOBUT_PANTALLA=x11 ./kiosk.sh
MODO="${FOTOBUT_PANTALLA:-auto}"
if [ -z "$WAYLAND_DISPLAY" ] && ls "$XDG_RUNTIME_DIR"/wayland-[0-9] >/dev/null 2>&1; then
  export WAYLAND_DISPLAY="$(basename "$(ls "$XDG_RUNTIME_DIR"/wayland-[0-9] 2>/dev/null | head -1)")"
fi
X=$(ls /tmp/.X11-unix/ 2>/dev/null | grep -m1 '^X[0-9]' | tr -d X)
if [ "$MODO" = "wayland" ] || { [ "$MODO" = "auto" ] && [ -z "$X" ] && [ -z "$DISPLAY" ] && [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; }; then
  FLAGS="--ozone-platform=wayland"; echo "Pantalla: Wayland ($WAYLAND_DISPLAY)"
else
  export DISPLAY="${DISPLAY:-:${X:-0}}"; FLAGS="--ozone-platform=x11"; echo "Pantalla: X11 ($DISPLAY)"
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
# Pantalla completa SIN modo --kiosk: en esta Pi (trixie + labwc) Chromium a pantalla completa queda en negro o en blanco,
# con o sin GPU. Una ventana de aplicacion (--app, sin barra ni pestanas) del tamano exacto del monitor si se dibuja bien.
TAM=$(WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" wlr-randr 2>/dev/null | grep -m1 current | grep -oE '[0-9]+x[0-9]+')
[ -n "$TAM" ] || TAM=$(xrandr 2>/dev/null | grep -m1 '\*' | grep -oE '[0-9]+x[0-9]+')
W=${TAM%x*}; H=${TAM#*x}; W=${W:-1920}; H=${H:-1080}
echo "Ventana de ${W}x${H}"
# Si el navegador se cierra (alguien conecto un teclado y pulso Alt+F4, o fallo), se abre de nuevo: la cabina nunca queda en el escritorio.
while true; do
  "$BROWSER" $FLAGS --app=http://127.0.0.1:8000 --window-position=0,0 --window-size="$W,$H" --noerrdialogs --disable-infobars \
    --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required --overscroll-history-navigation=0 --disable-pinch \
    --user-data-dir=/tmp/fotobut-chromium --password-store=basic --lang=es-MX --disable-features=Translate,TranslateUI \
    --disable-extensions --disable-sync --no-first-run --check-for-update-interval=31536000
  [ -n "$FOTOBUT_SIN_REINTENTO" ] && break
  sleep 1
done
