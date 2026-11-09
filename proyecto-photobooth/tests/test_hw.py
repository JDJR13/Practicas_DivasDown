"""Pruebas de la capa de hardware sin hardware: BMP280 (ejemplo del datasheet), empaquetado de la OLED y trama UART."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PIL import Image
from fotobut.i2c import BMP280, SSD1306

class FakeBus:
    def __init__(self): self.writes = []
    def write(self, addr, data): self.writes.append((addr, bytes(data)))
    def read_reg(self, addr, reg, n):
        if reg == 0x88:      # T1=27504, T2=26435, T3=-1000 (ejemplo del datasheet del BMP280)
            return (27504).to_bytes(2, "little") + (26435).to_bytes(2, "little") + (-1000).to_bytes(2, "little", signed=True)
        if reg == 0xFA:      # adc_T = 519888 -> 25.08 C
            v = 519888 << 4
            return bytes([(v >> 16) & 255, (v >> 8) & 255, v & 255])

b = BMP280(FakeBus(), 0x77)
t = b.temperature_c(); print("BMP280:", t, "C"); assert abs(t - 25.08) < 0.01

bus = FakeBus(); o = SSD1306(bus, 0x3C)
img = Image.new("1", (128, 64), 0); img.putpixel((5, 10), 1); img.putpixel((127, 63), 1)
bus.writes.clear(); o.show(img)
data = b"".join(d[1:] for a, d in bus.writes if d[0] == 0x40)
assert len(data) == 1024, len(data)
assert data[1 * 128 + 5] == (1 << 2), data[1*128+5]          # y=10 -> pagina 1, bit 2
assert data[7 * 128 + 127] == (1 << 7)                        # y=63 -> pagina 7, bit 7
assert sum(1 for x in data if x) == 2
print("SSD1306: empaquetado OK (1024 bytes)")

from fotobut.hal import PiHAL
for raw, exp in ((b"DIST:87 cm\r\n", 87), (b"DIST:ERR\r\n", None)):
    m = PiHAL._RX.search(raw); assert m is not None
    assert (int(m.group(1)) if m.group(1) else None) == exp
print("UART: tramas OK")
print("TODO OK")
