#!/bin/bash
# Endurece la Raspberry Pi de El Fotobut. Cada paso es independiente y se puede repetir. Ver docs/SEGURIDAD.md.
#   sudo ./scripts/blindar.sh                      aplica todo lo seguro de aplicar
#   sudo ./scripts/blindar.sh --ssh-solo-llave     ademas apaga las contrasenas en SSH (solo si ya hay una llave instalada)
#   sudo ./scripts/blindar.sh --teclado            ademas quita los atajos de teclado del escritorio (kiosco)
#   sudo ./scripts/blindar.sh --quitar-aislamiento retira el aislamiento extra de los servicios (si algo dejo de funcionar)
#   sudo ./scripts/blindar.sh --quitar-firewall    apaga el cortafuegos
#   sudo ./scripts/blindar.sh --quitar-politicas   quita las restricciones de Chromium (para usar el navegador normal en la Pi)
set -u
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo:  sudo $0 $*"; exit 1; }
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USR="${SUDO_USER:-papu}"; HOME_U="$(getent passwd "$USR" | cut -d: -f6)"
SSH_LLAVE=0; TECLADO=0
ok()   { echo "  [ok] $*"; }
ojo()  { echo "  [!!] $*"; }
paso() { echo; echo "== $* =="; }

for a in "$@"; do
  case "$a" in
    --ssh-solo-llave) SSH_LLAVE=1;;
    --teclado) TECLADO=1;;
    --quitar-aislamiento)
      for s in control vision qr; do rm -f "/etc/systemd/system/fotobut-$s.service.d/seguridad.conf"; done
      systemctl daemon-reload; systemctl restart fotobut-control fotobut-vision fotobut-qr
      echo "Aislamiento extra retirado; servicios reiniciados."; exit 0;;
    --quitar-politicas)
      rm -f /etc/chromium/policies/managed/fotobut.json; echo "Politicas de Chromium retiradas (aplica al reabrir Chromium)."; exit 0;;
    --quitar-firewall)
      systemctl disable --now fotobut-firewall 2>/dev/null; nft delete table inet fotobut 2>/dev/null
      echo "Cortafuegos apagado."; exit 0;;
    *) echo "Opcion desconocida: $a"; exit 1;;
  esac
done

paso "1. Cortafuegos (nftables): solo SSH y el puerto 8080 entran"
if ! command -v nft >/dev/null; then apt-get install -y nftables || ojo "no pude instalar nftables (¿sin internet?)"; fi
if command -v nft >/dev/null; then
  mkdir -p /etc/fotobut
  if nft -c -f "$DIR/seguridad/firewall.nft" 2>/dev/null; then
    cp "$DIR/seguridad/firewall.nft" /etc/fotobut/firewall.nft
  else                                             # nucleo sin el modulo de conteo de conexiones: version basica
    grep -v "# opcional" "$DIR/seguridad/firewall.nft" > /etc/fotobut/firewall.nft
    ojo "este nucleo no tiene 'ct count': se instala sin el tope de conexiones simultaneas (lo demas igual)"
  fi
  if nft -c -f /etc/fotobut/firewall.nft; then
    cat > /etc/systemd/system/fotobut-firewall.service <<EOT
[Unit]
Description=El Fotobut - cortafuegos (nftables)
Before=network-pre.target
Wants=network-pre.target
DefaultDependencies=no
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/fotobut/firewall.nft
ExecReload=/usr/sbin/nft -f /etc/fotobut/firewall.nft
ExecStop=/usr/sbin/nft delete table inet fotobut

[Install]
WantedBy=sysinit.target
EOT
    systemctl daemon-reload; systemctl enable fotobut-firewall >/dev/null 2>&1
    systemctl restart fotobut-firewall && ok "cortafuegos activo (tabla 'inet fotobut'); se carga en cada arranque" || ojo "no se pudo cargar; revisa: journalctl -u fotobut-firewall"
  else
    ojo "el archivo de reglas no es valido en este sistema; NO se instalo el cortafuegos"
  fi
fi

