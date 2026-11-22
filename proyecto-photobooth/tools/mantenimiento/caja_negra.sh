#!/bin/bash
# Lee la caja negra desde la terminal (por SSH): los ultimos eventos y la ultima muestra de salud.
#   ./tools/mantenimiento/caja_negra.sh            ultimos 30 eventos        ./tools/mantenimiento/caja_negra.sh 100      ultimos 100
N="${1:-30}"; D=/var/lib/fotobut/caja_negra; [ -d "$D" ] || D="$HOME/fotobut_estado/caja_negra"
cat "$D"/*.jsonl 2>/dev/null | python3 -c '
import sys, json
n = int(sys.argv[1]); ev, m = [], None
for l in sys.stdin:
    try: r = json.loads(l)
    except ValueError: continue
    if r.get("k") == "e": ev.append(r)
    elif r.get("k") == "m": m = r
for e in ev[-n:]: print(e.get("h", "?"), "%-5s" % e.get("nivel", ""), e.get("txt", ""))
if m:
    s = m.get("srv", {})
    print("\nUltima muestra (%s): cabina %s | CPU %s C | RAM %s MB | disco libre %s MB | STM32 %s | servicios: %s" % (
        m.get("h"), m.get("estado", "sin respuesta"), m.get("cpu_c"), m.get("ram_mb"), m.get("disco_libre_mb"),
        "ok" if m.get("stm32") else "sin tramas", ", ".join("%s=%s(%d reinicios)" % (k, v["activo"], v["reinicios"]) for k, v in s.items()) or "sin datos"))
' "$N"
