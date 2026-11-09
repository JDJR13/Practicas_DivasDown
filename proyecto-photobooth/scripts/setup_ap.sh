#!/bin/bash
# Crea (una sola vez) el perfil de punto de acceso Wi-Fi "FotobutAP" con NetworkManager.
# La Pi se vuelve una red Wi-Fi propia:  SSID Fotobut / clave fotobut2026 / IP 192.168.4.1
# Uso:  sudo ./scripts/setup_ap.sh        (no enciende la red; para eso: ./scripts/ap_on.sh)
set -e
SSID="${FOTOBUT_SSID:-Fotobut}"; PASS="${FOTOBUT_PASS:-fotobut2026}"; IP="192.168.4.1/24"; CON="FotobutAP"
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo:  sudo $0"; exit 1; }
command -v nmcli >/dev/null || { echo "No hay NetworkManager (nmcli). En Raspberry Pi OS Bookworm/Trixie viene por defecto."; exit 1; }
[ ${#PASS} -ge 8 ] || { echo "La clave WPA2 necesita 8 caracteres o mas"; exit 1; }
rfkill unblock wifi 2>/dev/null || true
iw reg set MX 2>/dev/null || true                       # pais (sin esto el AP en 2.4 GHz puede no arrancar)
nmcli connection delete "$CON" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname wlan0 con-name "$CON" autoconnect no ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASS" \
  ipv4.method shared ipv4.addresses "$IP" ipv6.method disabled
echo "Listo. Perfil '$CON' creado (SSID=$SSID). Enciende la red con:  ./scripts/ap_on.sh"
