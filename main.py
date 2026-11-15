#!/usr/bin/env python3
"""ai-excited-01 entry — "The Drawing Escaped".

A giant yellow pencil draws a red rocket on a sheet of paper; the rocket
bursts off the page into a starry sky, trailing sketch-line smoke, and
shouts I'M ALIVE! in a speech bubble. The surprise is the drawing coming
alive: the pencil's own sketch lines become the rocket's exhaust.

Pure Python 3.13 standard library (zlib + struct for the PNG encoder).
Fully deterministic: every pixel comes from fixed constants and a
fixed-seed generator, so two runs write byte-identical output.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------------------
# Framebuffer: one bytearray of RGB triples, row-major.
# ---------------------------------------------------------------------------
buf = bytearray(W * H * 3)


def _clip(x0, y0, x1, y1):
    x0 = max(0, min(W - 1, x0))
    y0 = max(0, min(H - 1, y0))
    x1 = max(0, min(W - 1, x1))
    y1 = max(0, min(H - 1, y1))
    return x0, y0, x1, y1


def put(x, y, r, g, b, a=255):
    """Set one pixel, alpha-blended over what is already there."""
    if x < 0 or x >= W or y < 0 or y >= H or a <= 0:
        return
    i = (y * W + x) * 3
    if a >= 255:
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b
    else:
        buf[i] = (buf[i] * (255 - a) + r * a) // 255
        buf[i + 1] = (buf[i + 1] * (255 - a) + g * a) // 255
        buf[i + 2] = (buf[i + 2] * (255 - a) + b * a) // 255


def fill_rect(x0, y0, x1, y1, col, a=255):
    x0, y0, x1, y1 = _clip(x0, y0, x1, y1)
    if x1 < x0 or y1 < y0:
        return
    r, g, b = col
    for y in range(y0, y1 + 1):
        base = (y * W + x0) * 3
        if a >= 255:
            for x in range(x0, x1 + 1):
                j = base + (x - x0) * 3
                buf[j] = r
                buf[j + 1] = g
                buf[j + 2] = b
        else:
            for x in range(x0, x1 + 1):
                j = base + (x - x0) * 3
                buf[j] = (buf[j] * (255 - a) + r * a) // 255
                buf[j + 1] = (buf[j + 1] * (255 - a) + g * a) // 255
                buf[j + 2] = (buf[j + 2] * (255 - a) + b * a) // 255


def disc(cx, cy, rad, col, a=255):
    """Filled circle, centre (cx, cy), radius rad."""
    r, g, b = col
    x0 = int(cx - rad) - 1
    x1 = int(cx + rad) + 1
    y0 = int(cy - rad) - 1
    y1 = int(cy + rad) + 1
    x0, y0, x1, y1 = _clip(x0, y0, x1, y1)
    for y in range(y0, y1 + 1):
        dy = y - cy
        span = rad * rad - dy * dy
        if span < 0:
            continue
        dx = int(math.sqrt(span))
        xa, xb = int(cx - dx), int(cx + dx)
        xa = max(xa, x0)
        xb = min(xb, x1)
        base = (y * W + xa) * 3
        if a >= 255:
            for x in range(xa, xb + 1):
                j = base + (x - xa) * 3
                buf[j] = r
                buf[j + 1] = g
                buf[j + 2] = b
        else:
            for x in range(xa, xb + 1):
                j = base + (x - xa) * 3
                buf[j] = (buf[j] * (255 - a) + r * a) // 255
                buf[j + 1] = (buf[j + 1] * (255 - a) + g * a) // 255
                buf[j + 2] = (buf[j + 2] * (255 - a) + b * a) // 255


def poly(points, col, a=255):
    """Filled polygon (scanline, even-odd). Points are (x, y) floats."""
    if len(points) < 3:
        return
    r, g, b = col
    ys = [p[1] for p in points]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, y0p = points[i]
            x1, y1p = points[(i + 1) % n]
            if (y0p <= y < y1p) or (y1p <= y < y0p):
                t = (y + 0.5 - y0p) / (y1p - y0p)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k])))
            xb = min(W - 1, int(math.floor(xs[k + 1])))
            if xb < xa:
                continue
            base = (y * W + xa) * 3
            if a >= 255:
                for x in range(xa, xb + 1):
                    j = base + (x - xa) * 3
                    buf[j] = r
                    buf[j + 1] = g
                    buf[j + 2] = b
            else:
                for x in range(xa, xb + 1):
                    j = base + (x - xa) * 3
                    buf[j] = (buf[j] * (255 - a) + r * a) // 255
                    buf[j + 1] = (buf[j + 1] * (255 - a) + g * a) // 255
                    buf[j + 2] = (buf[j + 2] * (255 - a) + b * a) // 255


def thick_line(x0, y0, x1, y1, w, col, a=255):
    """A line drawn as a chain of discs (round caps, round joins)."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    steps = max(1, int(dist / max(1.0, w * 0.4)))
    rad = w / 2.0
    for s in range(steps + 1):
        t = s / steps
        disc(x0 + dx * t, y0 + dy * t, rad, col, a)


