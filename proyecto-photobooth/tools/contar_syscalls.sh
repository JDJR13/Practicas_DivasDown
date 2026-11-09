#!/bin/bash
# Clase 21 con cifras: cuantas llamadas al sistema por segundo hace cada proceso (sudo apt install strace).
# Uso:  ./tools/contar_syscalls.sh      (10 s; presiona el boton un par de veces)
for u in fotobut-control fotobut-vision; do
  pid=$(systemctl show -p MainPID --value $u)
  echo "=== $u (pid $pid), 10 s ==="
  sudo timeout -s INT 10 strace -c -f -p $pid 2>&1 | grep -v "^strace: Process" | head -16
done
