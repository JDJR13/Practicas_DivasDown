# Decisiones de diseño de la interfaz de El Fotobut

Este documento guarda el porqué de la pantalla: cómo se muestra, con qué colores y por qué se eligió un navegador.
Sirve para la bitácora (Clase 22, software de aplicación) y para las preguntas de la presentación.

## 1. ¿Página web en un navegador o aplicación nativa?

La pantalla de la cabina es una página web (HTML, CSS y JavaScript) que sirve el proceso `vision_gui` en
`127.0.0.1:8000` y que Chromium abre a pantalla completa (modo kiosco) al encender. La alternativa era una aplicación
nativa que dibujara directo en la pantalla (Qt, pygame o el framebuffer), sin navegador.

| Criterio | Página web + Chromium (elegido) | Aplicación nativa |
|---|---|---|
| Cambiar el diseño y las animaciones | Rápido: se edita un archivo CSS | Lento: cada pantalla se programa |
| Probar sin la Raspberry Pi | Sí: `python3 run.py --sim` en cualquier PC | Difícil: depende de la pantalla real |
| Aislamiento de fallas | Si el navegador muere, la cabina sigue tomando fotos y `kiosk.sh` lo reabre | Pantalla y lógica suelen ir en el mismo proceso y caen juntas |
| Separación en capas (Clase 22) | Clara: la lógica (máquina de estados) no sabe cómo se dibuja | Hay que imponerla a mano |
| Memoria | Alta: Chromium usa varios cientos de MB | Baja: decenas de MB |
| Arranque | Necesita la sesión gráfica y el navegador (~13 s medidos) | Más rápido: no necesita escritorio |
| Superficie de ataque | Mayor: un navegador completo | Menor |

**Decisión:** página web con Chromium en modo kiosco.

**Por qué:** la Raspberry Pi 4 tiene memoria de sobra para Chromium, el arranque medido (12.9 s) cumple el requisito de
25 s, y el diseño pudo cambiarse varias veces sin tocar la lógica ni el hardware. El costo en memoria y en superficie de
ataque se acepta y se reduce así: la página solo se sirve en `127.0.0.1` (no existe para la red), Chromium arranca sin
extensiones ni sincronización, y el cortafuegos descarta el puerto 8000 (`docs/SEGURIDAD.md`).

**Cuándo convendría lo contrario:** en una placa con poca memoria (por ejemplo una Pi Zero), si el arranque tuviera que
bajar de unos 5 s, o en un producto donde no se pueda aceptar un navegador por seguridad.

**Lo que no se hace:** abrir la interfaz desde el navegador de otra computadora. Sería posible (basta escuchar en
`0.0.0.0`), pero expondría a la red el control de la cabina; por eso está cerrado a propósito. El mantenimiento a
distancia va por SSH (`docs/RECUPERACION.md`).

## 2. Cómo llega el estado a la pantalla

La página no decide nada: el estado vive en Python (`fotobut/logica/machine.py`) y llega por *Server-Sent Events* (`/events`).
El JavaScript solo dibuja. La vista previa de la cámara llega como MJPEG (`/preview.mjpg`). Si se pierde la conexión, la
página reintenta cada segundo y muestra «Reconectando…».

## 3. Recorrido (se conserva desde el Avance 3)

Inicio → elegir filtro → cuenta regresiva y 3 fotos → revelado → tira con los códigos QR. Pantalla de reposo a los 5 s
sin nadie frente al sensor. Dos apoyos fijos para no perderse:

- **Arriba, la ruta de 3 pasos** (elige tu filtro · posa · llévate tu tira): siempre se sabe en qué parte se está.
- **Abajo, la barra de mandos**: qué hace la perilla, el botón rojo y el botón azul en la pantalla actual. La cabina no
  tiene pantalla táctil, así que la interfaz debe decir qué control físico usar.

Una sola acción principal por pantalla, texto grande y la cuenta regresiva en una esquina del visor para no tapar caras.

## 4. Paleta «noche dorada»

La cabina es dorada con toques cobrizos. La pantalla debía contrastar con el mueble y, a la vez, combinar con él.