paso "1b. Servicios de red que la cabina no usa"
for s in rpcbind.socket rpcbind nfs-client.target; do systemctl disable --now "$s" >/dev/null 2>&1; done
ss -tlnH 2>/dev/null | grep -q ":111 " && ojo "el puerto 111 (rpcbind) sigue abierto" || ok "rpcbind apagado (puerto 111 cerrado)"

paso "2. Red: ajustes del nucleo"
cat > /etc/sysctl.d/90-fotobut.conf <<EOT
# El Fotobut: no aceptar redirecciones ni rutas de origen, filtrar direcciones falsas, proteger contra inundacion SYN
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.default.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
net.ipv4.conf.all.accept_source_route=0
net.ipv4.conf.all.rp_filter=1
net.ipv4.conf.default.rp_filter=1
net.ipv4.tcp_syncookies=1
net.ipv6.conf.all.accept_redirects=0
kernel.kptr_restrict=2
kernel.dmesg_restrict=1
EOT
sysctl -q --system && ok "sysctl aplicado"

paso "3. SSH"
mkdir -p /etc/ssh/sshd_config.d
CONF=/etc/ssh/sshd_config.d/01-fotobut.conf
{
  echo "# El Fotobut (scripts/blindar.sh). El primer valor que lee sshd es el que cuenta, por eso el archivo empieza con 01."
  echo "PermitRootLogin no"
  echo "AllowUsers $USR"
  echo "MaxAuthTries 3"
  echo "LoginGraceTime 20"
  echo "MaxStartups 4:50:10"
  echo "X11Forwarding no"
  echo "AllowAgentForwarding no"
  echo "PermitTunnel no"
  echo "AllowTcpForwarding local"
  echo "PermitEmptyPasswords no"
  echo "ClientAliveInterval 60"
  echo "ClientAliveCountMax 3"
} > "$CONF"
LLAVES="$HOME_U/.ssh/authorized_keys"
if [ $SSH_LLAVE = 1 ]; then
  if [ -s "$LLAVES" ] && grep -Eq '^(ssh-|ecdsa-|sk-)' "$LLAVES"; then
    { echo "PasswordAuthentication no"; echo "KbdInteractiveAuthentication no"; echo "PubkeyAuthentication yes"; } >> "$CONF"
    ok "contrasenas apagadas en SSH: solo entra quien tenga una llave de $LLAVES ($(grep -Ec '^(ssh-|ecdsa-|sk-)' "$LLAVES") instalada(s))"
  else
    ojo "NO apago las contrasenas: $LLAVES no tiene ninguna llave y te quedarias fuera. Instala tu llave primero (docs/SEGURIDAD.md, paso 2)."
  fi
else
  ojo "SSH sigue aceptando contrasena. Cuando tengas tu llave instalada y probada:  sudo $0 --ssh-solo-llave"
fi
if sshd -t 2>/dev/null; then systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null; ok "sshd recargado (root no entra, 3 intentos, solo el usuario $USR)"
else ojo "la configuracion de sshd no es valida: se retira"; rm -f "$CONF"; fi
if grep -Rqs "NOPASSWD" /etc/sudoers.d/ 2>/dev/null && sudo -l -U "$USR" 2>/dev/null | grep -q "NOPASSWD: ALL"; then
  ojo "sudo NO pide contrasena a $USR. Quien llegue a una terminal seria root. Quitalo:  sudo rm /etc/sudoers.d/010_pi-nopasswd"
else ok "sudo pide contrasena"; fi

