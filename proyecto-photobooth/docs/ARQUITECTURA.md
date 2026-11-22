# Arquitectura de El Fotobut

Cómo está organizado el programa para que otra persona lo entienda, lo cambie o lo replique. Sigue la organización por
capas de la Clase 22 (software de aplicación) y justifica la comunicación entre programas con los criterios de la
Clase 23 (middleware).

## 1. Las carpetas del repositorio

```
proyecto-photobooth/
├── README.md              cómo instalar, probar y usar (empieza aquí)
├── Makefile               atajos: make simular · make probar · make instalar · make firmware
├── fotobut.conf           valores que ajusta quien instala (Wi-Fi, distancias, tiempos, tonos, pines)
├── run.py                 lanzador de desarrollo: los 4 procesos con el simulador
├── kiosk.sh               abre la pantalla (Chromium a pantalla completa)
├── fotobut/               aplicación de la Raspberry Pi (Python), una carpeta por capa
│   ├── procesos/          arranque de cada proceso (el "main.c" de cada uno)
│   ├── comunicacion/      IPC entre procesos y servidores HTTP
│   ├── logica/            máquina de estados, pool de fotos, filtros, tira, QR
│   ├── servicios/         configuración, caja negra, watchdog, prioridades
│   └── hardware/          botones, ADC, UART, I2C, buzzer, cámara
├── firmware_stm32/        firmware del microcontrolador (C bare-metal), con su Makefile
├── web/                   interfaz de la pantalla y panel de mantenimiento (HTML, CSS, JS, fuentes)
├── systemd/               unidades de los 4 servicios
├── seguridad/             cortafuegos y aislamiento de cada servicio
├── scripts/               instalación, red Wi-Fi y endurecimiento
├── tools/
│   ├── medicion/          arranque, recursos, prioridades, distancia, IPC, buzzer
│   ├── pruebas/           fallas inducidas, pulsar botones, auditoría de seguridad
│   ├── mantenimiento/     caja negra, respaldo, restauración, estado en vivo
│   └── evidencia/         material de la bitácora (tipos, volatile, mapa archivo:línea)
├── tests/                 pruebas automáticas (corren en cualquier PC)
└── docs/                  arquitectura, diseño, seguridad y recuperación
```

## 2. Capas de la aplicación (Clase 22)

```
 ┌──────────────────────────────────────────────────────────────┐
 │ Comunicación e interfaz   comunicacion/  +  web/              │  cambia con la aplicación
 ├──────────────────────────────────────────────────────────────┤
 │ Lógica                    logica/                             │
 ├──────────────────────────────────────────────────────────────┤
 │ Servicios                 servicios/   (las usan todas)       │
 ├──────────────────────────────────────────────────────────────┤
 │ Acceso al hardware        hardware/                           │  cambia con el hardware
 ├──────────────────────────────────────────────────────────────┤
 │ Drivers del kernel  /dev/gpiochip0 · /dev/spidev0.0 · /dev/ttyAMA0 · /dev/i2c-1 · pwmchip0 · cámara │
 └──────────────────────────────────────────────────────────────┘
```

| Capa | Módulo | Qué hace |
|---|---|---|
| **Procesos** | `procesos/control_daemon.py` | Proceso 1: dueño del hardware; hilos del botón, sensores, OLED y socket |
| | `procesos/vision_gui.py` | Proceso 2: cámara, máquina de estados y servidor de la pantalla |
| | `procesos/qr_httpd.py` | Proceso 3: descargas del celular |
| | `procesos/monitor.py` | Proceso 4: caja negra y panel de mantenimiento |
| **Comunicación** | `comunicacion/ipc.py` | Socket Unix, memoria compartida y semáforo POSIX entre procesos |
| | `comunicacion/remote_hal.py` | El hardware visto desde `vision_gui` (a través del IPC) |
| | `comunicacion/server.py` | Servidor de la pantalla (127.0.0.1:8000): página, eventos, vista previa |
| | `comunicacion/share.py` | Servidor de descargas (puerto 8080) con sus límites de seguridad |
| **Lógica** | `logica/machine.py` | Máquina de estados de la sesión y punto de control |
| | `logica/pool.py` | Pool estático de 3 fotos con semáforos (productor-consumidor) |
| | `logica/filters.py` · `strip.py` · `qr.py` | Filtros de color, armado de la tira, códigos QR |
| **Servicios** | `servicios/config.py` | Valores por omisión y lectura de `fotobut.conf` |
| | `servicios/caja_negra.py` | Registro de salud y eventos en la microSD |
| | `servicios/vigia.py` | Señal de vida para el watchdog de systemd |
| | `servicios/sched.py` | Prioridad de cada hilo (Clase 8) |
| | `servicios/telemetry.py` | Temperatura, memoria e IP hacia la OLED |
| **Hardware** | `hardware/hal.py` | Botones (GPIO), potenciómetro (SPI), STM32 (UART), buzzer (PWM); y su simulador |
| | `hardware/i2c.py` · `oled.py` | BMP280 y pantalla OLED por I2C |
| | `hardware/camera.py` | Cámara (picamera2) y su simulador |