| Uso | Color | Motivo |
|---|---|---|
| Fondo | Azul noche `#0C1320` | El azul es el opuesto del dorado: un fondo frío y oscuro hace que el mueble resalte |
| Texto | Marfil `#F7EEDC` | Contraste mayor a 15:1 sobre el fondo (nivel AAA pide 7:1) |
| Acentos | Oro `#E2B659`, oro claro `#F6DE9C` | Repiten el color de la cabina en el título, los focos y los marcos |
| Acción y relieve | Cobre `#C8744A` | Repite los toques cobrizos en el borde de las tarjetas y botones de pantalla |
| Botones físicos | Rojo `#E5382B`, azul `#2F6FE0` | Se reservan para lo que representan: nada más en la pantalla es rojo o azul |

La tira impresa (`fotobut/logica/strip.py`) y la página de descarga del celular (`fotobut/comunicacion/share.py`) usan la misma paleta.

## 5. Referencias

Se revisó la categoría *Interface, Interaction and User Experience Design* de A' Design Award
(https://competition.adesignaward.com/accolade.php?CID=10). No se copió el aspecto de ningún ganador; se tomaron dos
principios de sus fichas:

- **Cathay Pacific IFE In-Flight Entertainment Experience** (Golden A' Design Award 2024–2025,
  https://competition.adesignaward.com/gooddesign.php?ID=169385): contraste de nivel triple A y modelos de interacción
  que la gente ya conoce. De ahí el texto marfil sobre azul noche y el recorrido lineal.
- **Pepsi Touch Tower 2.0 Interactive Beverage Dispenser** (Golden A' Design Award 2013–2014,
  https://competition.adesignaward.com/gooddesign.php?ID=32018): un equipo de autoservicio que debe entenderse y usarse
  rápido, con una interfaz lúdica y limpia. De ahí una acción por pantalla y el tono festivo (focos, confeti).

## 6. Versiones

| Versión | Qué era | Estado |
|---|---|---|
| Avance 3 | Recorrido actual, paleta verde con naranja | Base de la versión final |
| v1 (16 nov) | Se agregaron la ruta de pasos y la barra de mandos | Conservada dentro de la versión final |
| v2 (16 nov) | Rediseño con dial horizontal de filtros y portada asimétrica | Descartada: el equipo prefirió el recorrido anterior |
| Final | Recorrido del Avance 3 + ruta y mandos, con la paleta «noche dorada» | En uso |

## 7. Cómo se abre la pantalla en la Raspberry Pi (ajuste del 20 nov)

En Raspberry Pi OS trixie con el escritorio labwc, Chromium no se mostraba bien de dos formas: en Wayland nativo la ventana
no aparecía, y a pantalla completa (`--kiosk`) quedaba en negro o en blanco, con GPU y sin ella. En una ventana normal la
interfaz se veía bien. Por eso `kiosk.sh` abre Chromium por X11 (Xwayland) como **ventana de aplicación** (`--app`, sin barra
de direcciones ni pestañas) del tamaño exacto del monitor, que en la práctica se ve igual que pantalla completa. Si Chromium
se cierra, `kiosk.sh` lo vuelve a abrir. Para probar otra combinación: `FOTOBUT_PANTALLA=wayland ./kiosk.sh`.

Las politicas de Chromium (`seguridad/chromium-politicas.json`) bloquean `view-source:`, `devtools://` y `file://`. No se
bloquea `chrome://`: Chromium usa paginas internas para dibujar y con ese bloqueo la pantalla quedaba en blanco. Se quito la
opcion `--use-fake-ui-for-media-stream` (mostraba un aviso y no hacia falta: la camara la usa Python, no el navegador) y se
apago la barra de traduccion.
El titulo «El Fotobut» y el de la pantalla de reposo eran texto con degradado metalico (`background-clip:text`) con sombras
por `filter: drop-shadow`, y el visor usaba desenfoque de fondo (`backdrop-filter`). En la Raspberry Pi la pagina cargaba
por partes y luego quedaba en blanco; se cambiaron por dorado solido con `text-shadow` y fondos semitransparentes, que se
ven casi igual y Chromium dibuja sin problema.
