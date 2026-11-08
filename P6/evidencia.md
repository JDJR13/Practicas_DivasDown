## Parte B
hola                   12288  0
[ 1956.002749] hola: modulo cargado
[ 1956.075889] hola: modulo descargado
[ 1972.563071] hola: modulo cargado
[ 1956.075889] hola: modulo descargado
[ 1972.563071] hola: modulo cargado
[ 1972.633785] hola: modulo descargado
## Parte C
[ 2091.133208] parametros: veces=9 fuera de rango (1 a 5)
[ 2094.844496] parametros: hola FSE (1 de 3)
[ 2094.844520] parametros: hola FSE (2 de 3)
[ 2094.844527] parametros: hola FSE (3 de 3)
total 0
-r--r--r-- 1 root root 4096 Oct 10 16:26 nombre
-rw-r--r-- 1 root root 4096 Oct 10 16:26 veces
FSE
3
5
tee: /sys/module/parametros/parameters/nombre: Permission denied
otro
[ 2094.844527] parametros: hola FSE (3 de 3)
[ 2095.013698] parametros: adios FSE, veces vale 5 al descargar
insmod: ERROR: could not insert module parametros.ko: Invalid parameters
[ 2095.013698] parametros: adios FSE, veces vale 5 al descargar
[ 2095.074367] parametros: veces=9 fuera de rango (1 a 5)
## Parte D
hola desde bash
corto
256
-bash: printf: write error: No space left on device
codigo de salida: 1
256
[ 2134.401695] p6buf: /dev/p6buf creado, minor 266
[ 2182.317866] p6buf: open (pid 1968, proceso bash)
[ 2182.317943] p6buf: write de 16 bytes (pid 1968)
[ 2182.321907] p6buf: open (pid 1970, proceso cat)
[ 2182.322912] p6buf: open (pid 1968, proceso bash)
[ 2182.322999] p6buf: write de 6 bytes (pid 1968)
[ 2182.326877] p6buf: open (pid 1971, proceso cat)
[ 2182.338016] p6buf: open (pid 1968, proceso bash)
[ 2182.338291] p6buf: write de 256 bytes (pid 1968)
[ 2182.339587] p6buf: open (pid 1973, proceso bash)
[ 2182.348491] p6buf: open (pid 1968, proceso bash)
[ 2182.350507] p6buf: open (pid 1975, proceso bash)
## Parte E
openat(AT_FDCWD</home/papu/P2/practica06>, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3</etc/ld.so.cache>
close(3</etc/ld.so.cache>)              = 0
openat(AT_FDCWD</home/papu/P2/practica06>, "/lib/aarch64-linux-gnu/libc.so.6", O_RDONLY|O_CLOEXEC) = 3</usr/lib/aarch64-linux-gnu/libc.so.6>
read(3</usr/lib/aarch64-linux-gnu/libc.so.6>, "\177ELF\2\1\1\3\0\0\0\0\0\0\0\0\3\0\267\0\1\0\0\0\200$\2\0\0\0\0\0"..., 832) = 832
close(3</usr/lib/aarch64-linux-gnu/libc.so.6>) = 0
openat(AT_FDCWD</home/papu/P2/practica06>, "/dev/p6buf", O_RDWR) = 3</dev/p6buf>
write(3</dev/p6buf>, "mensaje de prueba", 17) = 17
lseek(3</dev/p6buf>, 0, SEEK_SET)       = 0
read(3</dev/p6buf>, "mensaje de prueba", 255) = 17
close(3</dev/p6buf>)                    = 0
write(1<pipe:[14649]>, "el driver devolvio 17 bytes: men"..., 47el driver devolvio 17 bytes: mensaje de prueba
) = 47
+++ exited with 0 +++
[ 2252.214331] p6buf: open (pid 1980, proceso cliente)
[ 2252.214387] p6buf: write de 17 bytes (pid 1980)
[ 2252.315004] p6buf: open (pid 1987, proceso cliente)
[ 2252.315240] p6buf: write de 17 bytes (pid 1987)
## Parte F
lectura de memoria de usuario:      3.3 ns por operacion
syscall getppid:                  479.4 ns por operacion
pread sobre /dev/p6buf:           599.2 ns por operacion
transferencia SPI de 3 bytes:  35911.7 ns por operacion
lectura de memoria de usuario:      1.2 ns por operacion
syscall getppid:                  446.5 ns por operacion
pread sobre /dev/p6buf:           597.8 ns por operacion
transferencia SPI de 3 bytes:  35732.1 ns por operacion
lectura de memoria de usuario:      1.1 ns por operacion
syscall getppid:                  453.0 ns por operacion
pread sobre /dev/p6buf:           591.1 ns por operacion
transferencia SPI de 3 bytes:  35464.2 ns por operacion
## Parte G
 89 i2c
153 spi
237 gpiomem
254 gpiochip
bcm2835 (i2c@7e804000)
fef04500.i2c
fef09500.i2c
lrwxrwxrwx 1 root root 0 Oct  5 19:31 /sys/devices/platform/soc/fe200000.gpio/gpiochip0/../driver -> ../../../../bus/platform/drivers/pinctrl-bcm2835
## Parte G (strace)
--- bmp280_id
ioctl I2C_RDWR: Remote I/O error
2049  openat(AT_FDCWD</home/papu/P2>, "/dev/i2c-1", O_RDWR) = 3</dev/i2c-1>
2049  ioctl(3</dev/i2c-1>, _IOC(_IOC_NONE, 0x7, 0x7, 0), 0x7fdff545c8) = -1 EREMOTEIO (Remote I/O error)
--- leer_pot
2055  openat(AT_FDCWD</home/papu/P2>, "/dev/spidev0.0", O_RDWR) = 3</dev/spidev0.0>
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_WR_MODE, 0x7fdabfb30f) = 0
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_WR_BITS_PER_WORD, 0x7fdabfb30e) = 0
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_WR_MAX_SPEED_HZ, 0x7fdabfb308) = 0
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
2055  ioctl(3</dev/spidev0.0>, SPI_IOC_MESSAGE(32), 0x7fdabfb2d8) = 3
## Parte A (headers)
6.18.34+rpt-rpi-v8
aarch64
arm64
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
gcc (Debian 14.2.0-19) 14.2.0
/lib/modules/6.18.34+rpt-rpi-v8/build/Makefile
/usr/src/linux-headers-6.18.34+rpt-rpi-v8
## Parte B (ps y /proc/modules)
papu        2079  0.0  0.0   6260  2024 pts/0    S+   16:39   0:00 grep --color=auto hola
hola 12288 0 - Live 0x0000000000000000 (O)
coresize
holders
initsize
initstate
notes
refcnt
sections
srcversion
taint
uevent
## Parte C (veces=9)
insmod: ERROR: could not insert module parametros.ko: Invalid parameters
codigo de salida: 1
[ 2868.953866] hola: modulo descargado
[ 2869.009466] parametros: veces=9 fuera de rango (1 a 5)
## Parte D (faltantes)
266 p6buf
tr: write error: No space left on device
codigo de salida: 1
hola kernel
## Parte E (demo_ipc)
read(3, "\177ELF\2\1\1\3\0\0\0\0\0\0\0\0\3\0\267\0\1\0\0\0\200$\2\0\0\0\0\0"..., 832) = 832
pipe2([3, 4], 0)                        = 0
clone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID|CLONE_CHILD_SETTID|SIGCHLDstrace: Process 2113 attached
, child_tidptr=0x7f91b090f0) = 2113
[pid  2112] write(4, "hola desde el padre", 19) = 19
[pid  2113] read(3, "hola desde el padre", 63) = 19
[pid  2113] +++ exited with 0 +++
--- SIGCHLD {si_signo=SIGCHLD, si_code=CLD_EXITED, si_pid=2113, si_uid=1000, si_status=0, si_utime=0, si_stime=0} ---
write(1, "Padre (pid 2112) termino\n", 25Padre (pid 2112) termino
) = 25
+++ exited with 0 +++
## Parte G (identificacion de drivers)
crw-rw----+ 1 root gpio 254,   0 Oct  5 19:31 /dev/gpiochip0
crw-rw----  1 root i2c   89,   1 Oct  5 19:31 /dev/i2c-1
crw-rw-rw-  1 root root  10, 266 Oct 10 16:27 /dev/p6buf
crw-rw----  1 root spi  153,   0 Oct  5 19:31 /dev/spidev0.0
raspberrypi_gpiomem    12288  0
i2c_dev                16384  0
spidev                 20480  0
i2c_bcm2835            16384  0
i2c_brcmstb            12288  0
spi_bcm2835            20480  0
gpiochip0 [pinctrl-bcm2711] (58 lines)
gpiochip1 [raspberrypi-exp-gpio] (8 lines)
i2c-1
i2c-20
i2c-21
brcmstb-i2c
i2c-bcm2835
pinctrl-bcm2712
pinctrl-bcm2835
pinctrl-rp1
spi-bcm2835

