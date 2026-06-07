from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont


OUT_DIR = "/Users/tanmaykumar/Desktop/sourcegraph/hlb_output"
SEED = 2542027

W, H = 3508, 2480  # A4 landscape at 300dpi

FONT_ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_HAND = "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf"
FONT_COURIER = "/System/Library/Fonts/Supplemental/Courier New.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        return ImageFont.load_default()


F_TITLE = font(FONT_ARIAL_BOLD, 44)
F_HEAD = font(FONT_ARIAL_BOLD, 28)
F_META = font(FONT_ARIAL, 24)
F_SMALL = font(FONT_ARIAL, 18)
F_TINY = font(FONT_ARIAL, 14)
F_HAND_BIG = font(FONT_HAND, 42)
F_HAND = font(FONT_HAND, 30)
F_HAND_SMALL = font(FONT_HAND, 23)
F_BOX = font(FONT_ARIAL, 15)
F_BOX_SMALL = font(FONT_ARIAL, 13)
F_COURIER = font(FONT_COURIER, 20)


@dataclass
class Sheet:
    image: Image.Image
    draw: ImageDraw.ImageDraw
    rng: random.Random
    ink: tuple[int, int, int]
    faint: tuple[int, int, int]
    map_box: tuple[int, int, int, int]

    def m(self, u: float, v: float) -> tuple[float, float]:
        x0, y0, x1, y1 = self.map_box
        return (x0 + u * (x1 - x0), y0 + v * (y1 - y0))


def lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def unit(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    d = dist(a, b) or 1.0
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def normal(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    ux, uy = unit(a, b)
    return (-uy, ux)


def angle_of(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def jitter_polyline(
    s: Sheet,
    points: Sequence[tuple[float, float]],
    *,
    width: int = 3,
    jitter: float = 2.2,
    fill: tuple[int, int, int] | None = None,
    passes: int = 1,
) -> None:
    fill = fill or s.ink
    for _ in range(passes):
        jpts: list[tuple[float, float]] = []
        for i in range(len(points) - 1):
            a, b = points[i], points[i + 1]
            steps = max(2, int(dist(a, b) / 38))
            nx, ny = normal(a, b)
            for k in range(steps):
                t = k / steps
                x, y = lerp(a, b, t)
                wobble = s.rng.uniform(-jitter, jitter)
                along = s.rng.uniform(-jitter * 0.45, jitter * 0.45)
                ux, uy = unit(a, b)
                jpts.append((x + nx * wobble + ux * along, y + ny * wobble + uy * along))
        last = points[-1]
        jpts.append((last[0] + s.rng.uniform(-jitter, jitter), last[1] + s.rng.uniform(-jitter, jitter)))
        if len(jpts) > 1:
            s.draw.line(jpts, fill=fill, width=width, joint="curve")


def dashed_line(
    s: Sheet,
    a: tuple[float, float],
    b: tuple[float, float],
    *,
    dash: float = 34,
    gap: float = 18,
    width: int = 4,
    jitter: float = 2.8,
    fill: tuple[int, int, int] | None = None,
) -> None:
    fill = fill or s.ink
    d = dist(a, b)
    if d == 0:
        return
    ux, uy = unit(a, b)
    cur = 0.0
    while cur < d:
        end = min(cur + dash * s.rng.uniform(0.85, 1.15), d)
        p1 = (a[0] + ux * cur, a[1] + uy * cur)
        p2 = (a[0] + ux * end, a[1] + uy * end)
        jitter_polyline(s, [p1, p2], width=width, jitter=jitter, fill=fill)
        cur = end + gap * s.rng.uniform(0.75, 1.2)


def dashed_polyline(
    s: Sheet,
    pts: Sequence[tuple[float, float]],
    *,
    closed: bool = False,
    dash: float = 36,
    gap: float = 20,
    width: int = 4,
) -> None:
    use = list(pts)
    if closed:
        use = use + [use[0]]
    for a, b in zip(use, use[1:]):
        dashed_line(s, a, b, dash=dash, gap=gap, width=width)


def offset_polyline(points: Sequence[tuple[float, float]], offset: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for i, p in enumerate(points):
        if i == 0:
            nx, ny = normal(points[0], points[1])
        elif i == len(points) - 1:
            nx, ny = normal(points[-2], points[-1])
        else:
            n1 = normal(points[i - 1], p)
            n2 = normal(p, points[i + 1])
            nx, ny = n1[0] + n2[0], n1[1] + n2[1]
            nd = math.hypot(nx, ny) or 1.0
            nx, ny = nx / nd, ny / nd
        out.append((p[0] + nx * offset, p[1] + ny * offset))
    return out


def road(
    s: Sheet,
    pts: Sequence[tuple[float, float]],
    *,
    main: bool = False,
    lane: bool = False,
    label: str | None = None,
    label_t: float = 0.5,
) -> None:
    if main:
        for off in (-13, 13):
            jitter_polyline(s, offset_polyline(pts, off), width=4, jitter=2.0, passes=1)
        jitter_polyline(s, pts, width=1, jitter=1.4, fill=(85, 85, 82))
    else:
        jitter_polyline(s, pts, width=3 if lane else 4, jitter=2.2)
    if label:
        path_len = sum(dist(a, b) for a, b in zip(pts, pts[1:]))
        target = path_len * label_t
        acc = 0
        for a, b in zip(pts, pts[1:]):
            seg = dist(a, b)
            if acc + seg >= target:
                t = (target - acc) / max(seg, 1)
                p = lerp(a, b, t)
                ang = math.degrees(angle_of(a, b))
                draw_rotated_text(s, label, p, F_HAND_SMALL, angle=ang, fill=s.ink)
                break
            acc += seg


def polygon_outline(s: Sheet, pts: Sequence[tuple[float, float]], width: int = 3) -> None:
    jitter_polyline(s, list(pts) + [pts[0]], width=width, jitter=2.2)


def draw_arrow(
    s: Sheet,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    width: int = 3,
    bend: tuple[float, float] | None = None,
) -> None:
    pts = [start, end] if bend is None else [start, bend, end]
    jitter_polyline(s, pts, width=width, jitter=1.8)
    ang = angle_of(pts[-2], pts[-1])
    size = 20
    left = (end[0] - math.cos(ang - 0.55) * size, end[1] - math.sin(ang - 0.55) * size)
    right = (end[0] - math.cos(ang + 0.55) * size, end[1] - math.sin(ang + 0.55) * size)
    jitter_polyline(s, [left, end, right], width=width, jitter=1.1)


def draw_rotated_text(
    s: Sheet,
    text: str,
    xy: tuple[float, float],
    fnt: ImageFont.FreeTypeFont,
    *,
    angle: float = 0,
    fill: tuple[int, int, int] | None = None,
    anchor: str = "mm",
) -> None:
    fill = fill or s.ink
    bbox = s.draw.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0] + 14, bbox[3] - bbox[1] + 12
    tile = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
    td = ImageDraw.Draw(tile)
    td.text((tw // 2, th // 2), text, font=fnt, fill=fill + (255,), anchor="mm")
    rot = tile.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)
    if anchor == "mm":
        pos = (int(xy[0] - rot.width / 2), int(xy[1] - rot.height / 2))
    else:
        pos = (int(xy[0]), int(xy[1]))
    s.image.paste(rot, pos, rot)


def house(
    s: Sheet,
    cx: float,
    cy: float,
    *,
    num: int | None = None,
    w: float = 34,
    h: float = 27,
    angle: float = 0,
    hatch: bool = False,
    filled: bool = False,
) -> None:
    ca, sa = math.cos(angle), math.sin(angle)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    pts: list[tuple[float, float]] = []
    for x, y in corners:
        pts.append(
            (
                cx + x * ca - y * sa + s.rng.uniform(-1.5, 1.5),
                cy + x * sa + y * ca + s.rng.uniform(-1.5, 1.5),
            )
        )
    if filled:
        s.draw.polygon(pts, fill=(38, 38, 36))
    polygon_outline(s, pts, width=2)
    if hatch:
        for i in range(3):
            t = -0.35 + i * 0.35
            p1 = (cx + (-w / 2 + i * 8) * ca - (-h / 2) * sa, cy + (-w / 2 + i * 8) * sa + (-h / 2) * ca)
            p2 = (cx + (w / 2) * ca - (h / 2 + t * h) * sa, cy + (w / 2) * sa + (h / 2 + t * h) * ca)
            jitter_polyline(s, [p1, p2], width=1, jitter=0.7)
    if num is not None and not filled:
        txt = str(num)
        f = F_BOX_SMALL if len(txt) > 2 else F_BOX
        s.draw.text((cx, cy - 1), txt, font=f, fill=s.ink, anchor="mm")


def row_houses(
    s: Sheet,
    a: tuple[float, float],
    b: tuple[float, float],
    n: int,
    *,
    side: float,
    offset: float,
    start_no: int,
    t0: float = 0.08,
    t1: float = 0.92,
    size: tuple[float, float] = (34, 27),
    skip: set[int] | None = None,
) -> int:
    skip = skip or set()
    nx, ny = normal(a, b)
    ang = angle_of(a, b)
    cur = start_no
    for i in range(n):
        if i in skip:
            continue
        t = t0 + (t1 - t0) * (i / max(n - 1, 1))
        x, y = lerp(a, b, t)
        cx = x + nx * offset * side + s.rng.uniform(-7, 7)
        cy = y + ny * offset * side + s.rng.uniform(-7, 7)
        house(s, cx, cy, num=cur, w=size[0] + s.rng.uniform(-4, 5), h=size[1] + s.rng.uniform(-3, 4), angle=ang + s.rng.uniform(-0.06, 0.06))
        cur += 1
    return cur


def block_houses(
    s: Sheet,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    rows: int,
    cols: int,
    *,
    start_no: int,
    jitter: float = 8,
    empty: set[tuple[int, int]] | None = None,
) -> int:
    empty = empty or set()
    cur = start_no
    for r in range(rows):
        for c in range(cols):
            if (r, c) in empty:
                continue
            x = x0 + (x1 - x0) * (c + 0.5) / cols + s.rng.uniform(-jitter, jitter)
            y = y0 + (y1 - y0) * (r + 0.5) / rows + s.rng.uniform(-jitter, jitter)
            house(s, x, y, num=cur, w=s.rng.uniform(27, 38), h=s.rng.uniform(23, 31), angle=s.rng.uniform(-0.08, 0.08))
            cur += 1
    return cur


def field_hatch(s: Sheet, pts: Sequence[tuple[float, float]], *, label: str | None = None, density: int = 12) -> None:
    s.draw.polygon(pts, fill=None)
    polygon_outline(s, pts, width=2)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    for i in range(density):
        y = y0 + (y1 - y0) * (i + 0.5) / density + s.rng.uniform(-8, 8)
        a = (x0 + s.rng.uniform(20, 55), y)
        b = (x1 - s.rng.uniform(20, 55), y + s.rng.uniform(-7, 7))
        jitter_polyline(s, [a, b], width=1, jitter=1.2, fill=(90, 90, 88))
    if label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        draw_rotated_text(s, label, (cx, cy), F_HAND, angle=s.rng.uniform(-4, 4), fill=s.ink)


def tree_symbol(s: Sheet, x: float, y: float, scale: float = 1.0) -> None:
    r = 10 * scale
    for dx, dy in [(-7, 0), (0, -8), (8, 0)]:
        s.draw.ellipse((x + dx - r, y + dy - r, x + dx + r, y + dy + r), outline=s.ink, width=2)
    jitter_polyline(s, [(x, y + 8 * scale), (x, y + 28 * scale)], width=2, jitter=0.8)


def landmark_triangle(s: Sheet, x: float, y: float, *, filled: bool = False) -> None:
    pts = [(x, y - 22), (x - 19, y + 15), (x + 19, y + 15)]
    if filled:
        s.draw.polygon(pts, fill=s.ink)
    polygon_outline(s, pts, width=2)


def pond_or_drain(s: Sheet, pts: Sequence[tuple[float, float]], *, label: str | None = None) -> None:
    jitter_polyline(s, pts, width=3, jitter=2.5)
    off = offset_polyline(pts, 18)
    jitter_polyline(s, off, width=2, jitter=2.2, fill=(65, 65, 64))
    if label:
        mid = pts[len(pts) // 2]
        draw_rotated_text(s, label, (mid[0] + 50, mid[1] - 10), F_HAND_SMALL, angle=-12)


def point_in_poly(x: float, y: float, pts: Sequence[tuple[float, float]]) -> bool:
    inside = False
    j = len(pts) - 1
    for i, p in enumerate(pts):
        xi, yi = p
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / ((yj - yi) or 1e-6) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def compound_wall(
    s: Sheet,
    pts: Sequence[tuple[float, float]],
    *,
    label: str | None = None,
    width: int = 2,
    faint: bool = False,
) -> None:
    fill = s.faint if faint else s.ink
    jitter_polyline(s, list(pts) + [pts[0]], width=width, jitter=1.5, fill=fill)
    for a, b in zip(pts, list(pts[1:]) + [pts[0]]):
        if dist(a, b) < 70:
            continue
        mid = lerp(a, b, 0.5)
        nx, ny = normal(a, b)
        tick1 = (mid[0] - nx * 10, mid[1] - ny * 10)
        tick2 = (mid[0] + nx * 10, mid[1] + ny * 10)
        jitter_polyline(s, [tick1, tick2], width=1, jitter=0.6, fill=fill)
    if label:
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        draw_rotated_text(s, label, (cx, cy), F_HAND_SMALL, angle=s.rng.uniform(-5, 5), fill=fill)


def yard_texture(
    s: Sheet,
    pts: Sequence[tuple[float, float]],
    *,
    count: int,
    label: str | None = None,
    dark: bool = False,
) -> None:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    fill = (48, 48, 46) if dark else s.faint
    attempts = 0
    drawn = 0
    while drawn < count and attempts < count * 12:
        attempts += 1
        x = s.rng.uniform(x0, x1)
        y = s.rng.uniform(y0, y1)
        if not point_in_poly(x, y, pts):
            continue
        kind = s.rng.randrange(4)
        if kind == 0:
            s.draw.ellipse((x - 2, y - 2, x + 2, y + 2), outline=fill, width=1)
        elif kind == 1:
            ang = s.rng.uniform(-1.1, 1.1)
            ln = s.rng.uniform(8, 22)
            jitter_polyline(
                s,
                [(x - math.cos(ang) * ln / 2, y - math.sin(ang) * ln / 2), (x + math.cos(ang) * ln / 2, y + math.sin(ang) * ln / 2)],
                width=1,
                jitter=0.5,
                fill=fill,
            )
        elif kind == 2:
            house(s, x, y, num=None, w=s.rng.uniform(10, 20), h=s.rng.uniform(7, 14), angle=s.rng.uniform(-0.6, 0.6), hatch=s.rng.random() < 0.35)
        else:
            s.draw.arc((x - 8, y - 5, x + 8, y + 6), start=s.rng.randrange(0, 180), end=s.rng.randrange(181, 360), fill=fill, width=1)
        drawn += 1
    if label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        draw_rotated_text(s, label, (cx, cy), F_HAND_SMALL, angle=s.rng.uniform(-7, 7), fill=fill)


def field_detail_lines(s: Sheet, pts: Sequence[tuple[float, float]], *, count: int, vertical: bool = False) -> None:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    for i in range(count):
        t = (i + 1) / (count + 1)
        if vertical:
            x = x0 + (x1 - x0) * t + s.rng.uniform(-10, 10)
            a = (x, y0 + s.rng.uniform(12, 35))
            b = (x + s.rng.uniform(-18, 18), y1 - s.rng.uniform(12, 35))
        else:
            y = y0 + (y1 - y0) * t + s.rng.uniform(-9, 9)
            a = (x0 + s.rng.uniform(12, 45), y)
            b = (x1 - s.rng.uniform(12, 45), y + s.rng.uniform(-12, 12))
        jitter_polyline(s, [a, b], width=1, jitter=1.0, fill=s.faint)


def well_symbol(s: Sheet, x: float, y: float, *, label: str | None = None) -> None:
    s.draw.ellipse((x - 13, y - 13, x + 13, y + 13), outline=s.ink, width=2)
    s.draw.ellipse((x - 6, y - 6, x + 6, y + 6), outline=s.faint, width=1)
    jitter_polyline(s, [(x - 20, y + 18), (x + 20, y + 18)], width=1, jitter=0.8, fill=s.faint)
    if label:
        s.draw.text((x + 22, y - 10), label, font=F_HAND_SMALL, fill=s.ink)


def culvert_symbol(s: Sheet, x: float, y: float, angle: float = 0) -> None:
    ca, sa = math.cos(angle), math.sin(angle)
    for off in (-8, 8):
        a = (x - ca * 26 - sa * off, y - sa * 26 + ca * off)
        b = (x + ca * 26 - sa * off, y + sa * 26 + ca * off)
        jitter_polyline(s, [a, b], width=1, jitter=0.5, fill=s.ink)


def tree_line(
    s: Sheet,
    pts: Sequence[tuple[float, float]],
    *,
    count: int,
    scale: float = 0.55,
) -> None:
    if len(pts) < 2:
        return
    lengths = [dist(a, b) for a, b in zip(pts, pts[1:])]
    total = sum(lengths) or 1
    for i in range(count):
        target = total * ((i + 0.5) / count)
        acc = 0.0
        for seg_i, (a, b) in enumerate(zip(pts, pts[1:])):
            seg = lengths[seg_i]
            if acc + seg >= target:
                t = (target - acc) / max(seg, 1)
                x, y = lerp(a, b, t)
                nx, ny = normal(a, b)
                tree_symbol(s, x + nx * s.rng.uniform(-12, 12), y + ny * s.rng.uniform(-12, 12), scale=s.rng.uniform(scale * 0.85, scale * 1.2))
                break
            acc += seg


def meta_line(s: Sheet, x: int, y: int, label: str, value: str, box_digits: int | None = None) -> int:
    s.draw.text((x, y), label, font=F_META, fill=s.ink)
    lx = x + 230
    s.draw.line((lx, y + 27, 600, y + 27), fill=s.faint, width=2)
    if value:
        s.draw.text((lx + 5, y - 2), value, font=F_META, fill=s.ink)
    if box_digits:
        bx = 520 - box_digits * 33
        by = y - 4
        for i in range(box_digits):
            s.draw.rectangle((bx + i * 33, by, bx + (i + 1) * 33, by + 32), outline=s.ink, width=2)
        txt = value.replace(" ", "")[-box_digits:].rjust(box_digits, "0")
        for i, ch in enumerate(txt):
            s.draw.text((bx + i * 33 + 16, by + 16), ch, font=F_SMALL, fill=s.ink, anchor="mm")
    return y + 58


def draw_legend(s: Sheet, x: int, y: int) -> None:
    s.draw.text((x, y), "LEGEND", font=F_HEAD, fill=s.ink)
    y += 50
    s.draw.text((x, y), "HLB boundary", font=F_SMALL, fill=s.ink)
    dashed_line(s, (x + 260, y + 13), (x + 430, y + 13), dash=28, gap=14, width=4)
    y += 45
    s.draw.text((x, y), "Main road / lane", font=F_SMALL, fill=s.ink)
    road(s, [(x + 260, y + 10), (x + 430, y + 10)], main=True)
    y += 48
    s.draw.text((x, y), "House / census house", font=F_SMALL, fill=s.ink)
    house(s, x + 330, y + 14, num=1, w=34, h=28)
    y += 48
    s.draw.text((x, y), "Landmark", font=F_SMALL, fill=s.ink)
    landmark_triangle(s, x + 332, y + 15, filled=False)
    y += 48
    s.draw.text((x, y), "Open field", font=F_SMALL, fill=s.ink)
    field_hatch(s, [(x + 270, y + 0), (x + 430, y - 2), (x + 430, y + 36), (x + 270, y + 35)], density=4)
    y += 60
    s.draw.text((x, y), "Enumerator movement", font=F_SMALL, fill=s.ink)
    draw_arrow(s, (x + 275, y + 15), (x + 425, y + 15), width=2)


def draw_sheet_frame(s: Sheet, *, textured: bool) -> None:
    # Page frame and title block, kept intentionally sparse like a field sheet.
    s.draw.rectangle((70, 65, W - 70, H - 72), outline=s.ink, width=3)
    s.draw.text((90, 88), "CENSUS OF INDIA 2027", font=F_TITLE, fill=s.ink)
    s.draw.text((W // 2, 88), "Layout Map", font=F_TITLE, fill=s.ink, anchor="ma")
    s.draw.text((W - 90, 94), "Houselisting & Housing Census", font=F_HEAD, fill=s.ink, anchor="ra")

    panel = (90, 140, 650, H - 110)
    map_box = s.map_box
    s.draw.rectangle(panel, outline=s.ink, width=3)
    s.draw.rectangle(map_box, outline=s.ink, width=3)

    y = 185
    y = meta_line(s, 110, y, "Name of State/UT", "Rajasthan")
    y = meta_line(s, 110, y, "Code No.", "09", box_digits=2)
    y = meta_line(s, 110, y, "Name of District", "Khairthal-Tijara")
    y = meta_line(s, 110, y, "Code No.", "15", box_digits=2)
    y = meta_line(s, 110, y, "Sub-District", "Tapukara")
    y = meta_line(s, 110, y, "Code No.", "004", box_digits=3)
    y = meta_line(s, 110, y, "Town/Village", "Bhiwadi")
    y = meta_line(s, 110, y, "Town/Village Code", "7121", box_digits=4)
    y = meta_line(s, 110, y, "Ward No.", "0060", box_digits=4)
    y = meta_line(s, 110, y, "HLB No.", "0254", box_digits=4)

    draw_legend(s, 110, y + 35)
    s.draw.text((110, H - 390), "Note: Numbers shown in houses are", font=F_SMALL, fill=s.ink)
    s.draw.text((110, H - 360), "symbolic census house sequence.", font=F_SMALL, fill=s.ink)
    s.draw.text((110, H - 260), "Created from satellite layout:", font=F_SMALL, fill=s.ink)
    s.draw.text((110, H - 230), "HLB_Map_0254", font=F_COURIER, fill=s.ink)
    s.draw.text((110, H - 190), "Prepared for field verification", font=F_SMALL, fill=s.ink)
    if textured:
        s.draw.text((110, H - 150), "Draft: hand sketch style", font=F_SMALL, fill=s.faint)


def draw_north_arrow(s: Sheet) -> None:
    x, y = s.m(0.965, 0.06)
    s.draw.text((x, y - 62), "N", font=F_HEAD, fill=s.ink, anchor="mm")
    pts = [(x, y - 35), (x - 28, y + 55), (x, y + 28), (x + 28, y + 55)]
    polygon_outline(s, pts, width=3)
    s.draw.line((x, y - 35, x, y + 72), fill=s.ink, width=2)


def draw_boundary_and_context(s: Sheet) -> list[tuple[float, float]]:
    boundary = [
        s.m(0.105, 0.775),
        s.m(0.100, 0.575),
        s.m(0.075, 0.440),
        s.m(0.115, 0.345),
        s.m(0.185, 0.305),
        s.m(0.295, 0.170),
        s.m(0.385, 0.055),
        s.m(0.455, 0.085),
        s.m(0.480, 0.045),
        s.m(0.555, 0.125),
        s.m(0.645, 0.130),
        s.m(0.735, 0.205),
        s.m(0.820, 0.255),
        s.m(0.885, 0.295),
        s.m(0.925, 0.238),
        s.m(0.985, 0.292),
        s.m(0.940, 0.470),
        s.m(0.895, 0.610),
        s.m(0.855, 0.790),
        s.m(0.820, 0.940),
        s.m(0.650, 0.915),
        s.m(0.462, 0.885),
        s.m(0.285, 0.862),
        s.m(0.105, 0.775),
    ]
    dashed_polyline(s, boundary, closed=False, dash=36, gap=19, width=5)

    # Outer / adjacent features copied schematically from the source sheet.
    dashed_line(s, s.m(0.01, 0.36), s.m(0.98, 0.28), dash=28, gap=18, width=3, fill=(85, 85, 83))
    draw_rotated_text(s, "HARYANA / RAJASTHAN", s.m(0.45, 0.145), F_HAND_SMALL, angle=-44)
    draw_rotated_text(s, "HARYANA / RAJASTHAN", s.m(0.755, 0.247), F_HAND_SMALL, angle=22)

    s.draw.text(s.m(0.18, 0.24), "0353", font=F_HEAD, fill=s.faint, anchor="mm")
    s.draw.text(s.m(0.83, 0.20), "0354", font=F_HEAD, fill=s.faint, anchor="mm")
    s.draw.text(s.m(0.985, 0.66), "0253", font=F_HEAD, fill=s.faint, anchor="rm")
    s.draw.text(s.m(0.36, 0.945), "0240", font=F_HEAD, fill=s.faint, anchor="mm")
    s.draw.text(s.m(0.055, 0.61), "0241", font=F_HEAD, fill=s.faint, anchor="mm")
    draw_rotated_text(s, "Jaursi - Bhiwadi Rd.", s.m(0.90, 0.105), F_HAND_SMALL, angle=2, fill=s.faint)
    draw_rotated_text(s, "Road to Tapukara", s.m(0.075, 0.49), F_HAND_SMALL, angle=80, fill=s.faint)
    return boundary


def draw_open_spaces(s: Sheet) -> None:
    north_field = [s.m(0.635, 0.185), s.m(0.858, 0.270), s.m(0.845, 0.465), s.m(0.622, 0.455)]
    field_hatch(
        s,
        north_field,
        label="Open Field / Khet",
        density=12,
    )
    field_detail_lines(s, north_field, count=5, vertical=True)
    compound_wall(s, [s.m(0.650, 0.202), s.m(0.845, 0.275), s.m(0.835, 0.445), s.m(0.640, 0.430)], faint=True)

    east_field = [s.m(0.825, 0.505), s.m(0.915, 0.540), s.m(0.855, 0.765), s.m(0.770, 0.730)]
    field_hatch(
        s,
        east_field,
        label="Field",
        density=10,
    )
    field_detail_lines(s, east_field, count=4, vertical=True)

    southwest_plot = [s.m(0.135, 0.645), s.m(0.305, 0.655), s.m(0.285, 0.805), s.m(0.115, 0.770)]
    field_hatch(
        s,
        southwest_plot,
        label="Open Plot",
        density=9,
    )
    field_detail_lines(s, southwest_plot, count=3, vertical=True)

    # Central grove/open green patch from the satellite image.
    grove = [s.m(0.430, 0.455), s.m(0.545, 0.450), s.m(0.595, 0.545), s.m(0.520, 0.605), s.m(0.415, 0.570)]
    polygon_outline(s, grove, width=2)
    s.draw.text(s.m(0.502, 0.525), "Grove", font=F_HAND_SMALL, fill=s.ink, anchor="mm")
    for u, v, sc in [(0.455, 0.490, 0.8), (0.510, 0.480, 0.7), (0.555, 0.535, 0.85), (0.475, 0.555, 0.65), (0.535, 0.575, 0.55), (0.435, 0.535, 0.55)]:
        tree_symbol(s, *s.m(u, v), scale=sc)
    tree_line(s, [s.m(0.425, 0.455), s.m(0.520, 0.445), s.m(0.590, 0.525)], count=7, scale=0.45)

    # Yard textures follow the visible scrap/open storage patches in the satellite image.
    nw_yard = [s.m(0.155, 0.315), s.m(0.315, 0.310), s.m(0.328, 0.455), s.m(0.150, 0.470)]
    compound_wall(s, nw_yard, label="transport yard", faint=True)
    yard_texture(s, nw_yard, count=55)

    north_scrap = [s.m(0.360, 0.145), s.m(0.510, 0.170), s.m(0.505, 0.305), s.m(0.348, 0.300)]
    compound_wall(s, north_scrap, faint=True)
    yard_texture(s, north_scrap, count=70, label="scrap/open plot")

    central_scrap = [s.m(0.500, 0.555), s.m(0.665, 0.555), s.m(0.688, 0.690), s.m(0.570, 0.730), s.m(0.485, 0.635)]
    compound_wall(s, central_scrap, faint=True)
    yard_texture(s, central_scrap, count=95, label="scrap / vacant", dark=True)

    se_scrap = [s.m(0.690, 0.650), s.m(0.812, 0.705), s.m(0.820, 0.835), s.m(0.735, 0.805)]
    compound_wall(s, se_scrap, faint=True)
    yard_texture(s, se_scrap, count=45)

    pond_or_drain(s, [s.m(0.920, 0.335), s.m(0.900, 0.455), s.m(0.885, 0.575), s.m(0.858, 0.730)], label="drain")
    pond_or_drain(s, [s.m(0.592, 0.572), s.m(0.655, 0.590), s.m(0.730, 0.620), s.m(0.795, 0.705)], label=None)


def draw_roads(s: Sheet) -> dict[str, list[tuple[float, float]]]:
    roads: dict[str, list[tuple[float, float]]] = {}
    roads["main_ns"] = [s.m(0.380, 0.055), s.m(0.355, 0.175), s.m(0.342, 0.325), s.m(0.350, 0.500), s.m(0.392, 0.635), s.m(0.405, 0.875)]
    roads["main_ew"] = [s.m(0.098, 0.535), s.m(0.220, 0.520), s.m(0.360, 0.540), s.m(0.515, 0.548), s.m(0.680, 0.520), s.m(0.870, 0.505)]
    roads["north_lane"] = [s.m(0.355, 0.210), s.m(0.505, 0.205), s.m(0.635, 0.225), s.m(0.720, 0.265)]
    roads["north_yard_lane"] = [s.m(0.335, 0.155), s.m(0.435, 0.155), s.m(0.515, 0.180)]
    roads["north_yard_cross"] = [s.m(0.430, 0.115), s.m(0.430, 0.205), s.m(0.425, 0.300)]
    roads["north_field_track"] = [s.m(0.630, 0.305), s.m(0.735, 0.315), s.m(0.850, 0.310)]
    roads["west_grid_1"] = [s.m(0.145, 0.335), s.m(0.295, 0.330), s.m(0.345, 0.330)]
    roads["west_grid_2"] = [s.m(0.160, 0.430), s.m(0.335, 0.438)]
    roads["west_inner_lane"] = [s.m(0.125, 0.585), s.m(0.205, 0.585), s.m(0.255, 0.615)]
    roads["west_compound_lane"] = [s.m(0.130, 0.395), s.m(0.215, 0.395), s.m(0.300, 0.405)]
    roads["southwest_lane"] = [s.m(0.220, 0.530), s.m(0.245, 0.655), s.m(0.205, 0.775)]
    roads["southwest_plot_edge"] = [s.m(0.115, 0.790), s.m(0.205, 0.805), s.m(0.300, 0.825)]
    roads["central_branch"] = [s.m(0.390, 0.560), s.m(0.505, 0.660), s.m(0.650, 0.660)]
    roads["central_scrap_track"] = [s.m(0.440, 0.585), s.m(0.535, 0.610), s.m(0.675, 0.590)]
    roads["central_north_foot"] = [s.m(0.500, 0.545), s.m(0.555, 0.500), s.m(0.620, 0.505)]
    roads["central_down"] = [s.m(0.545, 0.548), s.m(0.552, 0.710), s.m(0.570, 0.850)]
    roads["central_west_foot"] = [s.m(0.475, 0.545), s.m(0.445, 0.650), s.m(0.445, 0.870)]
    roads["se_branch"] = [s.m(0.685, 0.520), s.m(0.705, 0.662), s.m(0.755, 0.805), s.m(0.812, 0.910)]
    roads["east_cluster_lane"] = [s.m(0.720, 0.535), s.m(0.795, 0.600), s.m(0.825, 0.705)]
    roads["east_back_lane"] = [s.m(0.805, 0.520), s.m(0.825, 0.630), s.m(0.825, 0.790)]
    roads["east_edge_lane"] = [s.m(0.860, 0.500), s.m(0.830, 0.630), s.m(0.805, 0.785), s.m(0.780, 0.940)]
    roads["bottom_lane"] = [s.m(0.140, 0.775), s.m(0.310, 0.835), s.m(0.455, 0.855), s.m(0.640, 0.900), s.m(0.790, 0.930)]
    roads["fouji_inner"] = [s.m(0.635, 0.725), s.m(0.735, 0.745), s.m(0.810, 0.830)]
    roads["fouji_exit"] = [s.m(0.775, 0.780), s.m(0.790, 0.870), s.m(0.820, 0.940)]

    road(s, roads["main_ns"], main=True, label="main village road", label_t=0.28)
    road(s, roads["main_ew"], main=True, label="approach road", label_t=0.68)
    for key in [
        "north_lane",
        "north_yard_lane",
        "north_yard_cross",
        "north_field_track",
        "west_grid_1",
        "west_grid_2",
        "west_inner_lane",
        "west_compound_lane",
        "southwest_lane",
        "southwest_plot_edge",
        "central_branch",
        "central_scrap_track",
        "central_north_foot",
        "central_down",
        "central_west_foot",
        "se_branch",
        "east_cluster_lane",
        "east_back_lane",
        "east_edge_lane",
        "bottom_lane",
        "fouji_inner",
        "fouji_exit",
    ]:
        road(s, roads[key], lane=True)
    for x, y, ang in [
        (*s.m(0.350, 0.538), -0.02),
        (*s.m(0.612, 0.525), -0.08),
        (*s.m(0.865, 0.508), 0.02),
        (*s.m(0.807, 0.855), 1.25),
    ]:
        culvert_symbol(s, x, y, angle=ang)

    # A few internal block dividing lines, like the dummy reference.
    for pts in [
        [s.m(0.260, 0.330), s.m(0.260, 0.520)],
        [s.m(0.300, 0.220), s.m(0.300, 0.440)],
        [s.m(0.350, 0.155), s.m(0.500, 0.155)],
        [s.m(0.395, 0.155), s.m(0.392, 0.305)],
        [s.m(0.470, 0.205), s.m(0.465, 0.455)],
        [s.m(0.548, 0.205), s.m(0.548, 0.455)],
        [s.m(0.620, 0.300), s.m(0.615, 0.520)],
        [s.m(0.485, 0.660), s.m(0.485, 0.870)],
        [s.m(0.570, 0.565), s.m(0.570, 0.705)],
        [s.m(0.675, 0.620), s.m(0.805, 0.610)],
        [s.m(0.650, 0.785), s.m(0.805, 0.795)],
        [s.m(0.760, 0.510), s.m(0.760, 0.735)],
        [s.m(0.835, 0.500), s.m(0.850, 0.710)],
    ]:
        jitter_polyline(s, pts, width=3, jitter=1.8)

    return roads


def draw_houses(s: Sheet, roads: dict[str, list[tuple[float, float]]]) -> None:
    n = 1
    # NW dense settlement along the north-south road.
    n = row_houses(s, roads["main_ns"][0], roads["main_ns"][3], 9, side=-1, offset=55, start_no=n, t0=0.12, t1=0.88)
    n = row_houses(s, roads["main_ns"][1], roads["main_ns"][3], 8, side=1, offset=58, start_no=n, t0=0.08, t1=0.95)
    n = row_houses(s, roads["north_lane"][0], roads["north_lane"][-1], 9, side=-1, offset=44, start_no=n, t0=0.08, t1=0.82)
    n = row_houses(s, roads["west_grid_1"][0], roads["west_grid_1"][-1], 7, side=-1, offset=44, start_no=n)
    n = row_houses(s, roads["west_grid_2"][0], roads["west_grid_2"][-1], 6, side=1, offset=42, start_no=n)
    n = block_houses(s, *s.m(0.185, 0.360), *s.m(0.315, 0.495), 3, 4, start_no=n, empty={(1, 1)})
    n = row_houses(s, roads["north_yard_lane"][0], roads["north_yard_lane"][-1], 6, side=-1, offset=38, start_no=n, t0=0.08, t1=0.86, size=(29, 23))
    n = row_houses(s, roads["north_yard_cross"][0], roads["north_yard_cross"][-1], 5, side=1, offset=36, start_no=n, t0=0.08, t1=0.90, size=(28, 22))
    n = row_houses(s, roads["north_field_track"][0], roads["north_field_track"][-1], 4, side=-1, offset=34, start_no=n, t0=0.18, t1=0.82, size=(28, 22))
    n = row_houses(s, roads["west_compound_lane"][0], roads["west_compound_lane"][-1], 5, side=-1, offset=35, start_no=n, t0=0.10, t1=0.88, size=(28, 22))

    # Houses facing the main east-west approach road.
    n = row_houses(s, roads["main_ew"][0], roads["main_ew"][-1], 18, side=-1, offset=48, start_no=n, t0=0.08, t1=0.92, skip={7, 8, 14})
    n = row_houses(s, roads["main_ew"][0], roads["main_ew"][-1], 19, side=1, offset=54, start_no=n, t0=0.05, t1=0.94, skip={4, 11})

    # South-west sparse settlement and edge houses.
    n = row_houses(s, roads["west_inner_lane"][0], roads["west_inner_lane"][-1], 5, side=-1, offset=36, start_no=n, t0=0.10, t1=0.90, size=(28, 22))
    n = row_houses(s, roads["southwest_lane"][0], roads["southwest_lane"][-1], 7, side=-1, offset=45, start_no=n)
    n = row_houses(s, roads["southwest_plot_edge"][0], roads["southwest_plot_edge"][-1], 3, side=-1, offset=34, start_no=n, t0=0.14, t1=0.80, size=(28, 22))
    n = row_houses(s, roads["bottom_lane"][0], roads["bottom_lane"][2], 8, side=-1, offset=48, start_no=n, t0=0.05, t1=0.85)
    n = block_houses(s, *s.m(0.305, 0.670), *s.m(0.430, 0.835), 3, 3, start_no=n, empty={(0, 2)})

    # Central compact cluster near grove / Rampura side.
    n = row_houses(s, roads["central_branch"][0], roads["central_branch"][-1], 8, side=-1, offset=45, start_no=n)
    n = row_houses(s, roads["central_branch"][0], roads["central_branch"][-1], 8, side=1, offset=45, start_no=n, skip={4})
    n = row_houses(s, roads["central_down"][0], roads["central_down"][-1], 7, side=-1, offset=48, start_no=n, t0=0.10, t1=0.88)
    n = row_houses(s, roads["central_down"][0], roads["central_down"][-1], 6, side=1, offset=48, start_no=n, t0=0.10, t1=0.78)
    n = block_houses(s, *s.m(0.585, 0.580), *s.m(0.675, 0.730), 3, 3, start_no=n, empty={(2, 0)})
    n = row_houses(s, roads["central_scrap_track"][0], roads["central_scrap_track"][-1], 6, side=1, offset=34, start_no=n, t0=0.08, t1=0.88, size=(28, 22))
    n = row_houses(s, roads["central_north_foot"][0], roads["central_north_foot"][-1], 5, side=-1, offset=32, start_no=n, t0=0.05, t1=0.90, size=(27, 21), skip={2})
    n = row_houses(s, roads["central_west_foot"][0], roads["central_west_foot"][-1], 5, side=1, offset=34, start_no=n, t0=0.08, t1=0.86, size=(28, 22))

    # South-east / Fouji colony cluster.
    n = row_houses(s, roads["se_branch"][0], roads["se_branch"][-1], 10, side=-1, offset=46, start_no=n, t0=0.08, t1=0.88)
    n = row_houses(s, roads["se_branch"][1], roads["se_branch"][-1], 9, side=1, offset=48, start_no=n, t0=0.02, t1=0.90)
    n = row_houses(s, roads["east_cluster_lane"][0], roads["east_cluster_lane"][-1], 5, side=-1, offset=34, start_no=n, t0=0.10, t1=0.86, size=(28, 22))
    n = row_houses(s, roads["east_back_lane"][0], roads["east_back_lane"][-1], 4, side=1, offset=32, start_no=n, t0=0.10, t1=0.80, size=(27, 21))
    n = row_houses(s, roads["east_edge_lane"][0], roads["east_edge_lane"][-1], 8, side=1, offset=42, start_no=n, t0=0.20, t1=0.90)
    n = row_houses(s, roads["fouji_inner"][0], roads["fouji_inner"][-1], 7, side=-1, offset=42, start_no=n, t0=0.10, t1=0.88)
    n = row_houses(s, roads["fouji_exit"][0], roads["fouji_exit"][-1], 6, side=-1, offset=32, start_no=n, t0=0.05, t1=0.86, size=(27, 21))
    n = row_houses(s, roads["bottom_lane"][2], roads["bottom_lane"][-1], 9, side=-1, offset=45, start_no=n, t0=0.04, t1=0.88)

    # Scattered houses from the satellite-like irregular inner area.
    scatter = [
        (0.455, 0.705), (0.535, 0.760), (0.585, 0.835), (0.645, 0.842),
        (0.695, 0.865), (0.735, 0.888), (0.785, 0.900), (0.805, 0.835),
        (0.825, 0.775), (0.800, 0.725), (0.765, 0.820), (0.742, 0.925),
    ]
    for u, v in scatter:
        x, y = s.m(u, v)
        house(s, x + s.rng.uniform(-10, 10), y + s.rng.uniform(-8, 8), num=n, w=s.rng.uniform(28, 38), h=s.rng.uniform(23, 31), angle=s.rng.uniform(-0.1, 0.1))
        n += 1

    # Unnumbered sheds, courtyard marks, wells and small service structures add
    # satellite-derived detail without changing the census house sequence.
    for u, v, ang, hatch in [
        (0.172, 0.375, -0.06, True), (0.212, 0.352, 0.08, False), (0.282, 0.405, 0.03, True),
        (0.365, 0.178, -0.05, True), (0.455, 0.270, 0.04, False), (0.495, 0.570, 0.20, True),
        (0.615, 0.620, -0.10, True), (0.650, 0.685, 0.03, False), (0.735, 0.650, -0.45, True),
        (0.790, 0.745, 0.22, False), (0.815, 0.825, -0.10, True), (0.255, 0.735, -0.20, False),
    ]:
        x, y = s.m(u, v)
        house(s, x, y, num=None, w=s.rng.uniform(21, 31), h=s.rng.uniform(16, 24), angle=ang + s.rng.uniform(-0.08, 0.08), hatch=hatch)
    for u, v, lbl in [(0.555, 0.640, "well"), (0.750, 0.755, None), (0.235, 0.458, None)]:
        well_symbol(s, *s.m(u, v), label=lbl)

    # Non-residential symbols / landmark boxes.
    for u, v, txt in [(0.130, 0.410, "N.S. Transport"), (0.120, 0.525, "Aata Chakki"), (0.758, 0.500, "Rampura Aas")]:
        x, y = s.m(u, v)
        landmark_triangle(s, x, y, filled=False)
        s.draw.text((x + 26, y - 8), txt, font=F_HAND_SMALL, fill=s.ink)

    x, y = s.m(0.815, 0.835)
    landmark_triangle(s, x, y, filled=True)
    s.draw.text((x + 32, y - 8), "Fouji Colony", font=F_HAND_SMALL, fill=s.ink)

    # A few hatched house-like special symbols visible in census legend style.
    house(s, *s.m(0.240, 0.490), num=None, w=40, h=32, hatch=True)
    house(s, *s.m(0.705, 0.618), num=None, w=40, h=32, hatch=True)


def draw_enumerator_flow(s: Sheet) -> None:
    flow = [
        (s.m(0.370, 0.110), s.m(0.348, 0.305), None),
        (s.m(0.140, 0.532), s.m(0.335, 0.536), None),
        (s.m(0.390, 0.545), s.m(0.620, 0.535), s.m(0.505, 0.500)),
        (s.m(0.395, 0.600), s.m(0.505, 0.660), None),
        (s.m(0.552, 0.675), s.m(0.565, 0.820), None),
        (s.m(0.690, 0.555), s.m(0.750, 0.800), None),
        (s.m(0.760, 0.805), s.m(0.820, 0.915), None),
        (s.m(0.310, 0.835), s.m(0.160, 0.780), None),
        (s.m(0.275, 0.335), s.m(0.160, 0.345), None),
        (s.m(0.640, 0.230), s.m(0.720, 0.265), None),
        (s.m(0.350, 0.155), s.m(0.500, 0.185), s.m(0.430, 0.120)),
        (s.m(0.170, 0.395), s.m(0.305, 0.410), None),
        (s.m(0.500, 0.585), s.m(0.665, 0.590), s.m(0.580, 0.555)),
        (s.m(0.720, 0.545), s.m(0.820, 0.695), None),
        (s.m(0.780, 0.790), s.m(0.815, 0.930), None),
    ]
    for start, end, bend in flow:
        draw_arrow(s, start, end, width=2, bend=bend)
    s.draw.text(s.m(0.330, 0.085), "Entry", font=F_HAND_SMALL, fill=s.ink, anchor="mm")
    s.draw.text(s.m(0.790, 0.945), "Exit", font=F_HAND_SMALL, fill=s.ink, anchor="mm")


def add_hand_notes(s: Sheet) -> None:
    s.draw.text(s.m(0.510, 0.515), "HLB No. 0254", font=F_HAND_BIG, fill=s.ink, anchor="mm")
    s.draw.text(s.m(0.500, 0.955), "Village/Town: Bhiwadi   Ward: 0060", font=F_HAND, fill=s.ink, anchor="mm")
    s.draw.text(s.m(0.090, 0.310), "to Haryana side", font=F_HAND_SMALL, fill=s.faint, anchor="mm")
    s.draw.text(s.m(0.920, 0.835), "to 0253", font=F_HAND_SMALL, fill=s.faint, anchor="mm")
    draw_rotated_text(s, "kachcha lane", s.m(0.410, 0.175), F_HAND_SMALL, angle=1, fill=s.faint)
    draw_rotated_text(s, "field bund", s.m(0.820, 0.355), F_HAND_SMALL, angle=-2, fill=s.faint)
    draw_rotated_text(s, "scrap area", s.m(0.625, 0.615), F_HAND_SMALL, angle=-4, fill=s.faint)
    draw_rotated_text(s, "tin sheds", s.m(0.235, 0.385), F_HAND_SMALL, angle=3, fill=s.faint)
    # Small correction-like marks, similar to photographed dummy maps.
    jitter_polyline(s, [s.m(0.150, 0.915), s.m(0.185, 0.900), s.m(0.235, 0.915)], width=2, jitter=2.0, fill=s.faint)
    jitter_polyline(s, [s.m(0.910, 0.915), s.m(0.940, 0.895), s.m(0.965, 0.905)], width=2, jitter=2.0, fill=s.faint)


def make_background(*, textured: bool) -> Image.Image:
    if not textured:
        return Image.new("RGB", (W, H), (255, 255, 255))
    base = Image.new("RGB", (W, H), (246, 245, 240))
    noise = Image.effect_noise((W, H), 9).convert("L")
    noise = noise.point(lambda p: int(244 + (p - 128) * 0.055))
    texture = Image.merge("RGB", (noise, noise, noise))
    base = Image.blend(base, texture, 0.28)
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    sd.rectangle((0, H - 190, W, H), fill=22)
    shade = shade.filter(ImageFilter.GaussianBlur(55))
    shadow = Image.new("RGB", (W, H), (225, 224, 219))
    base = Image.composite(shadow, base, shade)
    return base


def generate(kind: str, *, textured: bool) -> Image.Image:
    rng = random.Random(SEED + (11 if textured else 0))
    img = make_background(textured=textured)
    draw = ImageDraw.Draw(img)
    ink = (20, 20, 19) if not textured else (24, 23, 22)
    faint = (94, 94, 90) if not textured else (105, 103, 98)
    map_box = (710, 140, W - 90, H - 110)
    s = Sheet(image=img, draw=draw, rng=rng, ink=ink, faint=faint, map_box=map_box)

    draw_sheet_frame(s, textured=textured)
    draw_boundary_and_context(s)
    draw_north_arrow(s)
    draw_open_spaces(s)
    roads = draw_roads(s)
    draw_houses(s, roads)
    draw_enumerator_flow(s)
    add_hand_notes(s)

    if textured:
        # Very light scan softness without losing crisp printability.
        img = img.filter(ImageFilter.GaussianBlur(0.18))
    return img


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    detailed = generate("detailed", textured=True)
    printable = generate("printable", textured=False)

    detailed_path = os.path.join(OUT_DIR, "hlb_0254_field_map_detailed_sketch.png")
    printable_path = os.path.join(OUT_DIR, "hlb_0254_field_map_printable.png")
    pdf_path = os.path.join(OUT_DIR, "hlb_0254_field_map_printable.pdf")
    map_only_path = os.path.join(OUT_DIR, "hlb_0254_map_only_detailed_sketch.png")
    detailed.save(detailed_path, quality=95)
    printable.save(printable_path, quality=95)
    printable.save(pdf_path, "PDF", resolution=300.0)
    detailed.crop((710, 140, W - 90, H - 110)).save(map_only_path, quality=95)
    print(detailed_path)
    print(printable_path)
    print(pdf_path)
    print(map_only_path)


if __name__ == "__main__":
    main()
