# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Isolines by marching squares, joined into polylines.

Used for the DXF drawings and the report; the browser has its own copy for
interactive display.  Levels are chosen on a 1-2-5 progression so that the
isolux / isoluminance labels are round numbers.
"""
from __future__ import annotations

import math

import numpy as np


def nice_levels(vmin, vmax, n=8, include=None):
    if vmax <= 0:
        return []
    lo = max(vmin, vmax / 200.0)
    raw = (vmax - lo) / max(n, 1)
    mag = 10 ** math.floor(math.log10(max(raw, 1e-12)))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10)), key=lambda s: abs(s - raw))
    start = math.ceil(lo / step) * step
    lv = list(np.arange(start, vmax, step))
    if include:
        lv = sorted(set([round(v, 6) for v in lv] + [v for v in include if vmin < v < vmax]))
    return [float(round(v, 6)) for v in lv]


def isolines(xs, ys, Z, level):
    """Segments of Z == level; Z indexed [iy][ix] with coordinates xs, ys."""
    Z = np.asarray(Z, float)
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    segs = []
    ny, nx = Z.shape
    for j in range(ny - 1):
        for i in range(nx - 1):
            z = (Z[j, i], Z[j, i + 1], Z[j + 1, i + 1], Z[j + 1, i])
            c = sum(1 << k for k in range(4) if z[k] >= level)
            if c in (0, 15):
                continue
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            corner = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))

            def edge(a, b):
                za, zb = z[a], z[b]
                t = (level - za) / (zb - za) if zb != za else 0.5
                pa, pb = corner[a], corner[b]
                return (pa[0] + t * (pb[0] - pa[0]), pa[1] + t * (pb[1] - pa[1]))
            e = {0: (0, 1), 1: (1, 2), 2: (2, 3), 3: (3, 0)}
            table = {1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)], 5: [(3, 2), (0, 1)],
                     6: [(0, 2)], 7: [(3, 2)], 8: [(2, 3)], 9: [(0, 2)], 10: [(0, 3), (1, 2)],
                     11: [(1, 2)], 12: [(1, 3)], 13: [(0, 1)], 14: [(0, 3)]}
            for ea, eb in table[c]:
                segs.append((edge(*e[ea]), edge(*e[eb])))
    return _join(segs)


def _join(segs, tol=1e-6):
    if not segs:
        return []
    key = lambda p: (round(p[0] / tol) if tol else p[0], round(p[1] / tol) if tol else p[1])
    from collections import defaultdict
    ends = defaultdict(list)
    for k, (a, b) in enumerate(segs):
        ends[key(a)].append(k)
        ends[key(b)].append(k)
    used = [False] * len(segs)
    lines = []
    for k in range(len(segs)):
        if used[k]:
            continue
        used[k] = True
        a, b = segs[k]
        line = [a, b]
        for direction in (1, -1):
            while True:
                tip = line[-1] if direction == 1 else line[0]
                nxt = None
                for j in ends[key(tip)]:
                    if not used[j]:
                        nxt = j
                        break
                if nxt is None:
                    break
                used[nxt] = True
                p, q = segs[nxt]
                other = q if key(p) == key(tip) else p
                if direction == 1:
                    line.append(other)
                else:
                    line.insert(0, other)
        lines.append(line)
    return lines


def contour_set(xs, ys, Z, levels):
    return [dict(level=lv, lines=isolines(xs, ys, Z, lv)) for lv in levels]