## Respuestas (Partes A a G)

### Parte A
- `readlink` devuelve `/usr/src/linux-headers-6.18.34+rpt-rpi-v8`, que termina igual que `uname -r` (`6.18.34+rpt-rpi-v8`): los headers coinciden con el kernel en ejecucion.

### Parte B
- Entre la carga y la descarga pasaron unos 0.07 s (1956.002749 -> 1956.075889 = 0.073 s; 1972.563071 -> 1972.633785 = 0.071 s).
- `hola` no aparece en `ps` (solo la linea del propio grep) y si aparece en `lsmod` y `/proc/modules`: un modulo no es un proceso, es codigo que corre dentro del kernel y no tiene PID; `lsmod` lista los modulos que el kernel tiene cargados.
- La columna `Used by` es el contador de referencias: cuantos procesos o modulos usan ese modulo (seguido de los modulos que dependen de el). Mientras sea mayor que 0, `rmmod` no lo descarga.

### Parte C
- Permisos: `nombre` es `-r--r--r--` por `module_param(nombre, charp, 0444);` y `veces` es `-rw-r--r--` por `module_param(veces, int, 0644);`.
- Tras escribir 5 en sysfs, al descargar `dmesg` mostro `adios FSE, veces vale 5 al descargar`. La modifico root (con `tee`) a traves del archivo de sysfs, y la variable `veces` vive en la memoria del kernel (datos del modulo), no en un programa de usuario.
- Con `veces=9`: `insmod: ERROR: could not insert module parametros.ko: Invalid parameters`, codigo de salida 1. El modulo no quedo cargado (`lsmod | grep parametros` no imprimio nada) porque la funcion de inicio devolvio `-EINVAL`.

