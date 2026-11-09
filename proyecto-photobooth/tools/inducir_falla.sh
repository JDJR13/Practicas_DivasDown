#!/bin/bash
# Fallas inducidas del Avance 3. Mata un proceso con SIGKILL (kill -9) y mide cuanto tarda el sistema en recuperarse SOLO.
#   ./tools/inducir_falla.sh control   -> pierde el hardware (boton, sensores, buzzer)   vision_gui sigue vivo y se reconecta
#   ./tools/inducir_falla.sh vision    -> cae la pantalla en plena sesion; control_daemon y qr_httpd siguen; Chromium reconecta
#   ./tools/inducir_falla.sh qr        -> cae la descarga; la cabina ni se entera (aislamiento de fallos)
U=${1:?uso: $0 control|vision|qr}; SVC=fotobut-$U
api() { curl -s -m 1 http://127.0.0.1:8000/api/state; }
ok_control() { api | python3 -c "import sys,json; print(json.load(sys.stdin)['hw']['link'])" 2>/dev/null | grep -q True; }
ok_vision()  { api | grep -q '"state"'; }
ok_qr()      { curl -s -m 1 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ | grep -qE '^(200|302|404)$'; }
echo "== ANTES =="; systemctl show -p MainPID,NRestarts,ActiveState $SVC | paste -sd' '
OLD=$(systemctl show -p MainPID --value $SVC)
echo "== FALLA: kill -9 $OLD ($SVC) =="; T0=$(date +%s.%N); sudo kill -9 $OLD
# 1) deteccion: el servicio cambia de PID / se reinicia
while true; do NEW=$(systemctl show -p MainPID --value $SVC); [ "$NEW" != "$OLD" ] && [ "$NEW" != 0 ] && break; sleep 0.05; done
T1=$(date +%s.%N)
# 2) recuperacion funcional: vuelve a responder
for i in $(seq 1 200); do ok_$U && break; sleep 0.05; done
T2=$(date +%s.%N)
printf "proceso nuevo (systemd) a los %.2f s   |   funcionando de nuevo a los %.2f s\n" $(echo "$T1-$T0"|bc -l) $(echo "$T2-$T0"|bc -l)
echo "== DESPUES =="; systemctl show -p MainPID,NRestarts,ActiveState $SVC | paste -sd' '
echo "== journal =="; journalctl -u $SVC -u fotobut-vision -u fotobut-control --since "-20 sec" --no-pager -o cat | tail -12
