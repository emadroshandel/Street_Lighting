# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Luminaire attitude and the (C, gamma) of a light path.

Global axes: x along the road (direction of travel of the observer), y across
the road (to the left when looking along +x), z up.  This is the right-handed
system of EN 13201-3:2015 clause 6.2.

A luminaire's photometric frame is defined by three turning angles applied in
the order of EN 13201-3 Figure 6:

* orientation  nu   about the vertical axis  — the C = 0 half-plane points to
                    azimuth nu (deg from +x, counter-clockwise seen from above);
                    the street side C = 90 then points to nu + 90.
* tilt         delta about the C0-C180 axis — positive raises the C = 90 side
                    (tilt for calculation, delta = theta_f - theta_m, Formula 11)
* rotation     psi   about the C90-C270 axis

For a direction vector v (luminaire -> point) in global axes the local
components are l = R^T v and

    gamma = atan( sqrt(lx^2 + ly^2) / (-lz) )     (Formula 21)
    C     = atan2(ly, lx)                          (Formulae 15-20)

which is a rotation-matrix form mathematically equivalent to Formulae 12-14.
"""
from __future__ import annotations

import math

import numpy as np

DEG = math.pi / 180.0


def rotation(nu_deg: float, delta_deg: float = 0.0, psi_deg: float = 0.0) -> np.ndarray:
    """3x3 matrix whose columns are the C0, C90 and up axes of the luminaire."""
    n, d, p = nu_deg * DEG, delta_deg * DEG, psi_deg * DEG
    Rz = np.array([[math.cos(n), -math.sin(n), 0], [math.sin(n), math.cos(n), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(d), -math.sin(d)], [0, math.sin(d), math.cos(d)]])
    Ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    return Rz @ Rx @ Ry


def c_gamma(R: np.ndarray, v: np.ndarray):
    """(C, gamma) in degrees for global direction vectors v (..., 3)."""
    l = v @ R            # = R^T v for row vectors
    lx, ly, lz = l[..., 0], l[..., 1], l[..., 2]
    gamma = np.degrees(np.arctan2(np.hypot(lx, ly), -lz))
    C = np.mod(np.degrees(np.arctan2(ly, lx)), 360.0)
    return C, gamma


class Luminaire:
    """One luminaire placed in the scene."""

    __slots__ = ("x", "y", "z", "nu", "tilt", "rot", "phot", "flux", "R", "pole",
                 "row", "tag", "on")

    def __init__(self, x, y, z, nu=0.0, tilt=0.0, rot=0.0, phot=None, flux=1.0,
                 pole=None, row=0, tag=""):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.nu, self.tilt, self.rot = float(nu), float(tilt), float(rot)
        self.phot = phot
        self.flux = float(flux)          # dimming / lumen-package multiplier
        self.pole = pole                 # (x, y, z_ground) of the column base
        self.row = row
        self.tag = tag
        self.on = True
        meas = phot.tilt_measurement if phot is not None else 0.0
        self.R = rotation(nu, tilt - meas, rot)

    @property
    def pos(self):
        return np.array([self.x, self.y, self.z])

    def intensity_to(self, pts):
        """Intensity (cd) toward points pts (N, 3) — includes the flux multiplier."""
        v = np.asarray(pts, float) - self.pos
        C, g = c_gamma(self.R, v)
        return self.phot.intensity(C, g) * self.flux

    def to_dict(self):
        return dict(x=round(self.x, 3), y=round(self.y, 3), z=round(self.z, 3),
                    nu=round(self.nu, 2), tilt=self.tilt, rot=self.rot,
                    flux=round(self.flux, 4), row=self.row, tag=self.tag,
                    pole=None if self.pole is None else [round(v, 3) for v in self.pole])


def group_intensities(lums, P):
    """Intensity matrix (K, N) from K luminaires to N points (N, 3).

    Luminaires sharing a photometry are evaluated in one vectorised call.
    """
    P = np.asarray(P, float)
    K, N = len(lums), len(P)
    out = np.zeros((K, N))
    groups = {}
    for k, l in enumerate(lums):
        groups.setdefault(id(l.phot), []).append(k)
    for idx in groups.values():
        ph = lums[idx[0]].phot
        pos = np.array([lums[k].pos for k in idx])            # (k, 3)
        R = np.array([lums[k].R for k in idx])                # (k, 3, 3)
        V = P[None, :, :] - pos[:, None, :]                    # (k, N, 3)
        Lc = np.einsum("kni,kij->knj", V, R)
        g = np.degrees(np.arctan2(np.hypot(Lc[..., 0], Lc[..., 1]), -Lc[..., 2]))
        C = np.mod(np.degrees(np.arctan2(Lc[..., 1], Lc[..., 0])), 360.0)
        fl = np.array([lums[k].flux for k in idx])[:, None]
        out[idx] = ph.intensity(C, g) * fl
    return out


def installed_intensity_class(phot, tilt=0.0, rot=0.0):
    """EN 13201-2 Annex A G* class and peak values for the installed tilt.

    Returns dict with the max cd/klm at >= 70, 80, 90 deg from the downward
    vertical, the max above 90/95 deg, and the best G* class satisfied.
    """
    R = rotation(0.0, tilt - phot.tilt_measurement, rot)
    th = np.arange(60.0, 180.0 + 1e-9, 0.5)                   # angle from nadir
    az = np.arange(0.0, 360.0, 2.5)
    TT, AA = np.meshgrid(th, az, indexing="ij")
    v = np.stack([np.sin(TT * DEG) * np.cos(AA * DEG), np.sin(TT * DEG) * np.sin(AA * DEG),
                  -np.cos(TT * DEG)], axis=-1)
    C, g = c_gamma(R, v)
    I = phot.intensity(C, g) * 1000.0 / max(phot.luminaire_flux, 1e-9)
    imax = lambda lo, hi=181: float(I[(TT >= lo) & (TT < hi)].max()) if np.any((TT >= lo) & (TT < hi)) else 0.0
    i70, i80, i90 = imax(70), imax(80), imax(90)
    above90, above95 = imax(90.0001), imax(95.0001)
    table = [("G*6", 350, 100, 0, 90), ("G*5", 350, 100, 10, 95), ("G*4", 500, 100, 10, 95),
             ("G*3", None, 100, 20, None), ("G*2", None, 150, 30, None),
             ("G*1", None, 200, 50, None)]
    cls = "none"
    for name, a70, a80, a90, zero_above in table:
        ok = (a70 is None or i70 <= a70) and i80 <= a80 and i90 <= max(a90, 1.0 if a90 == 0 else a90)
        if zero_above == 90:
            ok = ok and above90 <= 1.0
        elif zero_above == 95:
            ok = ok and above95 <= 1.0
        if ok:
            cls = name
            break
    return dict(cls=cls, i70=round(i70, 1), i80=round(i80, 1), i90=round(i90, 1),
                above90=round(above90, 2), above95=round(above95, 2))


def glare_index(phot):
    """EN 13201-2 Annex A.2 glare index I85 * A^-0.5 and D class."""
    g = np.full(144, 85.0)
    c = np.arange(0, 360, 2.5)
    I85 = float(phot.intensity(c, g).max())
    A = phot.lum_area if phot.lum_area > 0 else max(phot.lum_length * phot.lum_width, 0.01)
    A85 = A * math.cos(85 * DEG) + phot.lum_length * max(phot.lum_height, 0.0) * math.sin(85 * DEG)
    A85 = max(A85, 1e-4)
    gi = I85 / math.sqrt(A85)
    cls = "D0"
    for name, lim in (("D6", 500), ("D5", 1000), ("D4", 2000), ("D3", 4000), ("D2", 5500), ("D1", 7000)):
        if gi <= lim:
            cls = name
            break
    return dict(I85=round(I85, 1), area=round(A85, 5), index=round(gi, 0), cls=cls)
