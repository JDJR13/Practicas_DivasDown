"""Generador de codigos QR en Python puro (modo byte, nivel de correccion M, versiones 1-10).
Sin dependencias: pensado para correr en la Raspberry Pi sin internet.
    matriz = make_qr("https://...")   # lista de filas de booleanos (True = modulo oscuro)
"""
from __future__ import annotations

# version -> (codewords_totales, ec_por_bloque, [(n_bloques, datos_por_bloque), ...])  [nivel M]
_M = {
    1: (26, 10, [(1, 16)]),
    2: (44, 16, [(1, 28)]),
    3: (70, 26, [(1, 44)]),
    4: (100, 18, [(2, 32)]),
    5: (134, 24, [(2, 43)]),
    6: (172, 16, [(4, 27)]),
    7: (196, 18, [(4, 31)]),
    8: (242, 22, [(2, 38), (2, 39)]),
    9: (292, 22, [(3, 36), (2, 37)]),
    10: (346, 26, [(4, 43), (1, 44)]),
}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
          7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}


def _rs_mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _rs_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _rs_mul(root, 2)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _rs_mul(coef, factor)
    return result


def _data_capacity(version: int) -> int:
    _, _, groups = _M[version]
    return sum(n * d for n, d in groups)


def _pick_version(nbytes: int) -> int:
    for v in range(1, 11):
        count_bits = 8 if v < 10 else 16
        if 4 + count_bits + 8 * nbytes <= 8 * _data_capacity(v):
            return v
    raise ValueError("Texto demasiado largo para el QR (max ~213 bytes)")


def _build_codewords(data: bytes, version: int) -> list[int]:
    cap = _data_capacity(version)
    bits: list[int] = []

    def put(val: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)

    put(0b0100, 4)
    put(len(data), 8 if version < 10 else 16)
    for b in data:
        put(b, 8)
    put(0, min(4, 8 * cap - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    cw = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(cw) < cap:
        cw.append(pad)
        pad ^= 0xEC ^ 0x11
    total, ec_len, groups = _M[version]
    blocks, pos = [], 0
    for n, d in groups:
        for _ in range(n):
            blocks.append(cw[pos:pos + d])
            pos += d
    div = _rs_divisor(ec_len)
    ecs = [_rs_remainder(b, div) for b in blocks]
    out: list[int] = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(ec_len):
        for e in ecs:
            out.append(e[i])
    assert len(out) == total
    return out


class _Matrix:
    def __init__(self, version: int):
        self.version = version
        self.size = version * 4 + 17
        self.m = [[False] * self.size for _ in range(self.size)]
        self.fn = [[False] * self.size for _ in range(self.size)]

    def set_fn(self, x: int, y: int, dark: bool) -> None:
        self.m[y][x] = dark
        self.fn[y][x] = True

    def draw_function_patterns(self) -> None:
        n = self.size
        for i in range(n):
            self.set_fn(6, i, i % 2 == 0)
            self.set_fn(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self.set_fn(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = _ALIGN[self.version]
        for i, cx in enumerate(pos):
            for j, cy in enumerate(pos):
                if (i == 0 and j == 0) or (i == 0 and j == len(pos) - 1) or (i == len(pos) - 1 and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set_fn(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format(0)  # reserva las zonas
        self.draw_version()

    def draw_format(self, mask: int) -> None:
        n = self.size
        data = (0 << 3) | mask            # nivel M = 00
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = ((data << 10) | rem) ^ 0x5412
        g = lambda i: ((bits >> i) & 1) != 0
        for i in range(0, 6):
            self.set_fn(8, i, g(i))
        self.set_fn(8, 7, g(6))
        self.set_fn(8, 8, g(7))
        self.set_fn(7, 8, g(8))
        for i in range(9, 15):
            self.set_fn(14 - i, 8, g(i))
        for i in range(0, 8):
            self.set_fn(n - 1 - i, 8, g(i))
        for i in range(8, 15):
            self.set_fn(8, n - 15 + i, g(i))
        self.set_fn(8, n - 8, True)

    def draw_version(self) -> None:
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = (self.version << 12) | rem
        for i in range(18):
            b = ((bits >> i) & 1) != 0
            a = self.size - 11 + i % 3
            c = i // 3
            self.set_fn(a, c, b)
            self.set_fn(c, a, b)

    def draw_codewords(self, data: list[int]) -> None:
        n, i = self.size, 0
        total = len(data) * 8
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(n):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = n - 1 - vert if upward else vert
                    if not self.fn[y][x] and i < total:
                        self.m[y][x] = ((data[i >> 3] >> (7 - (i & 7))) & 1) != 0
                        i += 1
            right -= 2

    def apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            for x in range(self.size):
                if self.fn[y][x]:
                    continue
                inv = [
                    (x + y) % 2 == 0, y % 2 == 0, x % 3 == 0, (x + y) % 3 == 0,
                    (x // 3 + y // 2) % 2 == 0, x * y % 2 + x * y % 3 == 0,
                    (x * y % 2 + x * y % 3) % 2 == 0, ((x + y) % 2 + x * y % 3) % 2 == 0,
                ][mask]
                if inv:
                    self.m[y][x] = not self.m[y][x]

    def penalty(self) -> int:
        n, m, score = self.size, self.m, 0
        for lines in (m, [list(c) for c in zip(*m)]):      # filas y columnas
            for row in lines:
                run, prev = 1, row[0]
                for v in row[1:]:
                    if v == prev:
                        run += 1
                    else:
                        if run >= 5:
                            score += 3 + run - 5
                        run, prev = 1, v
                if run >= 5:
                    score += 3 + run - 5
                s = "".join("1" if v else "0" for v in row)
                score += 40 * (s.count("10111010000") + s.count("00001011101"))
        for y in range(n - 1):
            for x in range(n - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    score += 3
        dark = sum(v for row in m for v in row)
        score += (abs(dark * 20 - n * n * 10) // (n * n)) * 10
        return score


def make_qr(text: str) -> list[list[bool]]:
    data = text.encode("utf-8")
    version = _pick_version(len(data))
    codewords = _build_codewords(data, version)
    best, best_pen = None, None
    for mask in range(8):
        q = _Matrix(version)
        q.draw_function_patterns()
        q.draw_codewords(codewords)
        q.apply_mask(mask)
        q.draw_format(mask)
        pen = q.penalty()
        if best_pen is None or pen < best_pen:
            best, best_pen = q, pen
    return best.m
