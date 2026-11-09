"""Dibuja la pantalla pequena (OLED 128x64) con el estado de la cabina. Tambien sirve en el simulador (/oled.png)."""
from __future__ import annotations
import socket
from PIL import Image, ImageDraw, ImageFont

from . import config as C

_FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
_LABEL = {"ATTRACT": "REPOSO", "SLEEP": "DORMIDO", "READY": "LISTO", "COUNTDOWN": "FOTO", "CAPTURE": "FOTO",
          "PROCESSING": "REVELANDO", "RESULT": "LISTA"}


def _font(size: int, bold=False):
    try:
        return ImageFont.truetype(_FONTS[1 if bold else 0], size)
    except Exception:                                    # noqa: BLE001
        return ImageFont.load_default()


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))                 # no envia nada: solo elige la interfaz
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:                                    # noqa: BLE001
        return "sin red"


def render(info: dict) -> Image.Image:
    """info: state, shot, temp_c, cpu_c, dist, sessions, ram_used, ram_total, ip, alert"""
    img = Image.new("1", (128, 64), 0)
    d = ImageDraw.Draw(img)
    alert = info.get("alert")
    state = info.get("state", "ATTRACT")
    label = _LABEL.get(state, state)
    if state in ("COUNTDOWN", "CAPTURE"):
        label = f"FOTO {info.get('shot', 1)}/{C.SHOTS}"
    # fila 1: titulo + estado (invertida si hay alerta)
    if alert:
        d.rectangle([0, 0, 127, 13], fill=1)
    d.text((2, 0), "FOTOBUT", font=_font(12, True), fill=0 if alert else 1)
    f = _font(10, True)
    w = d.textlength(label, font=f)
    d.text((126 - w, 2), label, font=f, fill=0 if alert else 1)
    f = _font(10)
    t = info.get("temp_c")
    cpu = info.get("cpu_c")
    dist = info.get("dist")
    ram_u, ram_t = info.get("ram_used"), info.get("ram_total")
    rows = [
        "! TEMP ALTA !" if alert else str(info.get("ip", "sin red")),
        f"Caja {t:4.1f}C CPU {cpu:2.0f}C" if t is not None and cpu is not None else (f"CPU {cpu:2.0f}C  BMP: --" if cpu is not None else "Temp: sin dato"),
        f"Dist {dist:3d}cm Ses {info.get('sessions', 0)}" if dist is not None else f"Dist ---    Ses {info.get('sessions', 0)}",
        f"RAM {ram_u}/{ram_t} MB" if ram_u is not None else "RAM --",
    ]
    for i, r in enumerate(rows):
        d.text((2, 15 + i * 12), r, font=f, fill=1)
    return img