paso "4. Registros que sobreviven al reinicio (journald en la microSD, maximo 64 MB)"
mkdir -p /etc/systemd/journald.conf.d /var/log/journal
printf '[Journal]\nStorage=persistent\nSystemMaxUse=64M\nMaxRetentionSec=30day\n' > /etc/systemd/journald.conf.d/fotobut.conf
systemctl restart systemd-journald && journalctl --flush 2>/dev/null; ls /var/log/journal/*/system.journal >/dev/null 2>&1 && ok "journald persistente (/var/log/journal)" || ojo "journald aun no escribe en /var/log/journal: se activa al reiniciar"

paso "5. Watchdog de hardware: si el sistema entero se congela, la placa se reinicia sola"
mkdir -p /etc/systemd/system.conf.d
printf '[Manager]\nRuntimeWatchdogSec=15\nRebootWatchdogSec=2min\n' > /etc/systemd/system.conf.d/fotobut-watchdog.conf
systemctl daemon-reexec && ok "systemd alimenta /dev/watchdog cada 7 s (plazo 15 s)"
[ -e /dev/watchdog ] || ojo "no existe /dev/watchdog: agrega  dtparam=watchdog=on  a /boot/firmware/config.txt y reinicia"

paso "6. Aislamiento de los servicios (drop-ins de systemd)"
mkdir -p "$HOME_U/fotobut_sesiones"; chown "$USR:$USR" "$HOME_U/fotobut_sesiones"; chmod 750 "$HOME_U/fotobut_sesiones"
for s in control vision qr; do
  d="/etc/systemd/system/fotobut-$s.service.d"; mkdir -p "$d"
  sed "s|__HOME__|$HOME_U|g" "$DIR/seguridad/$s.conf" > "$d/seguridad.conf"
done
systemctl daemon-reload
systemctl restart fotobut-control fotobut-vision fotobut-qr 2>/dev/null
sleep 6
MAL=0
for s in control vision qr; do
  if systemctl is-active -q "fotobut-$s"; then ok "fotobut-$s activo con aislamiento"; else ojo "fotobut-$s NO arranco con el aislamiento"; MAL=1; fi
done
if curl -s --max-time 3 http://127.0.0.1:8000/api/state | grep -q '"cam_sim": true'; then
  ojo "la camara no abrio con el aislamiento de vision_gui: lo retiro solo de ese servicio"
  rm -f /etc/systemd/system/fotobut-vision.service.d/seguridad.conf; systemctl daemon-reload; systemctl restart fotobut-vision
fi
[ $MAL = 1 ] && ojo "si un servicio no levanta:  sudo $0 --quitar-aislamiento   y mandame  journalctl -u fotobut-<servicio> -n 30"

paso "7. Pantalla: Chromium sin codigo fuente, herramientas de desarrollador, descargas ni impresion"
mkdir -p /etc/chromium/policies/managed
cp "$DIR/seguridad/chromium-politicas.json" /etc/chromium/policies/managed/fotobut.json && chmod 644 /etc/chromium/policies/managed/fotobut.json \
  && ok "politicas instaladas (/etc/chromium/policies/managed/fotobut.json); aplican al reabrir Chromium. OJO: valen para todo Chromium de esta Pi" \
  || ojo "no se pudieron instalar las politicas de Chromium"

paso "8. Permisos de archivos"
chmod 750 "$HOME_U" 2>/dev/null && ok "la carpeta personal no es legible para otros usuarios"
chmod -R o-rwx "$DIR" 2>/dev/null && ok "el codigo del proyecto no es legible para otros usuarios"

if [ $TECLADO = 1 ]; then
  paso "9. Kiosco: sin atajos de teclado en el escritorio"
  RC="$HOME_U/.config/labwc/rc.xml"; mkdir -p "$(dirname "$RC")"
  [ -f "$RC" ] && [ ! -f "$RC.antes-fotobut" ] && cp "$RC" "$RC.antes-fotobut"
  cat > "$RC" <<EOT
<?xml version="1.0"?>
<!-- El Fotobut: al definir la seccion de teclado sin <default/>, labwc no carga ningun atajo (ni terminal, ni menu, ni cerrar ventana) -->
<labwc_config>
  <keyboard>
    <keybind key="C-A-F12"><action name="None"/></keybind>
  </keyboard>
</labwc_config>
EOT
  chown "$USR:$USR" "$RC"; ok "atajos retirados (respaldo en $RC.antes-fotobut). Aplica al reiniciar. Deshacer: restaura ese respaldo."
fi

paso "Resumen: puertos que escuchan"
ss -tulnH 2>/dev/null | awk '{print "   " $1, $5}' | sort -u
echo
echo "Comprueba todo con:  ./tools/pruebas/auditar_seguridad.sh"
