"""Filtros para las fotos finales. Replican la vista previa CSS (config.FILTERS) para que lo que ves es lo que sale."""
from __future__ import annotations
import numpy as np
from PIL import Image, ImageEnhance

_SEPIA = np.array([[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]], dtype=np.float32)


def _sepia(img: Image.Image, amount: float) -> Image.Image:
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    m = (1 - amount) * np.eye(3, dtype=np.float32) + amount * _SEPIA
    return Image.fromarray(np.clip(a @ m.T, 0, 255).astype(np.uint8))


def _vignette(img: Image.Image, strength: float) -> Image.Image:
    w, h = img.size
    y, x = np.ogrid[:h, :w]
    r = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
    k = 1 - strength * np.clip(r - 0.55, 0, 1) ** 1.6
    a = np.asarray(img, dtype=np.float32) * k[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def apply_filter(img: Image.Image, fid: str) -> Image.Image:
    img = img.convert("RGB")
    if fid == "bw":
        img = ImageEnhance.Contrast(img.convert("L").convert("RGB")).enhance(1.18)
    elif fid == "sepia":
        img = ImageEnhance.Contrast(_sepia(img, 0.9)).enhance(1.06)
    elif fid == "vintage":
        img = _sepia(img, 0.3)
        img = ImageEnhance.Color(img).enhance(1.35)
        img = ImageEnhance.Contrast(img).enhance(0.95)
        img = ImageEnhance.Brightness(img).enhance(1.06)
        img = _vignette(img, 0.55)
    elif fid == "pop":
        img = ImageEnhance.Color(img).enhance(1.9)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Brightness(img).enhance(1.03)
    else:                                              # natural
        img = ImageEnhance.Color(ImageEnhance.Contrast(img).enhance(1.04)).enhance(1.05)
    return img
