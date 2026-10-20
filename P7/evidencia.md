# Práctica 7. C embebido: evidencia

Grupo: 06
Integrantes del equipo:
- Rodríguez Dueñas José Luis - 320129690
- Jurado Rosas Josué David - 320220962 (autor de esta evidencia)
- Migueles Martínez Lino Shatini - 320178643
- Ramírez Valdovinos Eric - 423095203
- Rivas Gil Maria Lucia - 320492057
Fecha de realización: 18 y 19 de octubre de 2026
Hardware: Raspberry Pi 4 (`lino`, usuario `papu`), Debian, aarch64, gcc 14.2.0

> Las predicciones se escriben ANTES de ejecutar cada programa.

## Parte A. Entorno y circuito
- `gcc --version`: gcc 14.2.0 (Debian). `uname -m`: aarch64.
- `groups` incluye `gpio`, `i2c` y `spi`.
- Dispositivos: `/dev/gpiomem` (root:gpio, 238,0), `/dev/i2c-1` (89,1), `/dev/spidev0.0` (153,0).
- `i2cdetect -y 1`: aparecen 0x38 y 0x77.
- `pgrep`: sin programas previos. `misistema.service`: inactive.
- (Salida completa de los comandos: ver Figura A, captura del entorno.)
- Dirección I2C del BMP280: 0x77 (el 0x38 es otro dispositivo del bus).
- Qué indica `uname -m` sobre el tipo long: aarch64 es de 64 bits y en Linux de 64 bits `long` mide 8 bytes (modelo LP64).

## Parte B. Tamaños, promoción, padding y orden de bytes
### Predicciones (antes de ejecutar ./tipos)
- sizeof(long): 8 bytes
- a + b (200 + 100) guardado en uint8_t: 44
- ~reg == 0xF0: 0 (falso)
- (uint8_t)~reg == 0xF0: 1 (verdadero)
- sizeof(struct paquete_normal) / sizeof(struct paquete_compacto): 12 y 6 bytes
- Bytes de 0x01020304 en memoria: 04 03 02 01

### Tabla predicción vs real
| Punto | Predicción | Real |
|-------|-----------|------|
| long | 8 | 8 |
| a + b en uint8_t | 44 | 44 (300 → 44) |
| ~reg == 0xF0 | 0 | 0 (~reg = 0xFFFFFFF0) |
| (uint8_t)~reg == 0xF0 | 1 | 1 |
| struct normal | 12 | 12 |
| struct compacto | 6 | 6 |
| 0x01020304 en memoria | 04 03 02 01 | 04 03 02 01 |

### Aviso del compilador
- Texto completo del aviso: `tipos.c:43:17: warning: comparison of promoted bitwise complement of an unsigned value with constant [-Wsign-compare]`
- Línea de tipos.c: 43 (la comparación `~reg == 0xF0`).
- Por qué las dos comparaciones con 0xF0 no dan lo mismo: `reg` es de 8 bits, pero C lo promueve a `int` de 32 bits antes de aplicar `~`, y el resultado es `0xFFFFFFF0`, que no es `0xF0`. Con `(uint8_t)` el resultado se recorta a 8 bits y queda `0xF0`, por eso esa comparación sí es verdadera.
- Bytes de cada struct: normal 12 bytes (`valor` en el offset 4, `crc` en el offset 8); compacta (`packed`) 6 bytes (`valor` en el offset 1, `crc` en el offset 5). El espacio sobrante en `paquete_normal` son 3 bytes de relleno después de `tipo` y 3 al final; su contenido no está definido porque el compilador no lo inicializa.

## Parte C. Bits, máscaras y desbordamiento
### Valores previstos de r (antes de ejecutar ./bits)
| Operación | r previsto | r real |
|-----------|-----------|--------|
| inicio | 0x00000000 | 0x00000000 |
| SET_BIT(r, 17) | 0x00020000 | 0x00020000 |
| SET_BIT(r, 3) | 0x00020008 | 0x00020008 |
| TOGGLE_BIT(r, 17) | 0x00000008 | 0x00000008 |
| CLEAR_BIT(r, 3) | 0x00000000 | 0x00000000 |

### Tabla de los seis pines (calculada a mano)
| Pin | registro (pin/10) | desplazamiento ((pin%10)*3) | máscara (hex) |
|-----|-------------------|-----------------------------|---------------|
| 17 | GPFSEL1 | 21 | 0x00E00000 |
| 27 | GPFSEL2 | 21 | 0x00E00000 |
| 22 | GPFSEL2 | 6 | 0x000001C0 |
| 23 | GPFSEL2 | 9 | 0x00000E00 |
| 5 | GPFSEL0 | 15 | 0x00038000 |
| 6 | GPFSEL0 | 18 | 0x001C0000 |

