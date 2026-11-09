"""Camara. SimCamera dibuja una escena animada (para desarrollar sin hardware).
La PiCamera real (picamera2) entra en la fase 3 con esta misma interfaz:
    get_jpeg() -> bytes   (cuadro de vista previa, ~15 fps)
    capture(path)         (foto fija en alta resolucion)
"""
from __future__ import annotations
import io, math, time
from PIL import Image, ImageDraw, ImageFont

from . import config as C

_FONT = str(C.WEB_DIR / "fonts" / "Poppins-Medium.ttf")


def scene(t: float, w: int, h: int) -> Image.Image:
    """Escena de prueba: dos personajes animados sobre fondo con bokeh."""
    s = h / 540.0
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):                                   # degradado de fondo
        k = y / h
        px.line([(0, y), (w, y)], fill=(int(70 + 90 * k), int(150 - 40 * k), int(170 - 20 * k)))
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(14):                                  # bokeh
        cx = (i * 173 % 997) / 997 * w
        cy = (i * 91 % 463) / 463 * h * 0.8
        r = (28 + (i * 37) % 50) * s
        a = 38 + (i * 13) % 30
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 235, 190, a))
    d.rectangle([0, h * 0.82, w, h], fill=(30, 60, 50, 255))   # piso

    def person(cx, base, scale, skin, hair, shirt, phase):
        r = 62 * s * scale
        bob = math.sin(t * 2.2 + phase) * 5 * s
        top = base - 300 * s * scale + bob
        d.rounded_rectangle([cx - 105 * s * scale, top + r * 1.9, cx + 105 * s * scale, base + 80 * s],
                            radius=int(52 * s * scale), fill=shirt)                       # cuerpo
        wave = math.sin(t * 5 + phase)
        ax, ay = cx + 105 * s * scale, top + r * 2.3
        hx, hy = ax + (50 + 12 * wave) * s * scale, ay - (95 + 35 * wave) * s * scale
        d.line([ax, ay, hx, hy], fill=skin, width=int(26 * s * scale))                    # brazo saludando
        d.ellipse([hx - 20 * s * scale, hy - 20 * s * scale, hx + 20 * s * scale, hy + 20 * s * scale], fill=skin)
        d.ellipse([cx - r, top, cx + r, top + r * 2], fill=skin)                          # cabeza
        d.pieslice([cx - r * 1.08, top - r * 0.12, cx + r * 1.08, top + r * 1.55], 180, 360, fill=hair)
        blink = 0.15 if (t * 0.7 + phase) % 3.4 < 0.16 else 1.0
        for ex in (-0.38, 0.38):
            e = r * 0.13
            d.ellipse([cx + ex * r - e, top + r * 1.02 - e * blink, cx + ex * r + e, top + r * 1.02 + e * blink],
                      fill=(30, 25, 30, 255))
        d.arc([cx - r * 0.5, top + r * 1.1, cx + r * 0.5, top + r * 1.65], 15, 165, fill=(150, 40, 60, 255),
              width=max(2, int(5 * s * scale)))                                           # sonrisa
        d.ellipse([cx - r * 0.78, top + r * 1.3, cx - r * 0.5, top + r * 1.5], fill=(255, 120, 120, 90))
        d.ellipse([cx + r * 0.5, top + r * 1.3, cx + r * 0.78, top + r * 1.5], fill=(255, 120, 120, 90))

    person(w * 0.36, h * 0.9, 1.0, (233, 183, 140), (60, 38, 30, 255), (255, 106, 61, 255), 0.0)
    person(w * 0.64, h * 0.92, 0.86, (178, 120, 85), (25, 20, 25, 255), (255, 209, 102, 255), 1.7)
    return img


class SimCamera:
    is_sim = True

    def get_jpeg(self) -> bytes:
        buf = io.BytesIO()
        scene(time.monotonic(), 960, 540).save(buf, "JPEG", quality=72)
        return buf.getvalue()

    def capture(self, path) -> None:
        scene(time.monotonic(), 1920, 1080).save(path, "JPEG", quality=92)

    def close(self) -> None:
        pass


class PiCamera:
    """[C21-camara] Driver unicam + imx708 (V4L2/libcamera) -> /dev/video0, /dev/media*; picamera2.
    Camera Module 3 (IMX708) con picamera2. Vista previa MJPEG (flujo lores) + fotos 1080p (flujo main)."""
    is_sim = False

    def __init__(self):
        import threading
        from picamera2 import Picamera2
        from picamera2.encoders import MJPEGEncoder
        from picamera2.outputs import FileOutput

        class _Out(io.BufferedIOBase):
            def __init__(s):
                s.frame, s.seq, s.cond = None, 0, threading.Condition()

            def write(s, buf):
                with s.cond:
                    s.frame, s.seq = bytes(buf), s.seq + 1
                    s.cond.notify_all()
                return len(buf)

        self._tl = threading.local()
        self.out = _Out()
        self.cam = Picamera2()
        cfg = self.cam.create_video_configuration(
            main={"size": (1920, 1080), "format": "RGB888"},
            lores={"size": (960, 540), "format": "YUV420"},
            controls={"FrameRate": 30}, buffer_count=4)
        self.cam.configure(cfg)
        self.cam.options["quality"] = 92
        try:                                                  # enfoque automatico continuo (Camera Module 3)
            self.cam.set_controls({"AfMode": 2})
        except Exception:                                     # noqa: BLE001
            pass
        self.cam.start_recording(MJPEGEncoder(), FileOutput(self.out), name="lores")

    def get_jpeg(self) -> bytes:
        last = getattr(self._tl, "seq", 0)
        with self.out.cond:
            self.out.cond.wait_for(lambda: self.out.seq != last, timeout=1.0)
            self._tl.seq = self.out.seq
            return self.out.frame or b""

    def capture(self, path) -> None:
        self.cam.capture_file(str(path), name="main")

    def close(self) -> None:
        try:
            self.cam.stop_recording()
            self.cam.close()
        except Exception:                                     # noqa: BLE001
            pass
