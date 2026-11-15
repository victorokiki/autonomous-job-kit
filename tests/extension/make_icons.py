"""Generate the Autonomous Job Kit Autofill toolbar icons (a white "A" on a blue rounded square).

Usage:  python3 tests/extension/make_icons.py
Writes extension/icons/icon16.png, icon32.png, icon48.png and icon128.png using only the
standard library (zlib + struct). Shapes are drawn with 4x4 supersampling for smooth edges.
"""
import math
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'extension', 'icons')
BLUE = (31, 95, 191)
WHITE = (255, 255, 255)
STROKE = 0.115  # letter stroke width, as a fraction of the icon size

# Letter strokes as line segments in a 0..1 box: (x1, y1, x2, y2)
A = [(0.30, 0.74, 0.50, 0.26), (0.50, 0.26, 0.70, 0.74), (0.385, 0.57, 0.615, 0.57)]


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def in_rounded_square(x, y, r=0.22):
    cx = min(max(x, r), 1 - r)
    cy = min(max(y, r), 1 - r)
    return math.hypot(x - cx, y - cy) <= r and 0 <= x <= 1 and 0 <= y <= 1


def in_letters(x, y):
    h = STROKE / 2
    return any(seg_dist(x, y, *s) <= h for s in A)


def render(size):
    rows = []
    n = 4
    for j in range(size):
        row = bytearray([0])
        for i in range(size):
            bg = fg = 0
            for sj in range(n):
                for si in range(n):
                    x = (i + (si + 0.5) / n) / size
                    y = (j + (sj + 0.5) / n) / size
                    if in_rounded_square(x, y):
                        bg += 1
                        if in_letters(x, y):
                            fg += 1
            total = n * n
            a = bg / total
            if bg:
                f = fg / bg
                rgb = [round(BLUE[k] * (1 - f) + WHITE[k] * f) for k in range(3)]
            else:
                rgb = [0, 0, 0]
            row += bytes(rgb + [round(a * 255)])
        rows.append(bytes(row))
    raw = b''.join(rows)

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def main():
    os.makedirs(OUT, exist_ok=True)
    for size in (16, 32, 48, 128):
        path = os.path.join(OUT, 'icon%d.png' % size)
        with open(path, 'wb') as fh:
            fh.write(render(size))
        print(os.path.abspath(path))


if __name__ == '__main__':
    main()
