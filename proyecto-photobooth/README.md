# El Fotobut · SmartBooth FSE (equipo DivasDown, grupo 06)

Cabina de fotos embebida: **Raspberry Pi 4** (Linux) + **STM32F103C8T6** (bare-metal). Software de la Pi en **3 procesos** que arrancan solos
con systemd y se comunican por IPC; pantalla de 15.6" (Chromium en modo kiosco) y descarga de la tira desde el celular por una red Wi-Fi propia.
Funciona **sin internet**: fuentes, QR y todo lo demás van incluidos.

```
 ┌────────── control_daemon ──────────┐   socket AF_UNIX SEQPACKET (eventos/órdenes, 64 B)   ┌──────────── vision_gui ────────────┐
 │ H_boton (FIFO 80)  GPIO17          │ ───────────────────────────────────────────────────▶ │ H_maquina  máquina de estados      │
 │ H_sensores (nice -5) SPI MCP3008 ──┼──── /dev/shm/pb_status + semáforo POSIX (pot, ldr,  ─▶│ H_compositor (nice 0) tira + fsync │
 │   UART ← STM32 (HC-SR04)           │      distancia, temperatura; 128 B)                  │ cámara IMX708 · pool de 3 fotos    │
 │ H_oled (nice +10) I2C BMP280+OLED  │ ◀──────────────────────── órdenes: beep, estado ──── │ servidor de la pantalla 127.0.0.1:8000
 │ buzzer PWM0 (GPIO18)               │                                                      └─────────────────────────────────────┘
 └────────────────────────────────────┘                  qr_httpd (nice +10): descargas del celular :8080 — lee la tira del disco
```

## 1. Reproducir la configuración (Raspberry Pi OS 64-bit, Debian 13 trixie)
```bash
# 1) Firmware de la Pi: /boot/firmware/config.txt  (luego: sudo reboot)
dtparam=i2c_arm=on
dtparam=spi=on
enable_uart=1
dtoverlay=disable-bt          # libera /dev/ttyAMA0 para el STM32
dtoverlay=pwm,pin=18,func=2   # buzzer en GPIO18 (PWM0 por hardware)
sudo raspi-config nonint do_serial_cons 1 && sudo raspi-config nonint do_serial_hw 0   # sin consola serie, UART de hardware activo

# 2) Paquetes y permisos
sudo apt install -y python3-lgpio python3-spidev python3-serial python3-pil python3-numpy python3-picamera2 \
                    chromium i2c-tools strace gcc stlink-tools
sudo usermod -a -G gpio,i2c,spi,dialout,video,render $USER      # cerrar sesión y volver a entrar

# 3) Bajar el proyecto
git clone https://github.com/JDJR13/Practicas_DivasDown.git && cd Practicas_DivasDown/proyecto-photobooth

# 4) Servicios (arranque automático) y pantalla en modo kiosco
sudo ./scripts/instalar_servicios.sh        # crea y habilita fotobut-control / fotobut-vision / fotobut-qr
./scripts/instalar_autoarranque.sh          # Chromium a pantalla completa al iniciar la sesión gráfica
sudo reboot                                  # el sistema debe quedar funcionando solo
```
Red Wi-Fi propia para la descarga (opcional, una sola vez): `sudo ./scripts/setup_ap.sh` y luego `./scripts/ap_on.sh`
(usa wlan0: si entras por SSH por Wi-Fi se corta; usa cable o `--force`). SSID `Fotobut`, clave `fotobut2026`, IP `192.168.4.1`.

## 2. Probar sin hardware (simulador, en cualquier PC con Python 3.10+, Pillow y numpy)
```bash
python3 run.py --sim                 # lanza los 3 procesos y los vigila; abre http://127.0.0.1:8000
```
Teclas: Espacio = botón · ←/→ o 1-5 = potenciómetro (filtro) · P = persona frente al sensor · D = depuración. `?debug` muestra el estado del hardware.

