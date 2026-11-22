# Registros, caja negra y recuperación de El Fotobut

Qué pasa cuando algo falla, qué queda escrito y cómo se revive la cabina, también a distancia.

## 1. Quién revive qué

| Falla | Quién la detecta | Qué hace | Tiempo |
|---|---|---|---|
| Un proceso muere (`kill -9`, excepción) | systemd (`Restart=always`) | Lo levanta de nuevo | ~2 s (medido en el Avance 3) |
| Un proceso se cuelga sin morir | systemd (`WatchdogSec=`) + `fotobut/servicios/vigia.py` | Deja de llegar la señal de vida: lo mata y lo levanta | 15–30 s |
| El sistema entero se congela | Watchdog de hardware del BCM2711 (`RuntimeWatchdogSec=15`) | Reinicia la placa | ~15 s + arranque |
| Se va la luz | — | Al volver arranca sola y sigue donde iba | arranque (~13 s) |
| `vision_gui` muere con la tira en pantalla | Punto de control (`estado.json`) | Vuelve a mostrar la tira con su QR | ~2 s |
| `vision_gui` muere a media sesión | Punto de control | Descarta la sesión, lo anota y vuelve al inicio | ~2 s |
| El STM32 deja de mandar tramas | `control_daemon` / `monitor` | La cabina sigue con el botón; queda anotado | — |
| La microSD se daña | Respaldo | Tarjeta nueva + `instalar.sh` + `restaurar.sh` | ~20 min |

La señal de vida no se manda a ciegas: `vision_gui` solo avisa si el hilo de la máquina de estados dio una vuelta en los
últimos 8 s; `control_daemon`, si el muestreo de sensores sigue corriendo; `qr_httpd`, si su propio servidor contesta.

## 2. Qué queda escrito y dónde

| Qué | Dónde | Sobrevive a |
|---|---|---|
| Registros de los 4 servicios, con nivel y hora | journald en disco (`/var/log/journal`, máx. 64 MB) | reinicio y apagón |
| **Caja negra**: salud cada 10 s y eventos | `/var/lib/fotobut/caja_negra/AAAA-MM-DD.jsonl` (14 días) | reinicio y apagón |
| Punto de control (contador, sesión en curso) | `~/fotobut_sesiones/estado.json` (escritura atómica) | reinicio y apagón |
| Tiras finales y registro de sesiones | `~/fotobut_sesiones/*.jpg`, `sesiones.log` (con `fsync`) | reinicio y apagón |
| Fotos intermedias | `/tmp/fotobut` (RAM) | solo al reinicio de un proceso |

Cada muestra de la caja negra guarda: temperatura del CPU y de la caja, RAM, espacio libre, voltaje
(`vcgencmd get_throttled`), estado, PID y número de reinicios de cada servicio, estado de la cabina, STM32 y cámara.
Los eventos (un servicio se reinició, el STM32 dejó de responder, bajo voltaje, la Pi estuvo apagada…) se escriben con
`fsync` y nivel `INFO`/`WARN`/`ERROR`. Al arrancar, el monitor compara la última línea con el tiempo de encendido: si
la Pi se reinició, anota a qué hora fue el último registro y en qué estado estaba la cabina.

## 3. Verla y revivirla a distancia

La única puerta de administración es SSH. Sirve desde cualquier red por la que se llegue a la Pi: el Wi-Fi `Fotobut`
(`192.168.4.1`), la red del laboratorio o, con internet, una VPN (sección 5).

**Desde la terminal**

```bash
ssh papu@192.168.4.1
./tools/mantenimiento/caja_negra.sh                     # últimos eventos y última muestra de salud
journalctl -u 'fotobut-*' -n 50 --no-pager
sudo systemctl restart fotobut-vision     # revivir un servicio
sudo reboot                               # revivir todo
```

**Con el panel web** (se ve en el navegador de tu PC o celular, pero viaja dentro de SSH)

```bash
ssh -L 9000:127.0.0.1:9000 papu@192.168.4.1
```

Con esa terminal abierta, entra a `http://127.0.0.1:9000`. El panel muestra el estado de la cabina y de cada servicio,
la gráfica de la última hora, los eventos, los registros de systemd, un botón para reiniciar cada servicio y la descarga
de un respaldo. En el celular, una app de SSH con reenvío de puertos (por ejemplo Termius) hace lo mismo.

## 4. Respaldo y restauración

```bash
./tools/mantenimiento/respaldo.sh                # ~/fotobut-respaldo-FECHA.tar.gz (sin fotos)
./tools/mantenimiento/respaldo.sh --fotos        # incluye las tiras
scp papu@IP:~/fotobut-respaldo-*.tar.gz .          # desde tu PC
```

Para revivir la cabina en una microSD nueva (o en otra Raspberry Pi):

```bash
git clone https://github.com/JDJR13/Practicas_DivasDown.git && cd Practicas_DivasDown/proyecto-photobooth
sudo ./scripts/instalar.sh
./tools/mantenimiento/restaurar.sh ~/fotobut-respaldo-FECHA.tar.gz     # recupera contador, registros y caja negra
sudo reboot
```

## 5. Desde fuera de la red local (opcional)

Con el punto de acceso encendido la Pi no tiene internet (usa su única tarjeta Wi-Fi). Para llegar a ella desde
cualquier lugar hace falta darle salida por cable Ethernet y una VPN; con Tailscale:

```bash
curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up     # una vez, con internet
ssh papu@<nombre-o-ip-de-tailscale>                                        # desde cualquier red
```

No abre puertos en ningún ruteador y la puerta sigue siendo SSH con llave. No está instalado por omisión.

## 6. Cómo demostrarlo

| Prueba | Comando | Qué debe verse |
|---|---|---|
| Proceso que muere | `./tools/pruebas/inducir_falla.sh vision` | Vuelve en ~2 s; evento en la caja negra |
| Proceso colgado | `sudo kill -STOP $(systemctl show -p MainPID --value fotobut-vision)` | A los ~30 s systemd lo mata y lo levanta (`journalctl -u fotobut-vision`) |
| Tira en pantalla y cae el proceso | En la pantalla de resultado: `./tools/pruebas/inducir_falla.sh vision` | La tira y su QR reaparecen |
| Apagón | Desconectar y reconectar | Arranca sola; `./tools/mantenimiento/caja_negra.sh` dice a qué hora se apagó |
| Sistema congelado | `echo c \| sudo tee /proc/sysrq-trigger` (provoca un *kernel panic*) | La placa se reinicia sola |
