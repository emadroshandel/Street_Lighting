# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Obstruction of light by tree crowns.

EN 13201-3 clause 4.1 c) disregards obstruction for the conformity
calculation.  Real streets have trees, so the application also evaluates the
installation *with* trees: every crown is an ellipsoid of foliage and the
light crossing it is attenuated by Beer-Lambert's law

    T = exp(-kappa * chord)

where chord is the length of the light path inside the crown and kappa (1/m)
is the foliage extinction coefficient (about 0.3 for light, 0.6 for average
and 1.2 for dense summer foliage).  Several crowns multiply.
"""
from __future__ import annotations

import numpy as np


def crowns_array(crowns):
    """(T, 7) array: cx, cy, cz, rh, rv, kappa, s."""
    if not crowns:
        return np.zeros((0, 7))
    a = []
    for c in crowns:
        base, top = float(c["base"]), float(c["top"])
        rv = max((top - base) / 2.0, 0.3)
        a.append([c["x"], c["yw"], c["z0"] + base + rv, float(c["r"]), rv,
                  float(c.get("kappa", 0.6)), float(c.get("s", 0.0))])
    return np.array(a, float)


def transmission(Lp, P, crowns, chunk=200000):
    """Transmission factor (K, N) for light paths from luminaires Lp (K, 3) to
    points P (N, 3) through crowns (T, 7)."""
    K, N = len(Lp), len(P)
    T = np.ones((K, N))
    if crowns is None or len(crowns) == 0 or K == 0 or N == 0:
        return T
    crowns = np.asarray(crowns)
    # prefilter crowns that can intersect the bounding box of all paths
    lo = np.minimum(Lp.min(0), P.min(0)) - 1.0
    hi = np.maximum(Lp.max(0), P.max(0)) + 1.0
    m = ((crowns[:, 0] + crowns[:, 3] >= lo[0]) & (crowns[:, 0] - crowns[:, 3] <= hi[0]) &
         (crowns[:, 1] + crowns[:, 3] >= lo[1]) & (crowns[:, 1] - crowns[:, 3] <= hi[1]) &
         (crowns[:, 2] + crowns[:, 4] >= lo[2]) & (crowns[:, 2] - crowns[:, 4] <= hi[2]))
    crowns = crowns[m]
    if len(crowns) == 0:
        return T
    D = P[None, :, :] - Lp[:, None, :]                   # (K, N, 3) path vectors
    length = np.linalg.norm(D, axis=-1)
    optical = np.zeros((K, N))
    for c in crowns:
        cx, cy, cz, rh, rv, kap, _ = c
        scale = np.array([1.0 / rh, 1.0 / rh, 1.0 / rv])
        o = (Lp - np.array([cx, cy, cz])) * scale          # (K, 3)
        d = D * scale                                       # (K, N, 3)
        A = (d ** 2).sum(-1)
        B = 2.0 * (d * o[:, None, :]).sum(-1)
        C = (o ** 2).sum(-1)[:, None] - 1.0
        disc = B * B - 4 * A * C
        hit = disc > 0
        if not np.any(hit):
            continue
        sq = np.sqrt(np.where(hit, disc, 0.0))
        t1 = np.clip((-B - sq) / (2 * A), 0.0, 1.0)
        t2 = np.clip((-B + sq) / (2 * A), 0.0, 1.0)
        chord = np.where(hit, (t2 - t1), 0.0) * length
        optical += kap * chord
    return np.exp(-optical)


def luminaire_in_crown(pos, crowns):
    """True for luminaire positions (K, 3) that sit inside a crown."""
    pos = np.atleast_2d(pos)
    if crowns is None or len(crowns) == 0:
        return np.zeros(len(pos), bool)
    c = np.asarray(crowns)
    dx = (pos[:, None, 0] - c[None, :, 0]) / c[None, :, 3]
    dy = (pos[:, None, 1] - c[None, :, 1]) / c[None, :, 3]
    dz = (pos[:, None, 2] - c[None, :, 2]) / c[None, :, 4]
    return ((dx ** 2 + dy ** 2 + dz ** 2) < 1.0).any(1)


def straight_crowns(section, x_from, x_to):
    """Crowns for a straight section: section['trees'] = list of tree lines
    {y, spacing, phase (m), crown_base, height, crown_radius, density}."""
    out = []
    for tl in section.get("trees", []) or []:
        sp = max(float(tl.get("spacing", 8.0)), 1.0)
        ph = float(tl.get("phase", 0.0))
        k0 = int(np.floor((x_from - ph) / sp)) - 1
        k1 = int(np.ceil((x_to - ph) / sp)) + 1
        for k in range(k0, k1 + 1):
            x = ph + k * sp
            if x_from <= x <= x_to:
                out.append(dict(x=x, yw=float(tl["y"]), z0=0.0, base=float(tl.get("crown_base", 3.0)),
                                top=float(tl.get("height", 8.0)), r=float(tl.get("crown_radius", 2.5)),
                                kappa=float(tl.get("density", 0.6)), s=x))
    return crowns_array(out)
