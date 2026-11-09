#!/bin/bash
# Emula una pulsacion de un boton de la cabina cuando no esta cableado: pone el pin a 0 V durante 150 ms y lo regresa a
# entrada con pull-up. El software recorre el mismo camino que con el boton fisico (lgpio, antirrebote, socket, maquina).
#   ./tools/pulsar.sh rojo     boton de foto  (GPIO17, pin 11)
#   ./tools/pulsar.sh azul     boton de reset (GPIO27, pin 13)
case "${1:-rojo}" in
  rojo|foto) P=17;;
  azul|reset) P=27;;
  *) echo "Uso: $0 rojo|azul"; exit 1;;
esac
sudo pinctrl set $P op dl; sleep 0.15; sudo pinctrl set $P ip pu