## 3. Pruebas y mediciones (ver `tools/`)
| Qué | Comando |
|---|---|
| Lógica, IPC, carrera de la memoria compartida, recuperación | `python3 tests/test_machine.py` · `tests/test_ipc.py` · `tests/test_share.py` · `tests/test_hw.py` · `tests/test_qr.py` |
| Requisitos de tiempo contra el Avance 1 | `python3 tools/resumen_mediciones.py` (después de 8-10 sesiones) |
| Arranque ≤ 25 s | `./tools/medir_arranque.sh` |
| Prioridades de cada hilo (clase 8) | `./tools/mostrar_prioridades.sh` |
| RAM y CPU por proceso | `./tools/monitor_recursos.sh 10` |
| Fallas inducidas y recuperación | `./tools/inducir_falla.sh control` · `vision` · `qr` |
| Precision del HC-SR04 + STM32 (con `fotobut-control` detenido) | `python3 tools/medir_distancia.py 10 30 60 100` |
| Latencia y traza del socket (IPC) | `curl -s http://127.0.0.1:8000/api/ipc` · `./tools/trazar_ipc.sh` |
| Clases 20 y 21 (tipos, volatile, drivers) | `./tools/evidencia_clase20_21.sh 2>&1 \| tee /tmp/ev.txt` · `./tools/contar_syscalls.sh` |
| Dónde está cada decisión de la bitácora (archivo:línea) | `python3 tools/mapa_bitacora.py` |

## 4. Firmware del STM32 (`firmware_stm32/`)
```bash
sudo apt install gcc-arm-none-eabi stm32flash
cd firmware_stm32 && make                       # build/smartbooth_stm32.bin  (en la Pi: sudo apt install gcc-arm-none-eabi stm32flash)
# Sin ST-Link: gestor de arranque por UART desde la Pi. Detener antes el servicio que usa el puerto: sudo systemctl stop fotobut-control
#   1) jumper BOOT0=1 (BOOT1=0) y boton RESET de la placa;  2) sudo stm32flash /dev/ttyAMA0   (debe decir Device ID 0x0410)
#   3) sudo stm32flash -w build/smartbooth_stm32.bin -v -g 0x0 /dev/ttyAMA0;  4) BOOT0=0 y RESET;  5) sudo systemctl start fotobut-control
# Cableado UART: PA9 (TX) -> pin 10 (RXD) de la Pi;  PA10 (RX) <- pin 8 (TXD);  GND comun.
```
El STM32 mide con TIM2 CH2 (captura de entrada en PA1, 1 µs) el eco del HC-SR04 y manda `DIST:123 cm` por USART1 a 115200 a 10 Hz.
**Divisor de tensión obligatorio en el Echo** (5 V → 3.3 V): PA1 no tolera 5 V.

## 5. Estructura del código
- `fotobut/control_daemon.py` proceso 1: hardware, hilos H_sensores / H_oled / H_socket; `hal.py` (SimHAL, PiHAL), `i2c.py`, `oled.py`, `telemetry.py`
- `fotobut/vision_gui.py` proceso 2: `machine.py` (estados, productor), `pool.py` (3 bloques + semáforos), `camera.py`, `strip.py`, `filters.py`, `qr.py`, `server.py`, `remote_hal.py`
- `fotobut/qr_httpd.py` proceso 3: `share.py` (solo expone /s/, /strip/, /photo/, /dl/)
- `fotobut/ipc.py` socket AF_UNIX, memoria compartida, semáforo POSIX · `fotobut/sched.py` prioridades de hilos · `fotobut/config.py` parámetros
- `systemd/` unidades · `scripts/` instalación y red Wi-Fi · `web/` interfaz (HTML/CSS/JS) · `tools/` medición y evidencia · `tests/`

## 6. Reglas de la cabina
- Presencia: 5 lecturas seguidas (500 ms a 10 Hz) entre 30 y 120 cm despiertan la cabina; una lectura fuera de rango reinicia la cuenta.
- Potenciómetro (0-1023) → 5 filtros con histéresis. Cuenta regresiva 3-2-1 con tono; 3 fotos; tira lista en ≤ 2.5 s tras la 3ª foto.
- Fotos intermedias en /tmp (RAM); la tira final a la microSD con `fsync` (clase 15). 45 s en resultado → inicio; 120 s sin nadie → reposo.
- Buzzer: `python3 tools/buzzer_sweep.py` encuentra la frecuencia que suena más fuerte (`TICK_HZ`, `SHUTTER_HZ` en `config.py`).
