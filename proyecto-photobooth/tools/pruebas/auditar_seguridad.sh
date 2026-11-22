#!/bin/bash
# Autoauditoria de El Fotobut: prueba desde la propia Pi lo mismo que intentaria un atacante y revisa la configuracion.
# Uso:  ./tools/pruebas/auditar_seguridad.sh            (para el reporte:  ./tools/pruebas/auditar_seguridad.sh 2>&1 | tee /tmp/auditoria.txt)
P=0; F=0
si() { echo "  [PASA]  $*"; P=$((P+1)); }
no() { echo "  [FALLA] $*"; F=$((F+1)); }
cod() { curl -s -o /dev/null -m 4 -w '%{http_code}' "$@"; }
IP=$(hostname -I 2>/dev/null | awk '{print $1}'); IP=${IP:-127.0.0.1}
B="http://$IP:8080"
echo "== Auditoria de El Fotobut · $(date '+%F %T') · IP $IP =="

echo; echo "-- 1. Que se ve desde la red --"
for p in 8000 9000; do
  if ss -tlnH 2>/dev/null | awk '{print $4}' | grep -E "(^|:)$p\$" | grep -vq "^127.0.0.1:"; then no "el puerto $p escucha fuera de 127.0.0.1"
  else si "el puerto $p (pantalla/panel) solo escucha en 127.0.0.1"; fi
done
[ "$(cod "http://$IP:8000/api/state")" = "000" ] && si "la API de la pantalla no responde por la IP de red" || no "la API de la pantalla responde por la red"
ABIERTOS=$(ss -tlnH 2>/dev/null | awk '{print $4}' | grep -v "^127\.\|^\[::1\]" | sed 's/.*://' | sort -un | tr '\n' ' ')
echo "          puertos TCP que escuchan en la red: ${ABIERTOS:-ninguno}"
for p in $ABIERTOS; do case "$p" in 22|8080|53) ;; *) no "puerto inesperado abierto: $p";; esac; done

echo; echo "-- 2. Servidor de descargas (8080): lo que NO debe entregar --"
[ "$(cod "$B/salud")" = "200" ] && si "el servidor responde (/salud)" || no "el servidor de descargas no responde"
for r in /api/state /events /static/app.js /estado.json /sesiones.log "/strip/../../etc/passwd" "/f/..%2f..%2frun.py" \
         "/s/0001-0000000000000000" "/photo/0001-0000000000000000/..%2f..%2fetc%2fpasswd" /.git/config /admin; do
  c=$(cod --path-as-is "$B$r"); [ "$c" = "404" ] && si "404 en $r" || no "$r devolvio $c"
done
curl -s -m 4 "$B/" | grep -q "Descargar" && no "la raiz muestra una tira sin pedir el codigo" || si "sin el codigo QR no se ve la tira de nadie"
[ "$(cod -X POST "$B/")" = "405" ] && si "POST rechazado (405)" || no "POST no fue rechazado"
[ "$(cod "$B/$(head -c 300 /dev/zero | tr '\0' a)")" = "414" ] && si "ruta larguisima rechazada (414)" || no "ruta larga aceptada"
H=$(curl -s -I -m 4 "$B/")
echo "$H" | grep -qi "content-security-policy" && si "cabecera Content-Security-Policy" || no "falta Content-Security-Policy"
echo "$H" | grep -qi "x-content-type-options: nosniff" && si "cabecera nosniff" || no "falta nosniff"
echo "$H" | grep -i "^server:" | grep -qi "python" && no "el servidor revela su version" || si "no revela version de Python"
if [ "$IP" != "127.0.0.1" ]; then
  n=0; for i in $(seq 1 25); do [ "$(cod "$B/s/0001-$(printf '%016x' $i)")" = "429" ] && n=$((n+1)); done
  [ $n -gt 0 ] && si "adivinar ids: la IP quedo bloqueada tras 15 intentos ($n de 25 respondieron 429)" || no "25 ids falsos seguidos y ningun bloqueo"
  echo "          (tu IP queda bloqueada 2 min en el 8080; es lo esperado)"
fi

echo; echo "-- 3. Sistema --"
if command -v nft >/dev/null && sudo -n nft list table inet fotobut >/dev/null 2>&1; then si "cortafuegos cargado (tabla inet fotobut)"
elif systemctl is-active -q fotobut-firewall; then si "cortafuegos activo (fotobut-firewall)"; else no "cortafuegos no activo (sudo ./scripts/blindar.sh)"; fi
S=$(sudo -n sshd -T 2>/dev/null || sshd -T 2>/dev/null)
if [ -n "$S" ]; then
  echo "$S" | grep -q "^permitrootlogin no" && si "SSH: root no entra" || no "SSH permite root"
  echo "$S" | grep -q "^passwordauthentication no" && si "SSH: solo llave (sin contrasenas)" || no "SSH acepta contrasena (sudo ./scripts/blindar.sh --ssh-solo-llave)"
  echo "$S" | grep -q "^maxauthtries 3" && si "SSH: 3 intentos" || no "SSH: MaxAuthTries sin limitar"
else echo "          (no pude leer la configuracion de sshd sin sudo; corre este script con sudo -v antes)"; fi
for s in control vision qr monitor; do
  systemctl is-active -q fotobut-$s && si "fotobut-$s activo" || no "fotobut-$s no esta activo"
  w=$(systemctl show fotobut-$s -p WatchdogUSec --value 2>/dev/null); [ -n "$w" ] && [ "$w" != "0" ] && [ "$w" != "infinity" ] && si "fotobut-$s con watchdog ($w)" || no "fotobut-$s sin watchdog"
done
u=$(systemctl show fotobut-qr -p User --value 2>/dev/null); [ -n "$u" ] && [ "$u" != "root" ] && si "los servicios no corren como root (usuario $u)" || no "qr_httpd corre como root"
[ "$(systemctl show -p RuntimeWatchdogUSec --value 2>/dev/null)" != "0" ] && [ -e /dev/watchdog ] && si "watchdog de hardware armado" || no "watchdog de hardware sin armar"
ls /var/log/journal/*/system.journal >/dev/null 2>&1 && si "registros persistentes (journald en /var/log/journal)" || no "journald no es persistente (sudo journalctl --flush; o sudo ./scripts/blindar.sh)"
if command -v systemd-analyze >/dev/null; then
  echo "          exposicion segun systemd (0 = mejor, 10 = peor):"
  for s in qr vision control monitor; do printf '            fotobut-%-8s %s\n' "$s" "$(systemd-analyze security fotobut-$s 2>/dev/null | tail -1 | sed 's/.*Overall exposure level for [^:]*: //')"; done
fi

echo; echo "== Resultado: $P pasan, $F fallan =="
[ $F = 0 ]
