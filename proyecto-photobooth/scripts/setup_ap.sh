#!/bin/bash
# Crea (una sola vez) el perfil de punto de acceso Wi-Fi "FotobutAP" con NetworkManager.
# La Pi se vuelve una red Wi-Fi propia (por omision SSID Fotobut / clave fotobut2026 / IP 192.168.4.1).
# El nombre y la clave salen de fotobut.conf, los mismos que muestra el QR de la pantalla: se cambian en un solo lugar.
# Uso:  sudo ./scripts/setup_ap.sh        (no enciende la red; para eso: ./scripts/ap_on.sh)
# Correlo MIENTRAS la Pi todavia tiene internet: si falta dnsmasq-base lo instala (NetworkManager lo usa para dar IP a los celulares).
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
LEE() { (cd "$DIR" && python3 -c "from fotobut.servicios import config as C; print(C.$1)" 2>/dev/null); }
SSID="${FOTOBUT_SSID:-$(LEE WIFI_SSID)}"; PASS="${FOTOBUT_PASS:-$(LEE WIFI_PASS)}"; SSID="${SSID:-Fotobut}"; PASS="${PASS:-fotobut2026}"
IP="$(LEE AP_IP)"; IP="${IP:-192.168.4.1}/24"; CON="FotobutAP"
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo:  sudo $0"; exit 1; }
command -v nmcli >/dev/null || { echo "No hay NetworkManager (nmcli). En Raspberry Pi OS Bookworm/Trixie viene por defecto."; exit 1; }
[ ${#PASS} -ge 8 ] || { echo "La clave WPA2 necesita 8 caracteres o mas"; exit 1; }
if ! dpkg -s dnsmasq-base >/dev/null 2>&1; then
  echo "Falta dnsmasq-base (DHCP del punto de acceso): lo instalo..."
  apt-get install -y dnsmasq-base || { echo "No pude instalar dnsmasq-base. Conecta la Pi a internet y repite."; exit 1; }
fi
rfkill unblock wifi 2>/dev/null || true
iw reg set MX 2>/dev/null || true                       # pais (sin esto el AP en 2.4 GHz puede no arrancar)
nmcli connection delete "$CON" >/dev/null 2>&1 || true
# WPA2-AES (rsn/ccmp) sin PMF: es lo que aceptan sin quejarse iPhone y Android al escanear el QR de Wi-Fi
nmcli connection add type wifi ifname wlan0 con-name "$CON" autoconnect no ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS" wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp wifi-sec.pmf 1 \
  ipv4.method shared ipv4.addresses "$IP" ipv6.method disabled
# Aislamiento de clientes: la clave del Wi-Fi es publica (esta en el QR), asi que un celular no debe poder atacar a otro.
# Si el controlador no lo admite, NetworkManager rechaza la opcion y el punto de acceso queda igual que antes.
nmcli connection modify "$CON" 802-11-wireless.ap-isolation yes 2>/dev/null \
  && echo "Aislamiento entre clientes: activado" || echo "(este NetworkManager no admite ap-isolation; el cortafuegos de la cabina sigue protegiendola)"
echo "Listo. Perfil '$CON' creado (SSID=$SSID, clave=$PASS, IP de la cabina 192.168.4.1)."
echo "Enciende la red con:  ./scripts/ap_on.sh        (o  ./scripts/ap_on.sh --arranque  para que tambien se encienda sola al prender la Pi)"
