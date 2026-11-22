# El Fotobut · SmartBooth FSE (equipo DivasDown, grupo 06)

Cabina de fotos embebida: **Raspberry Pi 4** (Linux) + **STM32F103C8T6** (bare-metal). Software de la Pi en **3 procesos** que arrancan solos
(más un cuarto, el monitor) con systemd y se comunican por IPC; pantalla de 15.6" (Chromium en modo kiosco) y descarga de la tira desde el celular por una red Wi-Fi propia.
Funciona **sin internet**: fuentes, QR y todo lo demás van incluidos.

```
 ┌────────── control_daemon ──────────┐   socket AF_UNIX SEQPACKET (eventos/órdenes, 64 B)   ┌──────────── vision_gui ────────────┐
 │ H_boton (FIFO 80)  GPIO17 y GPIO27 │ ───────────────────────────────────────────────────▶ │ H_maquina  máquina de estados      │
 │ H_sensores (nice -5) SPI MCP3008 ──┼──── /dev/shm/pb_status + semáforo POSIX (pot, ldr,  ─▶│ H_compositor (nice 0) tira + fsync │
 │   UART ← STM32 (HC-SR04)           │      distancia, temperatura; 128 B)                  │ cámara IMX708 · pool de 3 fotos    │
 │ H_oled (nice +10) I2C BMP280+OLED  │ ◀──────────────────────── órdenes: beep, estado ──── │ servidor de la pantalla 127.0.0.1:8000
 │ buzzer PWM0 (GPIO18)               │                                                      └─────────────────────────────────────┘
 └────────────────────────────────────┘                  qr_httpd (nice +10): descargas del celular :8080 — lee la tira del disco
```

## 1. Instalar desde cero (Raspberry Pi 4, Raspberry Pi OS 64-bit con escritorio, Debian 13 trixie)
Con la Pi recién grabada, conectada a internet y con el hardware cableado (sección 7):
```bash
git clone https://github.com/JDJR13/Practicas_DivasDown.git
cd Practicas_DivasDown/proyecto-photobooth
sudo ./scripts/instalar.sh        # (o: make instalar) paquetes, buses y UART, los 4 servicios, pantalla en modo kiosco y endurecimiento
sudo reboot                        # la cabina debe aparecer sola en el monitor (~13 s)
```
`instalar.sh` es la suma de estos pasos, que también se pueden correr por separado:

| Paso | Qué hace | Comando |
|---|---|---|
| Paquetes | `python3-lgpio python3-spidev python3-serial python3-pil python3-numpy python3-picamera2 chromium i2c-tools nftables stm32flash dnsmasq-base` | `apt install` |
| Firmware de la Pi | Agrega a `/boot/firmware/config.txt`: `dtparam=i2c_arm=on`, `dtparam=spi=on`, `enable_uart=1`, `dtoverlay=disable-bt`, `dtoverlay=pwm,pin=18,func=2`, `dtparam=watchdog=on`; quita la consola del UART | (dentro de `instalar.sh`) |
| Servicios | Crea y habilita `fotobut-control`, `fotobut-vision`, `fotobut-qr`, `fotobut-monitor` | `sudo ./scripts/instalar_servicios.sh` |
| Pantalla | Chromium a pantalla completa al iniciar la sesión gráfica (autologin) | `./scripts/instalar_autoarranque.sh` |
| Endurecimiento | Cortafuegos, SSH, watchdog de hardware, registros persistentes, aislamiento | `sudo ./scripts/blindar.sh` |
| Wi-Fi propio | Perfil del punto de acceso `Fotobut` | `sudo ./scripts/setup_ap.sh` |

Después: firmware del STM32 (sección 4), llave SSH (`docs/SEGURIDAD.md`) y encender la red de la cabina:

**Red Wi-Fi propia para la descarga** (SSID `Fotobut`, clave `fotobut2026`, cabina en `192.168.4.1`):
```bash
sudo ./scripts/setup_ap.sh            # una sola vez, con la Pi todavía en internet (crea el perfil; instala dnsmasq-base si falta)
./scripts/ap_on.sh --arranque         # enciende la red ahora y en cada arranque (sin --arranque: solo hasta reiniciar)
./scripts/ap_off.sh                   # la apaga y la Pi vuelve a su Wi-Fi normal
```
Usa wlan0: si entras por SSH a través de Wi-Fi la sesión se corta (agrega `--force`, únete a `Fotobut` y entra con `ssh usuario@192.168.4.1`).
Con la red encendida la pantalla de resultado muestra **dos QR**: 1) unirse al Wi-Fi, 2) descargar la tira (`http://192.168.4.1:8080/s/<sesión>`).
Con la red apagada solo sale el QR de descarga con la IP actual de la Pi (sirve si el celular está en esa misma red).