- Cambio hecho en bits.c para el pin 22: `GPFSEL1` → `GPFSEL2`, `desplazamiento = 21` → `desplazamiento = 6`, y las etiquetas de GPIO17 a GPIO22. Resultado: máscara `0x000001C0`, valor tras el cambio `0xFFFFFE7F`, campo leído de vuelta = 1 (salida).
- Qué pasa si se quita el ~mascara: la línea queda `gpfsel | (1u << desplazamiento)`. Con el campo previo en `111`, el `|` no puede apagar bits, así que el registro queda en `0xFFFFFFFF` y el campo leído de vuelta es 7 (no 1). Un `|` solo enciende bits; sin borrar primero el campo, el pin queda en otra función alterna y no como salida.
- Línea del detector de desborde_ub y desde qué iteración aparece: `desborde.c:13:18: runtime error: signed integer overflow: 2147483647 + 1 cannot be represented in type 'int'`. Aparece al llegar a la iteración 3, que es cuando `con_signo` pasa de 2147483647 a -2147483648.
- Qué columna de desborde tiene comportamiento garantizado por el estándar y cuál no: la de `uint32_t` (sin signo) está garantizada, porque da la vuelta módulo 2^32 (con `./desborde 4294967290` pasa de 4294967295 a 0). La de `int` (con signo) no: el desborde con signo es comportamiento indefinido, aunque en esta máquina se vea que pasa a -2147483648.
- Un caso de tu circuito donde elegirías un tipo sin signo: los registros de 32 bits del GPIO (GPFSEL, GPLEV, GPSET), porque las máscaras y los desplazamientos de bits deben tener un comportamiento definido; también el valor de 10 bits del potenciómetro (0 a 1023), que nunca es negativo.

## Parte D. Registros reales del GPIO
- Predicción de la función de cada pin (antes de ejecutar ./regs_leer): pines 2 y 3 en ALT0 (I2C, P3); pines 8, 9, 10 y 11 en ALT0 (SPI, P3); pines 5 y 6 en entrada (botones); pines 17, 27, 22 y 23 en entrada (LEDs sin usar).
- Salida de regs_leer: pin 2 ALT0, nivel 1; pin 3 ALT0, nivel 1; pin 8 campo 1 = **salida**, nivel 1; pines 9, 10 y 11 ALT0, nivel 0; pines 5, 6, 17, 27, 22 y 23 entrada, nivel 0.
- Funciones de los pines 2, 3, 8 a 11 y qué práctica los dejó así: 2 y 3 en ALT0 por el I2C habilitado en la P3 (BMP280); 9, 10 y 11 en ALT0 por el SPI de la P3 (MCP3008); el pin 8 (CE0) **no** está en ALT0 sino como salida. Mi predicción para el pin 8 fue incorrecta: el driver SPI del kernel (`spi-bcm2835`) maneja CE0 como un chip select por software, es decir, un GPIO de salida en nivel alto en reposo (activo en bajo).
- En qué coincide y en qué se distingue gpioinfo de lo leído en el registro (`gpioinfo -c gpiochip0`, con libgpiod v2): coinciden en 5, 6, 17, 22, 23 y 27 (input) y en el 8 (output, consumidor `spi0 CS0`). Se distinguen en 2, 3, 9, 10 y 11: el registro dice ALT0, pero gpioinfo solo ve `input`, porque no conoce las funciones alternas de esos pines. En cambio, gpioinfo informa quién usa el pin 8 (`spi0 CS0`) y el registro no.
- Qué observaste en los LEDs en cada etapa y salida de GPLEV0 & mascara: con los cuatro LEDs `0x08C20000`; apagados `0x00000000` (tres rondas); solo uno a la vez, sin lectura; con GPIO17 y GPIO22 `0x00420000`.
  - Incidente: en las primeras corridas la última etapa dio `0x08420000` (bit 27 alto sin haberlo escrito). Con un programa de diagnóstico que enciende cada LED por separado, GPIO22 y GPIO27 se leían altos a la vez, o sea que estaban unidos eléctricamente por un cortocircuito en el cableado (pines físicos 15 y 13). Se corrigió el cableado y el diagnóstico dio: solo17 `0x00020000`, solo27 `0x08000000`, solo22 `0x00400000`, solo23 `0x00800000`, 17+22 `0x00420000`. Después el programa dio el resultado esperado.
