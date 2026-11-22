"""Configuracion central de El Fotobut (SmartBooth FSE, equipo DivasDown).

Aqui viven los valores por omision, cada uno con nombre y en un solo lugar (Clase 22). Los que ajusta quien instala la
cabina (red Wi-Fi, distancias, tiempos, tonos, pines) se pueden cambiar sin tocar codigo en el archivo de configuracion
fotobut.conf (ver cargar_conf al final). Si el archivo no existe se usan estos valores y queda anotado.
"""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]            # fotobut/servicios/config.py -> carpeta del proyecto
WEB_DIR = BASE / "web"
TMP_DIR = Path(os.environ.get("FOTOBUT_TMP", "/tmp/fotobut"))            # tmpfs (RAM): fotos intermedias
FINAL_DIR = Path(os.environ.get("FOTOBUT_FINAL", str(Path.home() / "fotobut_sesiones")))  # microSD: tira final

# IPC entre los 3 procesos (clase 11). En la Pi, systemd crea /run/photobooth (RuntimeDirectory); en desarrollo se usa /tmp.
_RUN = Path("/run/photobooth")
SOCK_PATH = os.environ.get("FOTOBUT_SOCK") or str((_RUN if os.access(_RUN, os.W_OK) else TMP_DIR) / "photobooth.sock")
SHM_PATH = os.environ.get("FOTOBUT_SHM", "/dev/shm/pb_status")           # memoria compartida POSIX (128 bytes)
SEM_NAME = os.environ.get("FOTOBUT_SEM", "/pb_status")                   # semaforo POSIX con nombre que la protege
CAP_W, CAP_H = 1920, 1080                                                # foto fija Full HD (pool de 3 bloques)

UI_HOST, UI_PORT = "127.0.0.1", 8000      # pantalla del photobooth (solo local)
SHARE_HOST, SHARE_PORT = "0.0.0.0", 8080  # descarga desde el celular (solo /s/, /strip/, /photo/)
AP_IP = "192.168.4.1"                     # IP de la cabina cuando es punto de acceso Wi-Fi
WIFI_SSID, WIFI_PASS = "Fotobut", "fotobut2026"   # scripts/setup_ap.sh lee estos mismos valores
SHARE_TTL_S = 6 * 3600                    # una tira deja de poder descargarse 6 h despues de tomada (privacidad)
ADMIN_HOST, ADMIN_PORT = "127.0.0.1", 9000   # panel de mantenimiento: SOLO local; se entra por tunel SSH (ver docs/RECUPERACION.md)
ESTADO_DIR = Path(os.environ.get("FOTOBUT_ESTADO", str(Path.home() / "fotobut_estado")))   # caja negra (bitacora de salud)
CAJA_NEGRA_PERIODO_S = 10                 # una muestra de salud cada 10 s
CAJA_NEGRA_DIAS = 14                      # dias de historia que se conservan
MAX_TMP_SESSIONS = 20                     # sesiones que se conservan en RAM (/tmp); la tira final queda en la microSD

# Buzzer piezoelectrico: suena mas fuerte cerca de su frecuencia de resonancia (tipico 2-4 kHz).
# Busca la mejor con:  python3 tools/medicion/buzzer_sweep.py
TICK_HZ, TICK_MS = 2700, 160              # tono de la cuenta regresiva
SHUTTER_HZ, SHUTTER_MS = 3400, 220        # obturador
RESET_HZ, RESET_MS = 1800, 120            # confirmacion del boton azul (reset)

# Hardware (pines segun el diagrama de bloques)
GPIO_BUTTON = 17               # boton rojo (pin fisico 11): empezar / siguiente sesion
GPIO_RESET = 27                # boton azul (pin fisico 13): cancelar y volver al inicio
BUTTON_ACTIVE_LOW = True       # pull-up interna: presionado = 0 V (si tu boton va a 3.3V, pon False). Aplica a los dos botones
GPIO_BUZZER = 18
I2C_BUS, OLED_ADDR, BMP_ADDR = 1, 0x3C, 0x77
SPI_BUS, SPI_DEV = 0, 0
ADC_POT_CH, ADC_LDR_CH = 0, 1
UART_PORT, UART_BAUD = "/dev/ttyAMA0", 115200

# Presencia (HC-SR04 via STM32): 5 lecturas a 10 Hz = 500 ms dentro de 30-120 cm
PRESENCE_MIN_CM, PRESENCE_MAX_CM, PRESENCE_SAMPLES = 30, 120, 5

# Tiempos (segundos)
COUNT_FROM = 3
SHOTS = 3
REVIEW_S = 1.7
PROCESSING_MIN_S = 0.6                    # revelado minimo; revision (1.7 s) + revelado <= 2.5 s (requisito del Avance 1)
NO_PRESENCE_S = 5                         # reposo (SLEEP, pantalla atenuada) tras 5 s sin que el HC-SR04 vea a nadie en 30-120 cm
READY_TIMEOUT_S = 30                      # respaldo si el STM32 no manda tramas (sin sensor no se sabe si hay gente): READY -> inicio
RESULT_TIMEOUT_S = 45
SLEEP_AFTER_S = 120                       # respaldo sin sensor: inicio -> reposo

