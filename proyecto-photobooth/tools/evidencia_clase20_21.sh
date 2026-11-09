#!/bin/bash
# Evidencia de terminal de las clases 20 (tipos y volatile) y 21 (driver de cada sensor y actuador).
# Corre en la Pi desde la carpeta del proyecto:   ./tools/evidencia_clase20_21.sh 2>&1 | tee /tmp/evidencia_c20_c21.txt
# Toma captura de la terminal por partes (Parte 1, 2, 3 y 4).
cd "$(dirname "$0")/.."
echo "################ CLASE 20 · PARTE 1: tipos y padding de las estructuras ################"
gcc -Wall -O2 tools/tipos_proyecto.c -o /tmp/tipos && /tmp/tipos
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from fotobut import ipc, pool, config as C
print(f"\nPython (mismo formato): MSG={ipc.MSG_SIZE} B, SHM={ipc.SHM_USED} B, bloque del pool={pool.SLOT_BYTES} B")
PY
echo
echo "################ CLASE 20 · PARTE 2: volatile (ciclo que espera una senal) ################"
gcc -O2 tools/volatile_demo.c -o /tmp/vol_sin && gcc -O2 -DCON_VOLATILE tools/volatile_demo.c -o /tmp/vol_con
echo "--- ensamblador de esperar() SIN volatile (lee g_listo una vez y se queda en un salto a si mismo)"
objdump -d /tmp/vol_sin --no-show-raw-insn | awk '/<esperar>:/,/ret/'
echo "--- ensamblador de esperar() CON volatile (vuelve a LEER la memoria en cada vuelta)"
objdump -d /tmp/vol_con --no-show-raw-insn | awk '/<esperar>:/,/ret/'
echo "--- ejecucion CON volatile:";  timeout 5 /tmp/vol_con; echo "codigo de salida: $?"
echo "--- ejecucion SIN volatile (se espera que se cuelgue; timeout de 3 s):"; timeout 3 /tmp/vol_sin; echo "codigo de salida: $? (124 = el timeout lo mato: nunca vio el cambio)"
echo
echo "################ CLASE 20 · PARTE 3: volatile en el firmware del STM32 ################"
grep -n "volatile" firmware_stm32/src/main.c
ELF=firmware_stm32/build/smartbooth_stm32.elf
if [ -f "$ELF" ]; then echo "--- tamano en la SRAM de cada variable (nm -S):"; nm -S "$ELF" | grep -E " g_(state|t0|width_us|ms)$"; size "$ELF"; fi
echo
echo "################ CLASE 21 · PARTE 4: driver y nodo de cada sensor y actuador ################"
echo "--- nodos de dispositivo"; ls -l /dev/gpiochip0 /dev/gpiomem /dev/i2c-1 /dev/spidev0.0 /dev/ttyAMA0 /dev/video0 2>&1
echo "--- PWM del buzzer (sysfs)"; ls /sys/class/pwm/; cat /sys/class/pwm/pwmchip0/npwm 2>/dev/null; readlink -f /sys/class/pwm/pwmchip0/device/driver 2>/dev/null
echo "--- modulos del kernel cargados"; lsmod | grep -E "i2c_bcm2835|i2c_dev|spi_bcm2835|spidev|pwm|imx708|unicam|bcm2835_isp|v4l2" 
echo "--- driver enlazado a cada dispositivo (sysfs)"
for p in /sys/bus/i2c/devices/*; do [ -e "$p/driver" ] && echo "$(basename $p) -> $(basename $(readlink -f $p/driver))"; done
for p in /sys/bus/spi/devices/*; do [ -e "$p/driver" ] && echo "$(basename $p) -> $(basename $(readlink -f $p/driver))"; done
echo "--- bus I2C"; i2cdetect -y 1
echo "--- funcion de cada pin (pinctrl)"; pinctrl get 2,3,8,9,10,11,14,15,17,18 2>/dev/null || raspi-gpio get 2,3,8,9,10,11,14,15,17,18 2>/dev/null
echo "--- dmesg relevante"; sudo dmesg | grep -iE "imx708|pl011|ttyAMA|spi|i2c|pwm" | tail -15
