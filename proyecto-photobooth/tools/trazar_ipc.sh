#!/bin/bash
# Evidencia de la clase 11: traza de los mensajes del socket AF_UNIX entre control_daemon y vision_gui (strace).
# Uso:  ./tools/trazar_ipc.sh      (6 s; presiona el boton una vez mientras corre)   Requiere: sudo apt install strace
P1=$(systemctl show -p MainPID --value fotobut-control); P2=$(systemctl show -p MainPID --value fotobut-vision)
echo "control_daemon pid=$P1   vision_gui pid=$P2   socket:"; ss -xp 2>/dev/null | grep photobooth | head -3
echo "--- llamadas send/recv de los dos procesos durante 6 s (cada mensaje = 64 bytes) ---"
sudo timeout -s INT 6 strace -f -tt -e trace=sendto,recvfrom,sendmsg,recvmsg -p $P1 -p $P2 2>&1 | grep -E "= 64$|= 1[0-9]{2}$" | head -30
