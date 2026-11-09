#!/bin/bash
# Evidencia de la clase 8: politica y prioridad de CADA hilo de los 3 procesos.   ./tools/mostrar_prioridades.sh
echo "== Procesos y servicios =="
systemctl --no-pager -p MainPID,ActiveState,Nice show fotobut-control fotobut-vision fotobut-qr 2>/dev/null | paste -sd' ' | sed 's/MainPID/\nMainPID/g'
echo
echo "== Hilos: CLS=politica (TS=CFS normal, FF=SCHED_FIFO)  RTPRIO=prioridad tiempo real  NI=nice  COMMAND=nombre del hilo =="
for u in fotobut-control fotobut-vision fotobut-qr; do
  pid=$(systemctl show -p MainPID --value $u 2>/dev/null)
  [ -n "$pid" ] && [ "$pid" != "0" ] && { echo "-- $u (pid $pid)"; ps -L -o tid,cls,rtprio,ni,pcpu,comm -p $pid; }
done
echo
echo "== Politica exacta por chrt (hilo del boton) =="
pid=$(systemctl show -p MainPID --value fotobut-control)
for t in $(ls /proc/$pid/task 2>/dev/null); do n=$(cat /proc/$pid/task/$t/comm); [ "$n" = "H_boton" ] && chrt -p $t; done
