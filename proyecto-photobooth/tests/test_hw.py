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

# Botones rojo (GPIO17) y azul (GPIO27) con un lgpio falso: antirrebote de 20 ms y aviso por separado
import time, types
from fotobut import config as C
lv = {C.GPIO_BUTTON: 1, C.GPIO_RESET: 1}                       # pull-up: 1 = suelto
fake = types.SimpleNamespace(SET_PULL_UP=32, gpiochip_open=lambda n: 7, claimed=[],
                             gpio_read=lambda h, pin: lv[pin])
fake.gpio_claim_input = lambda h, pin, flags: fake.claimed.append(pin)
sys.modules["lgpio"] = fake
sys.modules["spidev"] = sys.modules["serial"] = None           # la prueba no toca el SPI ni el UART reales (en la Pi los usa el servicio)
hal = PiHAL()
assert fake.claimed == [C.GPIO_BUTTON, C.GPIO_RESET], fake.claimed
assert hal.status()["button"] and hal.status()["reset"]
ev = []
hal.on_press = lambda t, d: ev.append(("rojo", d)); hal.on_reset = lambda t, d: ev.append(("azul", d))
def pulso(pin, ms):
    lv[pin] = 0; time.sleep(ms / 1000); lv[pin] = 1; time.sleep(0.06)
time.sleep(0.05)
pulso(C.GPIO_BUTTON, 150); assert ev == [("rojo", ev[0][1])] and ev[0][1] >= 20, ev
pulso(C.GPIO_RESET, 150);  assert [e[0] for e in ev] == ["rojo", "azul"], ev
pulso(C.GPIO_RESET, 6);    assert len(ev) == 2, "un rebote de 6 ms no debe contar"
i = hal.read(); assert (i.button_presses, i.reset_presses) == (1, 1), i
i = hal.read(); assert (i.button_presses, i.reset_presses) == (0, 0), i
hal.close()
print("Botones: rojo y azul OK (antirrebote %d ms)" % ev[0][1])
print("TODO OK")