def polyline(points, w, col, a=255):
    for i in range(len(points) - 1):
        thick_line(points[i][0], points[i][1], points[i + 1][0],
                   points[i + 1][1], w, col, a)


def sparkle(cx, cy, rad, col, a=255):
    """Four-point star (a diamond with pinched sides)."""
    w = rad * 0.22
    poly([(cx, cy - rad), (cx + w, cy - w), (cx + rad, cy), (cx + w, cy + w),
          (cx, cy + rad), (cx - w, cy + w), (cx - rad, cy), (cx - w, cy - w)],
         col, a)


def rotated_rect(cx, cy, length, width, angle_deg, col, a=255):
    """Rectangle of `length` along `angle_deg`, centred at (cx, cy)."""
    t = math.radians(angle_deg)
    ux, uy = math.cos(t), math.sin(t)
    vx, vy = -uy, ux
    hl, hw = length / 2.0, width / 2.0
    pts = [
        (cx + ux * hl + vx * hw, cy + uy * hl + vy * hw),
        (cx - ux * hl + vx * hw, cy - uy * hl + vy * hw),
        (cx - ux * hl - vx * hw, cy - uy * hl - vy * hw),
        (cx + ux * hl - vx * hw, cy + uy * hl - vy * hw),
    ]
    poly(pts, col, a)
    return pts


def rounded_rect(x0, y0, x1, y1, rad, col, a=255):
    fill_rect(int(x0 + rad), int(y0), int(x1 - rad), int(y1), col, a)
    fill_rect(int(x0), int(y0 + rad), int(x1), int(y1 - rad), col, a)
    for cx, cy in ((x0 + rad, y0 + rad), (x1 - rad, y0 + rad),
                   (x0 + rad, y1 - rad), (x1 - rad, y1 - rad)):
        disc(cx, cy, rad, col, a)


# ---------------------------------------------------------------------------
# Deterministic pseudo-random numbers (fixed seed LCG) — stars only.
# ---------------------------------------------------------------------------
def lcg(seed):
    state = seed & 0xFFFFFFFF

    def nxt():
        nonlocal state
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        return state / 4294967296.0

    return nxt


# ---------------------------------------------------------------------------
# 5x7 pixel font (only the glyphs the image needs, plus a few spares).
# ---------------------------------------------------------------------------
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def text_width(s, scale):
    return len(s) * (5 * scale + scale) - scale


def draw_text(s, x, y, scale, col):
    """Draw string s with its top-left corner at (x, y)."""
    cx = x
    for ch in s:
        glyph = FONT.get(ch, FONT[' '])
        for row in range(7):
            bits = glyph[row]
            for c in range(5):
                if bits[c] == '1':
                    fill_rect(cx + c * scale, y + row * scale,
                              cx + c * scale + scale - 1,
                              y + row * scale + scale - 1, col)
        cx += 6 * scale

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
SKY_TOP = (7, 11, 36)
SKY_MID = (27, 20, 69)
SKY_LOW = (58, 28, 92)
PAPER = (247, 239, 216)
PAPER_EDGE = (216, 201, 168)
PAPER_SHADOW = (10, 8, 40)
PENCIL_YELLOW = (246, 196, 69)
PENCIL_DARK = (214, 158, 32)
PENCIL_HI = (255, 224, 130)
ERASER = (232, 122, 144)
FERRULE = (200, 204, 212)
WOOD = (232, 192, 138)
GRAPHITE = (43, 43, 51)
ROCKET_WHITE = (250, 250, 246)
ROCKET_RED = (226, 52, 52)
ROCKET_DARK = (168, 28, 40)
WINDOW_BLUE = (64, 156, 220)
FLAME_YELLOW = (255, 214, 64)
FLAME_ORANGE = (255, 122, 26)
FLAME_WHITE = (255, 248, 220)
INK = (20, 32, 74)
SKETCH = (90, 84, 130)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_sky():
    """Vertical gradient + warm glow + deterministic starfield."""
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            col = lerp(SKY_TOP, SKY_MID, t / 0.55)
        else:
            col = lerp(SKY_MID, SKY_LOW, (t - 0.55) / 0.45)
        base = (y * W) * 3
        row = bytes(col) * W
        buf[base:base + W * 3] = row
    # Warm glow behind the rocket's flight path (top-right).
    for i in range(14, 0, -1):
        disc(770, 380, i * 26, (255, 154, 61), 7)
    # Stars, fixed seed so the sky never changes between runs.
    rnd = lcg(20261115)
    for _ in range(170):
        x = rnd() * W
        y = rnd() * 620
        s = rnd()
        rad = 1.0 if s < 0.6 else (2.0 if s < 0.9 else 3.0)
        disc(x, y, rad, (255, 255, 255), int(110 + rnd() * 145))
        if s > 0.93:
            sparkle(x, y, 9, (255, 244, 200), 200)