## 2. Probar sin hardware (simulador, en cualquier PC con Python 3.10+, Pillow y numpy)
```bash
make simular        # = python3 run.py --sim: lanza los 4 procesos y los vigila; abre http://127.0.0.1:8000  (panel: http://127.0.0.1:9000)
make probar         # pruebas automáticas
```
Teclas: Espacio = botón rojo · R = botón azul (reset) · ←/→ o 1-5 = potenciómetro (filtro) · P = persona frente al sensor · D = depuración. `?debug` muestra el estado del hardware.

## 3. Pruebas y mediciones (ver `tools/`)
| Qué | Comando |
|---|---|
| Lógica, IPC, carrera de la memoria compartida | `python3 tests/test_machine.py` · `tests/test_ipc.py` · `tests/test_hw.py` · `tests/test_qr.py` |
| Seguridad del servidor de descargas (rutas, límites por IP, slowloris) | `python3 tests/test_share.py` |
| Punto de control, recuperación tras un reinicio y watchdog | `python3 tests/test_recuperacion.py` |
| Caja negra y panel de mantenimiento | `python3 tests/test_monitor.py` |
| Autoauditoría de seguridad en la Pi | `./tools/pruebas/auditar_seguridad.sh` |
| Caja negra desde la terminal · respaldo · restauración | `./tools/mantenimiento/caja_negra.sh` · `./tools/mantenimiento/respaldo.sh` · `./tools/mantenimiento/restaurar.sh ARCHIVO` |
| Requisitos de tiempo contra el Avance 1 | `python3 tools/medicion/resumen_mediciones.py` (después de 8-10 sesiones) |
| Arranque ≤ 25 s | `./tools/medicion/medir_arranque.sh` |
| Prioridades de cada hilo (clase 8) | `./tools/medicion/mostrar_prioridades.sh` |
| RAM y CPU por proceso | `./tools/medicion/monitor_recursos.sh 10` |
| Fallas inducidas y recuperación | `./tools/pruebas/inducir_falla.sh control` · `vision` · `qr` |
| Precision del HC-SR04 + STM32 (con `fotobut-control` detenido) | `python3 tools/medicion/medir_distancia.py 10 30 60 100` |
| Pulsar un botón sin tenerlo cableado (pone el pin a 0 V 150 ms) | `./tools/pruebas/pulsar.sh rojo` · `./tools/pruebas/pulsar.sh azul` |
| Ver en vivo estado, distancia y presencia (para acomodar el sensor) | `./tools/mantenimiento/ver_estado.sh` |
| Latencia y traza del socket (IPC) | `curl -s http://127.0.0.1:8000/api/ipc` · `./tools/medicion/trazar_ipc.sh` |
| Clases 20 y 21 (tipos, volatile, drivers) | `./tools/evidencia/evidencia_clase20_21.sh 2>&1 \| tee /tmp/ev.txt` · `./tools/medicion/contar_syscalls.sh` |
| Dónde está cada decisión de la bitácora (archivo:línea) | `python3 tools/evidencia/mapa_bitacora.py` |

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

## 5. Estructura del proyecto
Organizado por capas (Clase 22): cada carpeta tiene una sola responsabilidad. El detalle de cada módulo, el modelo de ejecución
y por qué se eligió cada mecanismo de comunicación (Clase 23) están en **`docs/ARQUITECTURA.md`**.
```
fotobut/procesos/       arranque de cada proceso: control_daemon, vision_gui, qr_httpd, monitor
fotobut/comunicacion/   IPC (socket Unix, memoria compartida, semáforo) y servidores HTTP
fotobut/logica/         máquina de estados, pool de fotos, filtros, tira, QR
fotobut/servicios/      configuración, caja negra, watchdog, prioridades, telemetría
fotobut/hardware/       botones, ADC, UART, I2C, buzzer, cámara (y su simulador)
firmware_stm32/         firmware del STM32 (C bare-metal)        web/        interfaz y panel
systemd/  seguridad/  scripts/                                   instalación, servicios y endurecimiento
tools/medicion/  tools/pruebas/  tools/mantenimiento/  tools/evidencia/
tests/                  pruebas automáticas                      docs/       arquitectura, diseño, seguridad, recuperación
fotobut.conf            valores ajustables sin tocar el código   Makefile    atajos (make simular, make probar…)
```

