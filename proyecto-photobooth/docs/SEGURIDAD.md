# Seguridad de El Fotobut

La cabina es un equipo público: cualquiera puede acercarse, conectarse a su Wi-Fi (la clave está en un código QR) y
probar cosas. Este documento dice qué se protege, de quién, cómo, cómo comprobarlo y qué riesgos quedan.

## 1. Qué hay que proteger y de quién

| Activo | Riesgo | Quién |
|---|---|---|
| Las fotos de cada persona | Que otra persona las vea o descargue | Alguien conectado al Wi-Fi `Fotobut` |
| Que la cabina siga funcionando | Tirarla o dejarla colgada | Alguien en la red, o con un teclado USB |
| El control de la Raspberry Pi | Entrar por SSH, ejecutar código, volverse root | Alguien en la red |
| El hardware (botones, cámara, buzzer) | Dispararlo sin estar frente a la cabina | Alguien en la red |

## 2. Superficie de ataque: qué escucha y dónde

| Puerto | Proceso | Escucha en | Para qué | Protección |
|---|---|---|---|---|
| 8080 | `qr_httpd` | toda la red | Descargar la tira con el QR | Único servicio público: ver sección 3 |
| 22 | `sshd` | toda la red | Administración | Solo con llave, 3 intentos, 6 conexiones/min por IP |
| 8000 | `vision_gui` | **solo 127.0.0.1** | Pantalla de la cabina | No existe para la red |
| 9000 | `monitor` | **solo 127.0.0.1** | Panel de mantenimiento | Se entra por túnel SSH |
| 53, 67 | NetworkManager | red `Fotobut` | DNS y DHCP de los celulares | Solo desde 192.168.4.0/24 |

Todo lo demás lo descarta el cortafuegos (`seguridad/firewall.nft`, política *drop*). El hardware no tiene ningún camino
desde la red: los botones, el buzzer y la cámara solo se alcanzan por el socket Unix `/run/photobooth/photobooth.sock`
(permisos 0660) y por la API local del puerto 8000.

## 3. Medidas implementadas

**Servidor de descargas (`fotobut/comunicacion/share.py`)**
- Rutas por lista blanca con expresiones regulares completas: no hay forma de pedir un archivo arbitrario
  (`../`, `%2f`, rutas absolutas y enlaces simbólicos dan 404).
- El identificador de la tira lleva **64 bits al azar** (`secrets.token_hex(8)`): no se puede adivinar la de otra persona.
  Antes eran 32 bits y la raíz `/` mostraba la última tira a cualquiera; ya no.
- Los enlaces **caducan a las 6 horas** (`SHARE_TTL_S`).
- 15 errores 404 en un minuto bloquean esa IP 2 minutos (frena la búsqueda de identificadores y los escáneres).
- Máximo 60 peticiones cada 10 s por IP, 8 conexiones simultáneas por IP y 48 en total; 8 s de espera por conexión
  (un ataque *slowloris* no agota los hilos).
- Solo `GET` y `HEAD`; cabeceras `Content-Security-Policy`, `nosniff`, `X-Frame-Options`; no revela versiones.

**Sistema (`scripts/blindar.sh`)**
- Cortafuegos nftables: entra solo SSH y el 8080, con límites por IP; la cabina no reenvía tráfico entre redes.
- SSH: sin root, solo el usuario de la cabina, 3 intentos; con `--ssh-solo-llave` se apagan las contraseñas.
- Los servicios no corren como root. `qr_httpd`, el único que habla con la red, no ve dispositivos (`PrivateDevices`),
  no tiene capacidades, ve el sistema de archivos en solo lectura y tiene tope de memoria (200 MB) y de hilos.
- Aislamiento de clientes en el punto de acceso (un celular no alcanza a otro), si el controlador lo admite.
- Ajustes del núcleo: sin redirecciones ICMP, filtro de direcciones falsas, *SYN cookies*.
- La pantalla (Chromium) se vuelve a abrir sola si alguien la cierra; con `--teclado` se quitan los atajos del escritorio.

