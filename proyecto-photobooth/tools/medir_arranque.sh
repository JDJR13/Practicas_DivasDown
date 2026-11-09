#!/bin/bash
# Requisito del Avance 1: la cabina arranca sola por systemd en <= 25 s desde que se energiza.   ./tools/medir_arranque.sh
echo "== Tiempo de arranque del sistema (kernel + espacio de usuario) =="
systemd-analyze time
echo
echo "== Momento (segundos desde el encendido) en que quedo lista cada parte =="
for u in fotobut-control fotobut-vision fotobut-qr; do
  t=$(systemctl show -p ActiveEnterTimestampMonotonic --value $u)
  [ -n "$t" ] && printf "%-18s activo a los %6.2f s\n" $u $(echo "$t/1000000" | bc -l)
done
echo
echo "== Pantalla lista (log de vision_gui): ESTE es el valor que se compara con el requisito (<= 25 s) =="
journalctl -u fotobut-vision -b --no-pager | grep "LISTA interfaz" | tail -1
echo
echo "== Servicios habilitados para el arranque =="
systemctl is-enabled fotobut-control fotobut-vision fotobut-qr