### Parte D
- `crw-rw-rw- 1 root root 10, 266 ... /dev/p6buf`: la `c` indica un dispositivo de caracteres (no un archivo normal). `10, 266` son el major y el minor: 10 es la clase `misc` y 266 es el minor dinamico de p6buf (`/proc/misc` lista `266 p6buf`); ocupan el lugar del tamano porque un archivo de dispositivo no tiene tamano, solo identifica al driver y al dispositivo. Los permisos `rw` para todos vienen de `.mode = 0666`.
- Las lineas de `dmesg` de `open` y `write` (con proceso y pid) estan en la salida de esta Parte D.
- La escritura de 300 bytes fallo con `No space left on device`, que es `ENOSPC` (errno 28), devuelto por `p6_write` porque `n > TAM_BUF`. El contenido del buffer no cambio: `cat` siguio mostrando `hola kernel`.

### Parte E
- Las lineas de `strace ./cliente` sobre `/dev/p6buf`: `openat(...) = 3`, `write(3, ..., 17) = 17`, `lseek(3, 0, SEEK_SET) = 0`, `read(3, ..., 255) = 17`, `close(3) = 0`.
- `openat` produjo `open (pid 1987, proceso cliente)` y `write` produjo `write de 17 bytes (pid 1987)`. `lseek`, `read` y `close` no producen mensaje: `p6_read` no tiene `pr_info`, `lseek` usa la rutina generica y el driver no define `release`.
- `demo_ipc`: `pipe2([3, 4], 0) = 0` crea el pipe; `clone(... SIGCHLD) = 2113` es el fork; el padre hace `write(4, "hola desde el padre", 19) = 19` y el hijo `read(3, ..., 63) = 19`.
- Ambos programas usan las mismas syscalls genericas (`read`, `write`) sobre un descriptor, y el kernel decide a que codigo mandarlas segun lo que hay detras de ese descriptor. En `demo_ipc` ese codigo es del propio kernel (el pipe de `fs/pipe.c` y la creacion de procesos con `clone`) y en `cliente` es el de nuestro modulo (`p6_read` y `p6_write`).

### Parte F
Medianas de las tres corridas:

| Operacion | Mediana |
|---|---|
| lectura de memoria de usuario | 1.2 ns |
| syscall getppid | 453.0 ns |
| pread sobre /dev/p6buf | 597.8 ns |
| transferencia SPI de 3 bytes | 35732.1 ns |

- `memoria` es `volatile` para que el compilador haga la lectura real en cada vuelta; sin eso, con `-O2` veria un lazo sin efecto y lo eliminaria o sacaria la lectura del lazo, y mediria ~0 ns.
- 100,000 lecturas por segundo con `pread`: 100,000 x 597.8 ns = 59.8 ms de cada segundo, es decir 5.98 %.
- SPI: 1 s / 35.7321 us = unas 27,986 lecturas del MCP3008 por segundo como maximo. Cada transferencia tarda 35732.1 / 597.8 = 59.8 veces lo que un `pread` sobre `/dev/p6buf`.

### Parte G
Observacion: `sensor_combinado.c` no compila con la libgpiod 2.x de Debian 13 (usa la API 1.x), asi que se trazaron `bmp280_id` y `leer_pot` por separado y se omite el archivo del GPIO.

