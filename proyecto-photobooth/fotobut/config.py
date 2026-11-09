"""Configuracion central de El Fotobut (SmartBooth FSE, equipo DivasDown)."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
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
WIFI_SSID, WIFI_PASS = "Fotobut", "fotobut2026"   # (si los cambias, tambien en scripts/setup_ap.sh)
MAX_TMP_SESSIONS = 20                     # sesiones que se conservan en RAM (/tmp); la tira final queda en la microSD

# Buzzer piezoelectrico: suena mas fuerte cerca de su frecuencia de resonancia (tipico 2-4 kHz).
# Busca la mejor con:  python3 tools/buzzer_sweep.py
TICK_HZ, TICK_MS = 2700, 160              # tono de la cuenta regresiva
SHUTTER_HZ, SHUTTER_MS = 3400, 220        # obturador

# Hardware (pines segun el diagrama de bloques)
GPIO_BUTTON = 17
BUTTON_ACTIVE_LOW = True       # pull-up interna: presionado = 0 V (si tu boton va a 3.3V, pon False)
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
READY_TIMEOUT_S = 30
RESULT_TIMEOUT_S = 45
SLEEP_AFTER_S = 120

# Filtros: el potenciometro (0-1023) selecciona uno. 'css' es la vista previa en vivo.
FILTERS = [
    {"id": "natural", "name": "Natural",        "css": "contrast(1.04) saturate(1.05)"},
    {"id": "bw",      "name": "Blanco y negro", "css": "grayscale(1) contrast(1.18)"},
    {"id": "sepia",   "name": "Sepia",          "css": "sepia(.9) contrast(1.06)"},
    {"id": "vintage", "name": "Vintage",        "css": "sepia(.3) saturate(1.35) contrast(.95) brightness(1.06) hue-rotate(-8deg)"},
    {"id": "pop",     "name": "Pop",            "css": "saturate(1.9) contrast(1.2) brightness(1.03)"},
]
