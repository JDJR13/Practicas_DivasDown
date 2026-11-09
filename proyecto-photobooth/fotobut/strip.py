"""Arma la tira de 3 fotos (collage) con marco, titulo y pie. Resultado ~800x2222 px."""
from __future__ import annotations
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config as C
from .filters import apply_filter

CREAM, GREEN, DEEP, ORANGE, YELLOW = (255, 246, 227), (21, 80, 59), (11, 46, 34), (255, 106, 61), (255, 209, 102)
W, PH, PW, M = 800, 540, 720, 40
_F = lambda name, size: ImageFont.truetype(str(C.WEB_DIR / "fonts" / name), size)

MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _star(d: ImageDraw.ImageDraw, cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def _spaced(d, xy, text, font, fill, spacing, anchor_center=True):
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = xy[0] - total / 2 if anchor_center else xy[0]
    for ch, w in zip(text, widths):
        d.text((x, xy[1]), ch, font=font, fill=fill)
        x += w + spacing


def compose(photos: list[Image.Image], filter_id: str, label: str, when: datetime | None = None) -> Image.Image:
    when = when or datetime.now()
    top, head, foot = 56, 170, 230
    H = top + head + 3 * PH + 2 * M + 40 + foot + 36
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([14, 14, W - 15, H - 15], radius=34, fill=CREAM)
    # encabezado
    _spaced(d, (W / 2, top + 20), "EL FOTOBUT", _f_title, DEEP, 6)
    for i, x in enumerate((130, W / 2, W - 130)):
        _star(d, x, top + 134, 13 if i == 1 else 9, ORANGE if i == 1 else YELLOW)
    d.line([160, top + 134, W / 2 - 40, top + 134], fill=DEEP, width=3)
    d.line([W / 2 + 40, top + 134, W - 160, top + 134], fill=DEEP, width=3)
    # fotos
    y = top + head
    for p in photos[:3]:
        p = ImageOps.fit(apply_filter(p, filter_id), (PW, PH), Image.LANCZOS)
        d.rounded_rectangle([M - 8, y - 8, M + PW + 7, y + PH + 7], radius=14, fill=DEEP)
        img.paste(p, (M, y))
        y += PH + M
    # pie
    fy = y + 6
    _spaced(d, (W / 2, fy), f"{when.day:02d} {MESES[when.month - 1]} {when.year}  ·  {when:%H:%M}", _f_foot, DEEP, 3)
    _spaced(d, (W / 2, fy + 58), f"SESIÓN {label}", _f_foot_b, ORANGE, 4)
    tag = ImageFont.truetype(str(C.WEB_DIR / "fonts" / "Lora-Italic-Variable.ttf"), 34)
    t = "¡Gracias por sonreír!"
    d.text((W / 2 - d.textlength(t, font=tag) / 2, fy + 118), t, font=tag, fill=GREEN)
    _spaced(d, (W / 2, fy + 168), "DIVASDOWN · FSE · UNAM", _f_small, GREEN, 4)
    return img


_f_title = _F("Poppins-Bold.ttf", 78)
_f_foot = _F("Poppins-Medium.ttf", 32)
_f_foot_b = _F("Poppins-Bold.ttf", 36)
_f_small = _F("Poppins-Medium.ttf", 22)