**Reglas que se respetan**

- La lógica no importa nada de `hardware/`: recibe las entradas por una interfaz (`read()`, `beep()`), por eso se
  prueba en cualquier PC con el simulador (`tests/test_machine.py`).
- Cada módulo de `procesos/` solo une módulos de las otras capas y arranca sus hilos; no contiene decisiones.
- Si se cambia un sensor (por ejemplo, el potenciómetro por un encoder), solo cambia `hardware/hal.py`.
- Los valores que cambian tienen nombre y un solo lugar (`servicios/config.py`); los que ajusta quien instala, además,
  se pueden cambiar en `fotobut.conf` sin tocar el código.

## 3. Modelo de ejecución (Clase 22)

Hilos o procesos separados, porque hay trabajo largo que no debe frenar al resto: componer la tira tarda más de 1 s y
el botón debe atenderse en milisegundos.

| Proceso | Hilos principales | Prioridad |
|---|---|---|
| `control_daemon` | H_boton (sondeo cada 4 ms), H_sensores (20 Hz), H_oled (1 Hz), H_socket | FIFO 80 · nice −5 · +10 · 0 |
| `vision_gui` | H_maquina, H_compositor, servidor de la pantalla, H_ipc_rx | nice −10 |
| `qr_httpd` | servidor de descargas | nice +10 |
| `monitor` | muestreo de salud cada 10 s, panel | nice +15 |

Ante una falla: `systemd` reinicia el proceso que muere (`Restart=always`), el watchdog reinicia el que se cuelga
(`WatchdogSec=`) y el watchdog de hardware reinicia la placa si se congela todo. Detalle en `docs/RECUPERACION.md`.

## 4. Comunicación entre programas (Clase 23)

```
 control_daemon ══ socket Unix (64 B, eventos y órdenes) ══▶ vision_gui ── SSE / MJPEG ──▶ Chromium (pantalla)
       │                                                        │
       └──── memoria compartida /dev/shm/pb_status ────────────▶┘   (+ semáforo POSIX y seqlock)
 vision_gui ── archivos de la sesión (/tmp y microSD) ──▶ qr_httpd ── HTTP :8080 ──▶ celular
 monitor ── HTTP local (consulta /api/state y /salud) ──▶ vision_gui, qr_httpd
 STM32 ── UART 115200 ("DIST:123 cm") ──▶ control_daemon
```

| Enlace | Mecanismo | Por qué ese y no otro |
|---|---|---|
| Botón y órdenes (beep, estado) entre `control_daemon` y `vision_gui` | **Socket Unix** `SOCK_SEQPACKET` | Bidireccional, local y con límites de mensaje; avisa al instante (latencia medida: mediana 234 µs) |
| Lecturas de sensores a 20 Hz | **Memoria compartida** + semáforo | La más rápida en el mismo equipo; solo importa el último valor, no la cola de mensajes |
| Tira terminada hacia `qr_httpd` | **Archivos** | Aislamiento de fallas: si cualquiera de los dos procesos cae, el otro sigue |
| Pantalla | **HTTP + Server-Sent Events** en 127.0.0.1 | El navegador ya lo habla; el estado llega empujado, sin preguntar a cada rato |
| Celular | **HTTP** en el puerto 8080 | El celular no necesita ninguna app |
| STM32 | **UART** | Dos cables; el microcontrolador no tiene sistema operativo |

**Por qué no MQTT ni D-Bus.** Con el árbol de decisión de la Clase 23: todos los procesos están en la misma
computadora, así que no hace falta un broker de red (MQTT). D-Bus sirve para hablar con servicios del sistema; el único
caso que tenemos es encender la red Wi-Fi, y lo hace `nmcli`, que por dentro usa D-Bus para hablar con NetworkManager.
MQTT tendría sentido si varias cabinas mandaran su estado a una central, o si se quisiera ver la salud desde otra red;
quedaría como trabajo futuro (temas `fotobut/<cabina>/estado` retenido con testamento y `fotobut/<cabina>/salud`).

## 5. Para replicar la cabina

1. Hardware y cableado: `README.md`, sección de cableado.
2. Grabar Raspberry Pi OS (64 bits, con escritorio), clonar el repositorio y `make instalar`.
3. Ajustar `fotobut.conf` si cambian la red, las distancias o los pines.
4. Firmware del STM32: `make firmware` y `make flash-stm32`.
5. Comprobar: `make probar` (en cualquier PC) y `make auditar` (en la Pi).
