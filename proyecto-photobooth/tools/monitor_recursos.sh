#!/bin/bash
# RAM (RSS) y CPU de los 3 procesos cada 10 s -> /tmp/recursos.csv. Sirve para la deriva de memoria (<= 5 MB) y la huella (~410 MB).
# Uso:  ./tools/monitor_recursos.sh [minutos]     (corre las sesiones que quieras mientras tanto; Ctrl+C para terminar)
M=${1:-10}; OUT=/tmp/recursos.csv
echo "t_s,proceso,rss_mb,cpu_pct,hilos" > $OUT
t0=$(date +%s)
while [ $(( $(date +%s) - t0 )) -lt $((M*60)) ]; do
  for u in fotobut-control fotobut-vision fotobut-qr; do
    pid=$(systemctl show -p MainPID --value $u); [ "$pid" = 0 ] && continue
    read rss cpu nlwp < <(ps -o rss=,pcpu=,nlwp= -p $pid)
    echo "$(( $(date +%s) - t0 )),$u,$(echo "scale=1;$rss/1024" | bc),$cpu,$nlwp" >> $OUT
  done
  free -m | awk 'NR==2{printf "# sistema usado=%s MB libre=%s MB\n",$3,$4}' >> $OUT
  sleep 10
done
python3 - <<'PY'
import csv, collections
d = collections.defaultdict(list)
for r in csv.DictReader(l for l in open('/tmp/recursos.csv') if not l.startswith('#')):
    d[r['proceso']].append(float(r['rss_mb']))
print("\nproceso            RSS inicial  RSS final  deriva (MB)")
for k, v in d.items(): print(f"{k:18s} {v[0]:10.1f} {v[-1]:10.1f} {v[-1]-v[0]:+10.1f}")
PY