- Máscara para encender solo GPIO17 y GPIO22 (hex): `0x00420000` (bit 17 + bit 22).
- Escrituras a registros para encender los cuatro LEDs aquí vs llamadas en la Práctica 2: aquí es **una** escritura a GPSET0 con la máscara `BIT(17)|BIT(27)|BIT(22)|BIT(23)` (y una a GPCLR0 para apagarlos). En la P2 (`leds.c`, libgpiod v2): 8 llamadas de configuración (`gpiod_chip_open`, `line_settings_new`, `set_direction`, `line_config_new`, `add_line_settings`, `request_config_new`, `set_consumer`, `chip_request_lines`), luego **4** llamadas `gpiod_line_request_set_value`, una por LED, dentro de un bucle (línea 49; otras 4 para apagarlos, línea 53), y 5 llamadas para cerrar (`release`, tres `free` y `chip_close`). Comparación: encender los cuatro LEDs aquí cuesta 1 escritura a GPSET0, mientras que en la P2 cuesta 4 llamadas a la librería, y cada una termina en una llamada al kernel; además, la P2 necesita 13 llamadas de preparación y cierre que aquí se reducen a un `mmap` y a leer/escribir GPFSEL.
- Función de los pines 17, 27, 22 y 23 al terminar leds_regs (gpioinfo) y razón del cambio: quedan como `input`, porque al terminar el programa devuelve cada pin a entrada con `configurar(..., 0)`, para no dejar salidas activas manejando los LEDs.

## Parte E. volatile con el botón físico
- Predicción (cuáles de las 4 versiones detectan el botón): b_con_O0, b_sin_O0 y b_con_O2 sí; b_sin_O2 no (se queda esperando y `timeout` lo corta con código 124).
- Resultado y código de salida de cada una:
  - b_con_O0: detecta, código 0
  - b_sin_O0: detecta, código 0
  - b_con_O2: detecta, código 0
  - b_sin_O2: en el primer intento detectó (código 0), porque el botón seguía presionado cuando arrancó y la única lectura de GPLEV0 vio 1. Repetida sin tocar el botón al inicio: no detecta, código 124 (confirma la predicción).
- Líneas de ensamblador que leen el offset 52 en con.s y sin.s (aarch64, `-O2`):
  - con.s (con volatile): `.L5: ldr w0, [x19, 52]` (línea 65), seguida de `tbz x0, 5, .L5` (línea 66): la lectura está dentro del ciclo y se repite.
  - sin.s (sin volatile): `ldr w0, [x19, 52]` (línea 63), `tbz x0, 5, .L6` (línea 64) y `.L6: b .L6` (línea 84): una sola lectura antes del ciclo; el ciclo es un salto a sí mismo.
  - El offset 52 es 0x34, el registro GPLEV0; el bit 5 es GPIO5.
- Qué hizo el compilador con la versión sin volatile y por qué el botón no cambió el resultado: como el programa nunca escribe en GPLEV0, el compilador supone que su valor no cambia y lo lee una sola vez, antes del ciclo. Si en esa lectura el bit 5 era 0, queda en `b .L6` para siempre, sin volver a leer el registro. El botón cambia el hardware, pero el programa ya no mira el registro, así que no ve el cambio.
- Dos registros de tu circuito que deben leerse con volatile y una variable que no lo necesita: GPLEV0 (el hardware cambia su valor según el nivel del pin) y GPSET0/GPCLR0 (o GPFSEL), cuyas escrituras tienen efectos laterales que el compilador no debe eliminar, unir ni reordenar. Una variable que no lo necesita: un contador local de un `for` o una constante como `TRAMO`, que solo el programa lee y escribe.

## Parte F. Bytes de los sensores
- Salida completa de sensores y dirección usada (`./sensores 77`):
  - `dig_T1 = 27539, dig_T2 = 25891, dig_T3 = 50`
  - Corrida 1: pot 1023, 1023, 383, 0, 0; T = 25.10, 25.10, 25.11, 25.11, 25.12 °C
  - Corrida 2: pot 1023, 1023, 383, 383, 1023; T = 25.17, 25.17, 25.17, 25.16, 25.15 °C
  - (Una primera corrida con la perilla en el extremo dio pot = 0 en las cinco lecturas, con T = 24.28, 24.56, 24.60, 24.61, 24.61 °C.)