# Filtros: el potenciometro (0-1023) selecciona uno. 'css' es la vista previa en vivo.
FILTERS = [
    {"id": "natural", "name": "Natural",        "css": "contrast(1.04) saturate(1.05)"},
    {"id": "bw",      "name": "Blanco y negro", "css": "grayscale(1) contrast(1.18)"},
    {"id": "sepia",   "name": "Sepia",          "css": "sepia(.9) contrast(1.06)"},
    {"id": "vintage", "name": "Vintage",        "css": "sepia(.3) saturate(1.35) contrast(.95) brightness(1.06) hue-rotate(-8deg)"},
    {"id": "pop",     "name": "Pop",            "css": "saturate(1.9) contrast(1.2) brightness(1.03)"},
]


# ----------------------------------------------------------------------------------------------------------------
# Archivo de configuracion (Clase 22): clave = valor, un valor por linea, # para comentarios.
# Se busca en este orden: $FOTOBUT_CONF, /etc/fotobut/fotobut.conf y fotobut.conf en la carpeta del proyecto.
# Solo se aceptan las claves de AJUSTABLES; un valor con tipo equivocado se ignora y se anota (nunca tira el proceso).
# ----------------------------------------------------------------------------------------------------------------
AJUSTABLES = ("WIFI_SSID", "WIFI_PASS", "AP_IP", "SHARE_TTL_S", "PRESENCE_MIN_CM", "PRESENCE_MAX_CM", "PRESENCE_SAMPLES",
              "NO_PRESENCE_S", "READY_TIMEOUT_S", "RESULT_TIMEOUT_S", "SLEEP_AFTER_S", "COUNT_FROM", "TICK_HZ", "TICK_MS",
              "SHUTTER_HZ", "SHUTTER_MS", "RESET_HZ", "RESET_MS", "GPIO_BUTTON", "GPIO_RESET", "BUTTON_ACTIVE_LOW",
              "UART_PORT", "UART_BAUD", "CAJA_NEGRA_DIAS")
CONF_ARCHIVO: str | None = None           # archivo que se leyo (None = valores por omision)
CONF_AVISOS: list[str] = []               # lo que se ignoro y por que (los procesos lo escriben en su registro al arrancar)


def _convertir(texto: str, actual):
    if isinstance(actual, bool):
        t = texto.lower()
        if t in ("si", "sí", "true", "1", "yes"):
            return True
        if t in ("no", "false", "0"):
            return False
        raise ValueError("se esperaba si/no")
    if isinstance(actual, int):
        return int(texto, 0)
    if isinstance(actual, float):
        return float(texto)
    return texto


def cargar_conf(ruta: str | None = None) -> None:
    global CONF_ARCHIVO
    candidatos = [ruta] if ruta else [os.environ.get("FOTOBUT_CONF"), "/etc/fotobut/fotobut.conf", str(BASE / "fotobut.conf")]
    archivo = next((c for c in candidatos if c and os.path.isfile(c)), None)
    if not archivo:
        return
    g = globals()
    try:
        lineas = open(archivo, encoding="utf-8").read().splitlines()
    except OSError as e:
        CONF_AVISOS.append(f"no se pudo leer {archivo}: {e}")
        return
    CONF_ARCHIVO = archivo
    for n, linea in enumerate(lineas, 1):
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        if "=" not in linea:
            CONF_AVISOS.append(f"{archivo}:{n}: falta '=' (se ignora)")
            continue
        clave, valor = (x.strip() for x in linea.split("=", 1))
        clave = clave.upper()
        if clave not in AJUSTABLES:
            CONF_AVISOS.append(f"{archivo}:{n}: '{clave}' no es ajustable (se ignora)")
            continue
        try:
            g[clave] = _convertir(valor.strip('"').strip("'"), g[clave])
        except ValueError as e:
            CONF_AVISOS.append(f"{archivo}:{n}: valor invalido para {clave}: {valor} ({e}; se conserva {g[clave]!r})")
    if len(WIFI_PASS) < 8:
        CONF_AVISOS.append("WIFI_PASS necesita al menos 8 caracteres (WPA2): se usa fotobut2026")
        g["WIFI_PASS"] = "fotobut2026"
    if not (0 < PRESENCE_MIN_CM < PRESENCE_MAX_CM <= 400):
        CONF_AVISOS.append("PRESENCE_MIN_CM/PRESENCE_MAX_CM fuera de 1-400 cm o invertidos: se usan 30 y 120")
        g["PRESENCE_MIN_CM"], g["PRESENCE_MAX_CM"] = 30, 120


def resumen_conf() -> str:
    """Una linea para el registro de cada proceso al arrancar."""
    origen = CONF_ARCHIVO or "sin archivo de configuracion: valores por omision"
    return f"configuracion: {origen}" + (f" ({len(CONF_AVISOS)} avisos)" if CONF_AVISOS else "")


cargar_conf()
