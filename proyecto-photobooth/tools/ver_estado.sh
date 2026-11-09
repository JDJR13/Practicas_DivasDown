#!/bin/bash
# Muestra en vivo lo que ve la cabina: estado, distancia del HC-SR04 y si cuenta como presencia (30-120 cm).
# Sirve para acomodar el sensor y probar el reposo de 5 s y el boton de reset.   Uso: ./tools/ver_estado.sh   (Ctrl+C para salir)
while true; do
  curl -s --max-time 1 http://127.0.0.1:8000/api/state | python3 -c '
import sys, json, time
try:
    s = json.load(sys.stdin)
except Exception:
    print(time.strftime("%H:%M:%S"), "vision_gui no responde"); sys.exit()
d = s["distance"]
print(time.strftime("%H:%M:%S"), "%-10s" % s["state"], "dist:", ("%3d cm" % d) if d is not None else "  ---  ",
      "| presencia:", "SI" if s["present"] else "no", "| STM32:", "ok" if s["uart_ok"] else "SIN TRAMAS",
      "| sin actividad: %4.1f s" % (s.get("idle_ms", 0) / 1000), "| foto", s["shot"])'
  sleep 0.5
done
