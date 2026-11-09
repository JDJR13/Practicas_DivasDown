"""I2C por /dev/i2c-1 sin dependencias (mismo metodo que tus practicas en C: ioctl I2C_SLAVE + read/write).
Incluye el BMP280 (compensacion entera del datasheet, centesimas de grado) y la pantalla OLED SSD1306 128x64."""
from __future__ import annotations
import fcntl, os, threading

I2C_SLAVE = 0x0703


class I2CBus:
    def __init__(self, bus: int = 1):
        self.fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
        self.lock = threading.Lock()          # el BMP280 y la OLED comparten el bus

    def write(self, addr: int, data: bytes) -> None:
        with self.lock:
            fcntl.ioctl(self.fd, I2C_SLAVE, addr)
            os.write(self.fd, data)

    def read_reg(self, addr: int, reg: int, n: int) -> bytes:
        with self.lock:
            fcntl.ioctl(self.fd, I2C_SLAVE, addr)
            os.write(self.fd, bytes([reg]))
            return os.read(self.fd, n)


class BMP280:
    """[C21-bmp280] Driver i2c-bcm2835 + i2c-dev -> /dev/i2c-1, direccion 0x77: ioctl(I2C_SLAVE) + read/write (misma tecnica de la P7)."""
    def __init__(self, bus: I2CBus, addr: int = 0x77):
        self.bus, self.addr = bus, addr
        b = bus.read_reg(addr, 0x88, 6)
        self.T1 = b[0] | (b[1] << 8)
        self.T2 = int.from_bytes(b[2:4], "little", signed=True)
        self.T3 = int.from_bytes(b[4:6], "little", signed=True)
        bus.write(addr, bytes([0xF4, 0x27]))   # temp x1, presion x1, modo normal

    def temperature_c(self) -> float:
        r = self.bus.read_reg(self.addr, 0xFA, 3)
        adc = (r[0] << 12) | (r[1] << 4) | (r[2] >> 4)
        var1 = (((adc >> 3) - (self.T1 << 1)) * self.T2) >> 11
        d = (adc >> 4) - self.T1
        var2 = (((d * d) >> 12) * self.T3) >> 14
        return (((var1 + var2) * 5 + 128) >> 8) / 100.0


class SSD1306:
    """[C21-oled] Mismo bus /dev/i2c-1, direccion 0x3C: comandos 0x00 y datos 0x40 de 128x64 (1024 bytes de framebuffer)."""
    """OLED 128x64 por I2C (0x3C). show(imagen_PIL) la dibuja completa."""
    W, H = 128, 64

    def __init__(self, bus: I2CBus, addr: int = 0x3C):
        self.bus, self.addr = bus, addr
        init = [0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40, 0x8D, 0x14, 0x20, 0x00,
                0xA1, 0xC8, 0xDA, 0x12, 0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF]
        for c in init:
            self._cmd(c)

    def _cmd(self, c: int) -> None:
        self.bus.write(self.addr, bytes([0x00, c]))

    def show(self, img) -> None:
        import numpy as np
        a = np.array(img.convert("1").resize((self.W, self.H)), dtype=np.uint8)        # (64,128) 0/1
        pages = a.reshape(8, 8, self.W)                                                  # pagina, bit, columna
        data = (pages * (1 << np.arange(8, dtype=np.uint8))[None, :, None]).sum(axis=1).astype(np.uint8)
        for c in (0x21, 0, self.W - 1, 0x22, 0, 7):
            self._cmd(c)
        buf = data.tobytes()
        for i in range(0, len(buf), 128):
            self.bus.write(self.addr, b"\x40" + buf[i:i + 128])

    def off(self) -> None:
        self._cmd(0xAE)