**Panel de mantenimiento (`fotobut/procesos/monitor.py`)**
- No está en la red: escucha en 127.0.0.1 y se entra con `ssh -L`. La autenticación es la llave SSH.
- Exige `Host` local exacto (contra *DNS rebinding*) y una cabecera propia en los `POST` (contra peticiones cruzadas).
- Reinicia servicios mandando `SIGTERM` a procesos del mismo usuario: no necesita `sudo` ni privilegios.

## 4. Puesta en marcha (una vez, en la Pi)

```bash
sudo ./scripts/blindar.sh                 # cortafuegos, SSH, watchdog, registros, aislamiento
./tools/pruebas/auditar_seguridad.sh              # comprueba todo y dice qué falla
```

**Llave SSH** (hazlo antes de apagar las contraseñas). En tu PC con Windows (PowerShell):

```powershell
ssh-keygen -t ed25519                                    # Enter a todo (o ponle una frase)
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh papu@IP_DE_LA_PI "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
ssh papu@IP_DE_LA_PI                                     # ya no debe pedir la contraseña de la Pi
```

Cada integrante que vaya a administrar la cabina repite esos pasos desde su equipo. Con la llave probada:

```bash
sudo ./scripts/blindar.sh --ssh-solo-llave
```

El script se niega a apagar las contraseñas si no encuentra ninguna llave instalada, para no dejarte fuera.
Cambia también la contraseña del usuario (`passwd`): `sudo` la sigue pidiendo.

**Si algo deja de funcionar después de blindar:**

| Síntoma | Qué hacer |
|---|---|
| Un servicio no arranca o la cámara no abre | `sudo ./scripts/blindar.sh --quitar-aislamiento` |
| No entras por SSH ni descargas | Con teclado y monitor: `sudo ./scripts/blindar.sh --quitar-firewall` |
| La red `Fotobut` no enciende | `sudo nmcli connection modify FotobutAP 802-11-wireless.ap-isolation no` |

## 5. Cómo comprobarlo desde fuera (lo que intentaría un atacante)

Desde una laptop conectada a `Fotobut`:

```bash
nmap -p- 192.168.4.1                          # deben verse solo 22, 53 y 8080
curl -i http://192.168.4.1:8000/api/state     # sin respuesta: la pantalla no existe para la red
curl -i http://192.168.4.1:8080/              # página neutra, ninguna tira
curl -i --path-as-is http://192.168.4.1:8080/strip/../../etc/passwd      # 404
for i in $(seq 30); do curl -s -o /dev/null -w "%{http_code} " http://192.168.4.1:8080/s/0001-$(printf %016x $i); done   # 404... y luego 429
ssh root@192.168.4.1                          # rechazado
```

## 6. Riesgos que quedan (declarados)

- **El Wi-Fi usa una clave compartida y la descarga va por HTTP.** Quien conozca la clave y capture el tráfico de otro
  celular en el momento de la descarga puede ver esa foto. Usar HTTPS con un certificado propio haría que cada celular
  mostrara una advertencia de seguridad, y se prefirió que la descarga funcione sin pasos extra.
- **Acceso físico.** Quien abra la caja puede sacar la microSD (no está cifrada) o desconectar la alimentación.
- **Interferencia de radio.** Nadie puede impedir que se sature o se desautentique el Wi-Fi desde otro equipo.
- **Negación de servicio desde muchas direcciones a la vez.** Los límites son por IP; la cabina seguiría tomando fotos
  (son procesos distintos), pero las descargas se volverían lentas.
- El aislamiento de systemd, el cortafuegos y el aislamiento de clientes se escribieron sin la Raspberry Pi a la mano:
  hay que validarlos en la placa con `tools/pruebas/auditar_seguridad.sh`.
