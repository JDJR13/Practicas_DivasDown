#!/bin/bash

echo "=== Reporte de Diagnostico del Sistema ==="
echo ""
echo "Fecha: $(date)"
echo "Hostname: $(hostname)"
echo ""

echo "--- Uptime ---"
uptime
echo ""

echo "--- Uso de disco ---"
df -h
echo ""

echo "--- Uso de memoria ---"
free -h
echo ""

echo "--- Temperatura de CPU ---"
if command -v vcgencmd &> /dev/null; then
    vcgencmd measure_temp
else
    echo "vcgencmd no disponible"
fi
echo ""

echo "--- Reporte compilado en C ---"
if [ -x ./reporte_sistema ]; then
    ./reporte_sistema
else
    echo "reporte_sistema no encontrado o sin permiso de ejecucion"
fi

echo ""
echo "=== Fin del reporte ==="