| Ruta | ioctl principal | major, minor | Driver |
|---|---|---|---|
| /dev/i2c-1 | I2C_RDWR (strace lo muestra como _IOC(_IOC_NONE, 0x7, 0x7, 0)) | 89, 1 | i2c_dev (modulo) sobre i2c_bcm2835 |
| /dev/spidev0.0 | SPI_IOC_MESSAGE (mas WR_MODE, WR_BITS_PER_WORD y WR_MAX_SPEED_HZ) | 153, 0 | spidev (modulo) sobre spi_bcm2835 |
| /dev/gpiochip0 | no trazado | 254, 0 | pinctrl-bcm2835 (gpiodetect lo reporta como pinctrl-bcm2711) |

- En `lsmod` aparecen `i2c_dev`, `spidev`, `i2c_bcm2835`, `spi_bcm2835` (tambien `i2c_brcmstb` y `raspberrypi_gpiomem`). No aparece el controlador GPIO porque esta integrado en el kernel. Evidencia de que existe y esta activo: `gpiodetect` lista `gpiochip0 [pinctrl-bcm2711] (58 lines)`, existe `/dev/gpiochip0` (major 254) y `/sys/bus/platform/drivers/pinctrl-bcm2835` existe.
- `/sys/bus/i2c/devices` lista solo los buses `i2c-1`, `i2c-20` e `i2c-21` y ninguna entrada de dispositivo (como 1-0076): el kernel no tiene un driver enlazado al BMP280, y mi programa lo maneja directamente desde espacio de usuario por `/dev/i2c-1`.
- En `/dev/p6buf` el codigo que decide que significa un `read` o un `write` es nuestro modulo (`p6_read` y `p6_write`); en `/dev/i2c-1` y `/dev/spidev0.0` los drivers `i2c_dev` y `spidev` solo transportan bytes al controlador, y el significado de esos bytes (registros del BMP280, trama del MCP3008) lo decide el programa de usuario segun la hoja de datos del chip.
## Reto final (p6cnt)
aperturas: 1
aperturas: 2
aperturas: 3
aperturas: 1
-bash: echo: write error: Invalid argument
codigo de salida: 1
write(1, "hola\n", 5)                   = -1 EINVAL (Invalid argument)
[ 3312.815936] p6cnt: open (pid 2352, proceso cat)
[ 3312.816360] p6cnt: open (pid 2345, proceso bash)
[ 3312.823684] p6cnt: open (pid 2357, proceso sh)
[ 3312.850986] p6cnt: /dev/p6cnt eliminado. Total de aperturas: 1
[ 3426.619355] p6cnt: /dev/p6cnt creado, minor 267
[ 3426.631911] p6cnt: open (pid 2588, proceso cat)
[ 3426.636473] p6cnt: open (pid 2590, proceso cat)
[ 3426.640976] p6cnt: open (pid 2592, proceso cat)
[ 3426.641811] p6cnt: open (pid 2586, proceso bash)
[ 3426.641895] p6cnt: contador reiniciado a 0 (pid 2586)
[ 3426.645316] p6cnt: open (pid 2593, proceso cat)
[ 3426.646164] p6cnt: open (pid 2586, proceso bash)
[ 3426.661382] p6cnt: open (pid 2598, proceso sh)
[ 3426.694727] p6cnt: /dev/p6cnt eliminado. Total de aperturas: 3
ls: cannot access '/dev/p6cnt': No such file or directory

### Justificacion del codigo de error (reto)
- Elegi `-EINVAL` (errno 22, "Invalid argument") porque el problema no es el dispositivo ni los permisos: el dato que se escribio no tiene un contenido valido para esta operacion, y solo `reset` es valido.
- Descarte `-ENOSPC` (lo usa p6buf porque ahi el problema es el tamano) y `-EPERM`/`-EACCES` (el usuario si tiene permiso de escritura, el modo es 0666).
Nota: las primeras 4 lineas de dmesg del reto (hasta 'Total de aperturas: 1') son de una corrida anterior con la version vieja del modulo, que contaba en read. Se corrigio para contar en open y se repitio la prueba.
## Parte H (descargar.sh)
no estaba cargado: p6cnt
descargado: p6buf
no estaba cargado: parametros
no estaba cargado: hola
ningun modulo de la practica 6 sigue cargado
sin dispositivos p6 en /dev
[ 3426.640976] p6cnt: open (pid 2592, proceso cat)
[ 3426.641811] p6cnt: open (pid 2586, proceso bash)
[ 3426.641895] p6cnt: contador reiniciado a 0 (pid 2586)
[ 3426.645316] p6cnt: open (pid 2593, proceso cat)
[ 3426.646164] p6cnt: open (pid 2586, proceso bash)
[ 3426.661382] p6cnt: open (pid 2598, proceso sh)
[ 3426.694727] p6cnt: /dev/p6cnt eliminado. Total de aperturas: 3
[ 3495.067863] p6buf: /dev/p6buf eliminado