def draw_paper():
    """The sheet the rocket is drawn on, tilted, with a soft shadow."""
    # Shadow: same shape, shifted down-right, translucent dark.
    t = math.radians(-12)
    ux, uy = math.cos(t), math.sin(t)
    vx, vy = -uy, ux
    cx, cy, hl, hw = 470 + 16, 800 + 20, 490, 310
    poly([(cx + ux * hl + vx * hw, cy + uy * hl + vy * hw),
          (cx - ux * hl + vx * hw, cy - uy * hl + vy * hw),
          (cx - ux * hl - vx * hw, cy - uy * hl - vy * hw),
          (cx + ux * hl - vx * hw, cy + uy * hl - vy * hw)],
         PAPER_SHADOW, 70)
    cx, cy = 470, 800
    corners = [(cx + ux * hl + vx * hw, cy + uy * hl + vy * hw),
               (cx - ux * hl + vx * hw, cy - uy * hl + vy * hw),
               (cx - ux * hl - vx * hw, cy - uy * hl - vy * hw),
               (cx + ux * hl - vx * hw, cy + uy * hl - vy * hw)]
    poly(corners, PAPER)
    # Edge stroke (top and right edges catch the light).
    polyline(corners + [corners[0]], 5, PAPER_EDGE, 220)
    # Top-right corner curling up off the page.
    c = corners[0]
    poly([(c[0], c[1]), (c[0] - 74, c[1] + 26), (c[0] - 18, c[1] + 78)],
         (232, 220, 192))
    polyline([(c[0], c[1]), (c[0] - 74, c[1] + 26),
              (c[0] - 18, c[1] + 78)], 4, PAPER_EDGE, 200)


def draw_pencil():
    """Giant pencil, base at bottom-left, graphite tip touching the rocket."""
    # Axis: base (150, 950) -> tip (600, 540). Angle ~ -42.4 degrees.
    bx, by = 150.0, 950.0
    tx, ty = 600.0, 540.0
    dx, dy = tx - bx, ty - by
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    vx, vy = -uy, ux
    ang = math.degrees(math.atan2(dy, dx))

    def seg(dist0, dist1, half_w, col, a=255):
        """A band of the pencil between distances dist0..dist1 along axis."""
        cx = bx + ux * (dist0 + dist1) / 2.0
        cy = by + uy * (dist0 + dist1) / 2.0
        return rotated_rect(cx, cy, dist1 - dist0, half_w * 2, ang, col, a)

    def band_edge(dist0, dist1, side, off, w, col, a=255):
        """Thin stripe along one edge of a band (side=+1/-1)."""
        cx = bx + ux * (dist0 + dist1) / 2.0 + vx * side * off
        cy = by + uy * (dist0 + dist1) / 2.0 + vy * side * off
        rotated_rect(cx, cy, dist1 - dist0, w, ang, col, a)

    # Eraser, ferrule, body.
    seg(0, 52, 32, ERASER)
    seg(52, 96, 33, FERRULE)
    band_edge(52, 96, 1, 0, 6, (140, 146, 160))
    band_edge(52, 96, -1, 0, 6, (140, 146, 160))
    seg(96, 470, 32, PENCIL_YELLOW)
    band_edge(96, 470, 1, 24, 10, PENCIL_DARK, 200)
    band_edge(96, 470, -1, 24, 8, PENCIL_HI, 170)
    # Sharpened wood cone, then the graphite point.
    tip_x = bx + ux * 470
    tip_y = by + uy * 470
    base_cx = bx + ux * 470
    base_cy = by + uy * 470
    poly([(base_cx + vx * 32, base_cy + vy * 32),
          (base_cx - vx * 32, base_cy - vy * 32),
          (tx, ty)], WOOD)
    gx = bx + ux * (length - 46)
    gy = by + uy * (length - 46)
    poly([(gx + vx * 13, gy + vy * 13),
          (gx - vx * 13, gy - vy * 13),
          (tx, ty)], GRAPHITE)