**Configuración.** Red Wi-Fi, distancias de presencia, tiempos, tonos y pines se cambian en `fotobut.conf` (clave = valor).
Si el archivo falta se usan los valores por omisión de `fotobut/servicios/config.py`; un valor inválido se ignora y queda
anotado en el registro (`journalctl -u fotobut-vision | grep configuracion`). Después de cambiarlo:
`sudo systemctl restart 'fotobut-*'` (y `sudo ./scripts/setup_ap.sh` si cambió la red Wi-Fi).

## 6. Reglas de la cabina
- Presencia: 5 lecturas seguidas (500 ms a 10 Hz) entre 30 y 120 cm sacan a la cabina del reposo a la pantalla de inicio (y la mantienen
  despierta); para elegir filtro y tomar las fotos siempre hay que presionar el botón rojo. Una lectura fuera de rango reinicia la cuenta
  (`PRESENCE_MIN_CM`, `PRESENCE_MAX_CM` en `config.py`).
- Reposo: **5 s sin nadie en ese rango** (`NO_PRESENCE_S`), en la pantalla de filtros o en la de inicio, llevan a la pantalla de reposo
  (atenuada, "Acércate para despertar"); la presencia o el botón rojo la despiertan. Si el STM32 no manda tramas se usan los respaldos
  (30 s filtros → inicio, 120 s inicio → reposo), porque sin sensor no se puede saber si hay alguien. Durante las fotos y el resultado no aplica.
- Botón rojo (GPIO17, pin 11): empezar / otra sesión. **Botón azul (GPIO27, pin 13): reset** — cancela lo que haya (cuenta regresiva, fotos,
  revelado o resultado) y vuelve al inicio; las fotos de la sesión cancelada se descartan. Ambos van del pin a GND (pull-up interna).
- Potenciómetro (0-1023) → 5 filtros con histéresis. Cuenta regresiva 3-2-1 con tono; 3 fotos; tira lista en ≤ 2.5 s tras la 3ª foto.
- Fotos intermedias en /tmp (RAM); la tira final a la microSD con `fsync` (clase 15). 45 s en resultado → inicio.
- Buzzer: `python3 tools/medicion/buzzer_sweep.py` encuentra la frecuencia que suena más fuerte (`TICK_HZ`, `SHUTTER_HZ` en `config.py`).

## 7. Cableado
| Dispositivo | Conexión en la Raspberry Pi |
|---|---|
| Botón rojo (foto) | GPIO17 (pin 11) a GND; pull-up interna |
| Botón azul (reset) | GPIO27 (pin 13) a GND; pull-up interna |
| Buzzer pasivo | GPIO18 (pin 12, PWM0) y GND |
| MCP3008 (potenciómetro en CH0, LDR en CH1) | SPI0: MOSI pin 19, MISO pin 21, SCLK pin 23, CE0 pin 24; 3.3 V y GND |
| BMP280 (0x77) y OLED SSD1306 (0x3C) | I2C1: SDA pin 3, SCL pin 5; 3.3 V y GND |
| STM32F103 (HC-SR04) | UART: PA9 (TX) → pin 10 (RXD), PA10 (RX) ← pin 8 (TXD), GND común |
| Cámara IMX708 | Conector CSI |
| Monitor de 15.6" | HDMI |

## 8. Interfaz
Recorrido de tres pasos (elige tu filtro → posa → llévate tu tira), con la ruta siempre visible arriba y, abajo, una barra que
dice qué hace cada control físico (perilla, botón rojo, botón azul) en la pantalla actual. Paleta «noche dorada» para combinar
con la cabina dorada y cobriza: fondo azul noche, texto marfil (contraste AAA) y acentos oro y cobre. La pantalla es una página
web que Chromium abre en modo kiosco; el porqué de esa decisión frente a una aplicación nativa, la paleta y las referencias
están en `docs/DISENO.md`.

## 9. Seguridad y recuperación
- **Seguridad** (`docs/SEGURIDAD.md`): a la red solo salen SSH y el puerto 8080; la pantalla (8000) y el panel (9000) escuchan en
  127.0.0.1. Cortafuegos nftables, SSH con llave, servicios sin root y aislados, identificadores de 64 bits que caducan,
  límites por IP. Se comprueba con `./tools/pruebas/auditar_seguridad.sh`.
- **Recuperación** (`docs/RECUPERACION.md`): `Restart=always` revive al proceso que muere, `WatchdogSec` al que se cuelga y el
  watchdog de hardware a la placa entera. La caja negra guarda la salud cada 10 s y los eventos; el punto de control devuelve
  la tira a la pantalla si el proceso cae. Mantenimiento a distancia por SSH: `ssh -L 9000:127.0.0.1:9000 usuario@cabina` y
  abrir `http://127.0.0.1:9000`.