- Mínimo y máximo del potenciómetro con su voltaje: mínimo 0 (0.00 V), máximo 1023 (3.30 V); un valor intermedio fue 383 (1.24 V).
- Cambio de cruda y de la temperatura con el dedo sobre el sensor: PENDIENTE (opcional, no se hizo). Sin tocar el sensor, la cruda subió de 519264 a 520352 (24.28 a 24.61 °C) en la primera corrida por el calentamiento inicial.
- Cálculo manual de cruda (a partir de los tres bytes de una línea) vs valor impreso: bytes `7E C6 00` → `(0x7E << 12) | (0xC6 << 4) | (0x00 >> 4) = 0x7E000 + 0xC60 + 0 = 0x7EC60 = 519264`, igual al valor impreso.
- Valor de dig_T1 si leer_u16_le combinara los bytes en orden contrario: `dig_T1 = 27539 = 0x6B93`, que el sensor guarda como `93 6B`. Con el orden contrario quedaría `0x936B = 37739`, y la temperatura calculada saldría absurda.
- Qué haría mcp3008_valor sin la máscara `& 0x03u`: el MCP3008 solo usa los 2 bits bajos del segundo byte (bits 9 y 8 del resultado); los otros 6 bits no son dato. Sin la máscara, esos bits se sumarían al valor y podría pasar de 1023.

## Reto final. panel.c
- Salida de la compilación (sin avisos): `gcc -std=gnu11 -Wall -Wextra -Wconversion -O0 -g -o panel panel.c`, sin ninguna línea de aviso.
- Salida de una ejecución con las dos pulsaciones:
  ```
  BMP280 en 0x77: dig_T1 = 27539, dig_T2 = 25891, dig_T3 = 50
  Pines de I2C y SPI (al iniciar): GPIO2=ALT0 GPIO3=ALT0 GPIO8=salida GPIO9=ALT0 GPIO10=ALT0 GPIO11=ALT0
  Panel listo. GPIO5: congelar/reanudar barra, GPIO6: temperatura, Ctrl+C: salir
  Temperatura: 24.35 C | potenciometro: 383
  Barra congelada
  ^CPines 2, 3, 8, 9, 10 y 11 sin cambios (al terminar)
  Panel terminado: LEDs apagados
  ```
- Una frase por condición de aceptación (en qué parte del código se cumple):
  1. Compila sin avisos con -Wall -Wextra -Wconversion y corre sin sudo: la compilación no muestra avisos, y se ejecuta con el usuario `papu`, que está en los grupos `gpio`, `i2c` y `spi`.
  2. Acceso por struct con volatile sobre /dev/gpiomem, sin gpiod.h: `gpio_regs.h` define `gpio_regs_t` con campos `volatile` y los mapea con `mmap` sobre `/dev/gpiomem` en `gpio_abrir()`; `panel.c` no incluye `gpiod.h`.
  3. Pines modificados solo con leer, borrar campo, escribir: `configurar()` lee el GPFSEL, borra el campo de 3 bits del pin y escribe el valor nuevo.
  4. Solo se escribe en los pines 17, 27, 22, 23, 5 y 6: `pin_permitido()` rechaza cualquier otro pin antes de escribir, y las escrituras a GPSET/GPCLR usan solo `LED_MASCARA`.
  5. Pines 2, 3, 8 a 11 se verifican al iniciar y al terminar: `leer_bus()` y `mostrar_bus()` muestran su función al iniciar, y `verificar_bus()` compara al terminar contra lo leído al inicio. Solo se leen, nunca se escriben. (El pin 8 queda como salida por diseño del driver SPI, no en ALT0.)
  6. Temperatura con los coeficientes leídos del propio sensor: `bmp_calibracion()` lee `dig_T1`, `dig_T2` y `dig_T3` de los registros 0x88 en adelante y `bmp_compensar()` los usa.
- Cómo se evita contar una pulsación más de una vez, e intervalo de muestreo: `boton_pulsado()` muestrea cada 10 ms (`PERIODO_US`) y solo acepta un nivel tras 3 muestras iguales seguidas (30 ms, `ESTABLE`), lo que filtra el rebote. Cuenta la pulsación únicamente en la transición de 0 a 1, así que mantener el botón presionado produce una sola línea (comprobado: una pulsación de unos 3 segundos dio una sola línea de temperatura).

## Parte G. Commit
- Salida de git status, git commit y git log --stat -1: PENDIENTE (se hace al tener conexión y hora sincronizada).