def draw_rocket():
    """Red-and-white rocket launching up-right, off the paper."""
    # Tail centre C0, nose base C1, flight direction d (45 degrees up-right).
    c0x, c0y = 640.0, 510.0
    dx, dy = 0.70710678, -0.70710678
    px, py = 0.70710678, 0.70710678  # perpendicular (down-right)
    c1x, c1y = c0x + dx * 210, c0y + dy * 210
    hw = 46.0

    def pt(along, across):
        return (c0x + dx * along + px * across,
                c0y + dy * along + py * across)

    # Fins first (behind the body).
    for s in (1, -1):
        poly([pt(18, s * hw), pt(78, s * hw), pt(-52, s * 104)], ROCKET_RED)
        poly([pt(30, s * hw), pt(70, s * hw), pt(-30, s * 92)], ROCKET_DARK)
    # Body: white capsule.
    poly([pt(0, hw), pt(210, hw), pt(210, -hw), pt(0, -hw)], ROCKET_WHITE)
    disc(c1x, c1y, hw, ROCKET_WHITE)
    # Red nose cone.
    nose = (c1x + dx * 78, c1y + dy * 78)
    poly([pt(210, hw), pt(210, -hw), nose], ROCKET_RED)
    # Red band near the tail.
    poly([pt(28, hw), pt(62, hw), pt(62, -hw), pt(28, -hw)], ROCKET_RED)
    # Round window with a highlight.
    wx, wy = c0x + dx * 138, c0y + dy * 138
    disc(wx, wy, 27, WINDOW_BLUE)
    disc(wx - 8, wy - 8, 10, (255, 255, 255), 220)
    # Flame: three layered tongues pointing back down-left.
    fx, fy = c0x - dx * 8, c0y - dy * 8
    for length, width, col in ((168, 76, FLAME_YELLOW),
                               (122, 50, FLAME_ORANGE),
                               (74, 28, FLAME_WHITE)):
        tip = (fx - dx * length + px * 10, fy - dy * length + py * 10)
        poly([(fx + px * width / 2, fy + py * width / 2),
              (fx - px * width / 2, fy - py * width / 2),
              tip], col)
    # Sketch-line smoke: the pencil's own scribbles become exhaust.
    # Two loose spirals curling back from the tail, in sketch grey.
    for k, (sx, sy, size) in enumerate(((560, 600, 46), (500, 668, 60))):
        pts = []
        for i in range(26):
            a = i * 0.55 + k * 1.3
            r = size * (0.25 + 0.75 * i / 25.0)
            pts.append((sx + math.cos(a) * r, sy + math.sin(a) * r * 0.8))
        polyline(pts, 5, SKETCH, 150)
    # Soft smoke puffs trailing the flame.
    for i, (along, rad, a) in enumerate(((-150, 30, 190), (-215, 42, 165),
                                         (-285, 56, 135), (-360, 70, 105))):
        disc(c0x + dx * along + px * (10 - i * 6),
             c0y + dy * along + py * (10 - i * 6),
             rad, (245, 244, 240), a)
    # Speed lines streaking past the rocket.
    for across, start, ln in ((-150, 90, 150), (-190, 150, 190),
                              (150, 60, 130), (195, 130, 170),
                              (-120, 210, 110), (120, 220, 120)):
        x0 = c0x + dx * start + px * across
        y0 = c0y + dy * start + py * across
        thick_line(x0, y0, x0 + dx * ln, y0 + dy * ln, 6,
                   (255, 255, 255), 150)
    # Burst sparkles around the nose.
    sparkle(918, 196, 30, (255, 214, 64))
    sparkle(958, 330, 22, (255, 255, 255))
    sparkle(800, 158, 18, (255, 244, 200))
    sparkle(700, 250, 14, (255, 214, 64), 220)


def draw_bubble():
    """Speech bubble: the rocket shouts I'M ALIVE! at the viewer."""
    x0, y0, x1, y1 = 556, 52, 992, 238
    # Tail: ink triangle slightly larger, white triangle on top.
    poly([(772, y1 - 4), (872, y1 - 4), (900, 276)], INK)
    poly([(784, y1 - 4), (860, y1 - 4), (892, 264)], (255, 255, 255))
    # Body: ink rounded rect, then a white one inset by 7 px.
    rounded_rect(x0, y0, x1, y1, 34, INK)
    rounded_rect(x0 + 7, y0 + 7, x1 - 7, y1 - 7, 28, (255, 255, 255))
    scale = 7
    line1 = "I'M"
    line2 = "ALIVE!"
    draw_text(line1, x0 + (x1 - x0 - text_width(line1, scale)) // 2,
              y0 + 26, scale, INK)
    draw_text(line2, x0 + (x1 - x0 - text_width(line2, scale)) // 2,
              y0 + 26 + 7 * scale + 16, scale, INK)


# ---------------------------------------------------------------------------
# PNG encoder (pure stdlib, deterministic: fixed compression level, no
# timestamps anywhere in the file).
# ---------------------------------------------------------------------------
def png_bytes():
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += buf[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        return out + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    draw_sky()
    draw_paper()
    draw_pencil()
    draw_rocket()
    draw_bubble()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png_bytes())


if __name__ == "__main__":
    main()
