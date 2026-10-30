# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Luminous intensity tables (I-tables).

Readers
-------
* IES LM-63 (1986, 1991, 1995, 2002, 2019) — type C photometry
* EULUMDAT (.ldt) — all symmetry indicators 0..4

Both are converted to one internal form: absolute candela on a full
C = 0..360 deg x gamma = 0..180 deg table, for the lamp flux actually used.
Linear interpolation follows EN 13201-3:2015 clause 5.2.2 (first in C,
then in gamma; the order does not change the result).

Generic optics
--------------
For preliminary sizing without a manufacturer's file (or for old lamp types
where no file exists) `generic()` builds a smooth road-lighting distribution
from a few physical parameters.  Reports flag such results as indicative.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

DEG = math.pi / 180.0


# ---------------------------------------------------------------------------
# data container
# ---------------------------------------------------------------------------
@dataclass
class Photometry:
    name: str = "luminaire"
    manufacturer: str = ""
    catalogue: str = ""
    source: str = "generic"          # 'ies' | 'ldt' | 'generic'
    C: np.ndarray = None              # deg, ascending, 0..360 inclusive
    G: np.ndarray = None              # deg, ascending, 0..180 inclusive
    I: np.ndarray = None              # cd, shape (len(C), len(G))
    lamp_flux: float = 0.0            # lm of the light source(s) the table refers to
    power: float = 0.0                # W, system power (lamp + gear)
    absolute: bool = False            # True when the file is absolute (LED) photometry
    tilt_measurement: float = 0.0     # deg, theta_m
    lamp_type: str = "LED"
    cct: float = 4000.0
    cri: float = 70.0
    lum_length: float = 0.5           # m, luminaire / luminous area size
    lum_width: float = 0.25
    lum_height: float = 0.0
    lum_area: float = 0.0             # m2, luminous area (for glare index)
    weight: float = 10.0              # kg (structural)
    wind_area: float = 0.12           # m2 projected area (structural)
    symmetry: str = "none"
    notes: list = field(default_factory=list)
    _cache: dict = field(default_factory=dict, repr=False)

    # -- interpolation ---------------------------------------------------
    def intensity(self, C, gamma):
        """Absolute intensity (cd) for arrays of C and gamma in degrees."""
        C = np.mod(np.asarray(C, float), 360.0)
        g = np.clip(np.asarray(gamma, float), 0.0, 180.0)
        Ca, Ga, Ia = self.C, self.G, self.I
        ic = np.clip(np.searchsorted(Ca, C, side="right") - 1, 0, len(Ca) - 2)
        ig = np.clip(np.searchsorted(Ga, g, side="right") - 1, 0, len(Ga) - 2)
        c0, c1 = Ca[ic], Ca[ic + 1]
        g0, g1 = Ga[ig], Ga[ig + 1]
        tc = np.where(c1 > c0, (C - c0) / np.where(c1 > c0, c1 - c0, 1.0), 0.0)
        tg = np.where(g1 > g0, (g - g0) / np.where(g1 > g0, g1 - g0, 1.0), 0.0)
        # interpolation on C first (EN 13201-3 Formulae 4 and 6), then gamma (8)
        i_j = Ia[ic, ig] + tc * (Ia[ic + 1, ig] - Ia[ic, ig])
        i_j1 = Ia[ic, ig + 1] + tc * (Ia[ic + 1, ig + 1] - Ia[ic, ig + 1])
        return i_j + tg * (i_j1 - i_j)

    # -- derived quantities ---------------------------------------------
    def flux_split(self):
        """(total, downward, upward) luminaire flux in lm by numerical integration."""
        if "flux" in self._cache:
            return self._cache["flux"]
        dg, dc = 0.5, 1.0
        g = np.arange(dg / 2, 180.0, dg)
        c = np.arange(dc / 2, 360.0, dc)
        CC, GG = np.meshgrid(c, g, indexing="ij")
        I = self.intensity(CC, GG)
        dOmega = np.sin(GG * DEG) * (dg * DEG) * (dc * DEG)
        F = I * dOmega
        down = float(F[:, g < 90].sum())
        up = float(F[:, g >= 90].sum())
        self._cache["flux"] = (down + up, down, up)
        return self._cache["flux"]

    @property
    def luminaire_flux(self):
        return self.flux_split()[0]

    @property
    def lor(self):
        t = self.luminaire_flux
        return t / self.lamp_flux if self.lamp_flux > 0 else 1.0

    @property
    def ulor(self):
        return self.flux_split()[2] / self.lamp_flux if self.lamp_flux > 0 else 0.0

    @property
    def efficacy(self):
        return self.luminaire_flux / self.power if self.power > 0 else 0.0

    def max_intensity(self):
        k = np.unravel_index(np.argmax(self.I), self.I.shape)
        return float(self.I[k]), float(self.C[k[0]]), float(self.G[k[1]])

    def street_side(self):
        """Return +1 if more downward flux goes to the C90 half, -1 if to C270."""
        if "side" in self._cache:
            return self._cache["side"]
        g = np.arange(1.0, 90.0, 2.0)
        c90 = np.arange(1.0, 180.0, 2.0)
        c270 = c90 + 180.0
        w = np.sin(g * DEG)
        a = sum(float((self.intensity(np.full_like(g, c), g) * w).sum()) for c in c90)
        b = sum(float((self.intensity(np.full_like(g, c), g) * w).sum()) for c in c270)
        self._cache["side"] = 1 if a >= b else -1
        return self._cache["side"]

    def symmetric_c90(self, tol=0.03):
        """True if I(C) == I(180 - C): same light toward +x and -x along the road."""
        if "symc90" in self._cache:
            return self._cache["symc90"]
        g = np.arange(0.0, 90.0, 2.5)
        c = np.arange(0.0, 90.0, 5.0)
        CC, GG = np.meshgrid(c, g, indexing="ij")
        a = self.intensity(CC, GG) + self.intensity(CC + 270.0, GG)
        b = self.intensity(180.0 - CC, GG) + self.intensity(270.0 - CC, GG)
        ok = bool(np.abs(a - b).max() <= tol * max(float(self.I.max()), 1e-9))
        self._cache["symc90"] = ok
        return ok

    def mirror_deviation(self, plane: float) -> float:
        """Largest |I(C) - I(mirror of C)| / Imax below the horizontal.

        plane = 90: mirror in the C90-C270 plane (I(C) vs I(180 - C)), i.e. the same
        light forward and backward along the road (C0-C180 axis).
        plane = 0:  mirror in the C0-C180 plane (I(C) vs I(-C)).
        """
        g = np.arange(0.0, 90.0, 2.5)
        c = np.arange(0.0, 360.0, 5.0)
        CC, GG = np.meshgrid(c, g, indexing="ij")
        a = self.intensity(CC, GG)
        b = self.intensity((180.0 - CC) if plane == 90 else -CC, GG)
        return float(np.abs(a - b).max() / max(float(self.I.max()), 1e-9))

    def rotated(self, angle: float):
        """Copy with the C-plane system turned by `angle` deg: I_new(C) = I_old(C - angle)."""
        Cn = np.unique(np.round(np.mod(self.C + angle, 360.0), 9))
        if Cn[0] > 1e-9:
            Cn = np.concatenate([[0.0], Cn])
        if Cn[-1] < 360.0 - 1e-9:
            Cn = np.concatenate([Cn, [360.0]])
        CC, GG = np.meshgrid(Cn, self.G, indexing="ij")
        p = Photometry(**{k: v for k, v in self.__dict__.items() if k != "_cache"})
        p.C = Cn
        p.I = self.intensity(CC - angle, GG)
        p.notes = list(self.notes)
        p.symmetry = "none"
        p._cache = {}
        return p

    def orient_for_road(self, tol_sym=0.01, min_asym=0.03):
        """Turn the C-planes 90 deg when the file's along-road axis is C90-C270.

        The engine (like EN 13201-3 / CIE 140) takes C0-C180 along the road and C90 as
        the street side, so a road luminaire is mirror-symmetric in the C90-C270 plane.
        Some files — notably many IES (LM-63) road files, whose horizontal-angle origin is
        not fixed by the format, and the IES files of the CIE 140:2019 Annex B test set —
        put the along-road axis on 90-270 instead.  Such a file is mirror-symmetric in
        the C0-C180 plane and not in the C90-C270 plane; it is turned by 90 deg here and
        the street side is then found as usual.  Returns (photometry, rotated?).
        """
        d90 = self.mirror_deviation(90)
        d0 = self.mirror_deviation(0)
        if d0 <= tol_sym and d90 >= min_asym:
            p = self.rotated(90.0)
            p.notes.append("C-planes turned 90 deg: the file's along-road axis was 90-270 "
                           "(symmetric in the C0-C180 plane), the engine uses C0-C180 along the road.")
            return p, True
        return self, False

    def scaled(self, factor: float, power_factor: float | None = None):
        """Copy with intensities scaled (dimming or a different lumen package)."""
        p = Photometry(**{k: v for k, v in self.__dict__.items() if k != "_cache"})
        p.I = self.I * factor
        p.lamp_flux = self.lamp_flux * factor
        p.power = self.power * (factor if power_factor is None else power_factor)
        p.notes = list(self.notes)
        p._cache = {}
        return p

    def to_dict(self, full=False):
        tot, down, up = self.flux_split()
        imax, cmax, gmax = self.max_intensity()
        d = dict(name=self.name, manufacturer=self.manufacturer,
                 catalogue=self.catalogue, source=self.source,
                 lamp_flux=round(self.lamp_flux, 1), power=round(self.power, 2),
                 luminaire_flux=round(tot, 1), downward_flux=round(down, 1),
                 upward_flux=round(up, 1), lor=round(self.lor, 4),
                 ulor=round(self.ulor, 5), efficacy=round(self.efficacy, 1),
                 imax=round(imax, 1), imax_C=cmax, imax_gamma=gmax,
                 absolute=self.absolute, tilt_measurement=self.tilt_measurement,
                 lamp_type=self.lamp_type, cct=self.cct, cri=self.cri,
                 lum_length=self.lum_length, lum_width=self.lum_width,
                 lum_area=self.lum_area, symmetry=self.symmetry,
                 weight=self.weight, wind_area=self.wind_area,
                 notes=self.notes, nC=len(self.C), nG=len(self.G))
        if full:
            d["C"] = self.C.tolist()
            d["G"] = self.G.tolist()
            d["I"] = np.round(self.I, 3).tolist()
        return d

    def polar(self, planes=(0, 90, 180, 270), step=2.5):
        """Polar curves in cd/klm for the given C planes (for drawing)."""
        g = np.arange(0.0, 180.0 + 1e-9, step)
        k = 1000.0 / self.lamp_flux if self.lamp_flux > 0 else 1.0
        return {str(c): (self.intensity(np.full_like(g, c), g) * k).round(2).tolist()
                for c in planes} | {"gamma": g.tolist()}

    def isocandela(self, nC=73, nG=37):
        c = np.linspace(0, 360, nC)
        g = np.linspace(0, 180, nG)
        CC, GG = np.meshgrid(c, g, indexing="ij")
        k = 1000.0 / self.lamp_flux if self.lamp_flux > 0 else 1.0
        return dict(C=c.tolist(), G=g.tolist(),
                    I=(self.intensity(CC, GG) * k).round(2).tolist())


# ---------------------------------------------------------------------------
# symmetry expansion
# ---------------------------------------------------------------------------
def _expand(Cdef, Gdef, Idef, mode):
    """Expand a partial C-plane table to the full circle.

    mode: 'rot'   one plane, rotationally symmetric
          'c0'    data for C 0..180, symmetric about the C0-C180 plane
          'c90'   data for C 90..270 (or 270..90), symmetric about C90-C270
          'quad'  data for C 0..90, symmetric about both planes
          'none'  full data 0..360
    """
    Cdef = np.asarray(Cdef, float)
    Idef = np.asarray(Idef, float)
    if mode == "rot":
        C = np.array([0.0, 360.0])
        I = np.vstack([Idef[0], Idef[0]])
        return C, np.asarray(Gdef, float), I
    pairs = {}
    for c, row in zip(Cdef, Idef):
        c = c % 360.0
        cs = [c]
        if mode == "c0":
            cs.append((360.0 - c) % 360.0)
        elif mode == "c90":
            cs.append((180.0 - c) % 360.0)
        elif mode == "quad":
            cs += [(180.0 - c) % 360.0, (180.0 + c) % 360.0, (360.0 - c) % 360.0]
        for cc in cs:
            key = round(cc, 6)
            if key not in pairs:
                pairs[key] = row
    keys = sorted(pairs)
    C = np.array(keys + [360.0])
    I = np.vstack([pairs[k] for k in keys] + [pairs[keys[0]]])
    return C, np.asarray(Gdef, float), I


def _fill_gamma(G, I):
    """Make sure the table spans gamma 0..180 (zero outside the measured range)."""
    G = np.asarray(G, float)
    if G[0] > 0:
        G = np.concatenate([[0.0], [G[0] - 1e-6], G]) if G[0] > 1e-6 else G
        I = np.hstack([np.zeros((I.shape[0], 2)), I])
    if G[-1] < 180:
        G = np.concatenate([G, [G[-1] + 1e-6, 180.0]])
        I = np.hstack([I, np.zeros((I.shape[0], 2))])
    return G, I


# ---------------------------------------------------------------------------
# IES LM-63
# ---------------------------------------------------------------------------
def read_ies(text: str, name: str = "") -> Photometry:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kw = {}
    version = lines[0].strip().upper() if lines else ""
    i = 0
    tilt_line = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        m = re.match(r"\[(\w+)\]\s*(.*)", s)
        if m:
            k = m.group(1).upper()
            kw[k] = (kw.get(k, "") + " " + m.group(2)).strip() if k in kw else m.group(2).strip()
        if s.upper().startswith("TILT"):
            tilt_line = s
            break
    else:
        raise ValueError("Not an IES file: no TILT= line was found.")
    rest = " ".join(lines[i + 1:])
    nums = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", rest)]
    p = 0
    notes = []
    if tilt_line.upper().startswith("TILT=INCLUDE"):
        # lamp-to-luminaire geometry, number of tilt angles, angles, factors
        p += 1
        nt = int(nums[p]); p += 1
        p += 2 * nt
        notes.append("TILT=INCLUDE data present; lamp-tilt factors were not applied.")
    n_lamps = int(nums[p]); lm_lamp = nums[p + 1]; mult = nums[p + 2]
    nV = int(nums[p + 3]); nH = int(nums[p + 4]); ptype = int(nums[p + 5])
    units = int(nums[p + 6]); width = nums[p + 7]; length = nums[p + 8]; height = nums[p + 9]
    p += 10
    bf = nums[p]; f2 = nums[p + 1]; watts = nums[p + 2]
    p += 3
    V = np.array(nums[p:p + nV]); p += nV
    H = np.array(nums[p:p + nH]); p += nH
    cand = np.array(nums[p:p + nV * nH])
    if cand.size < nV * nH:
        raise ValueError("IES file is truncated: %d of %d candela values." % (cand.size, nV * nH))
    if ptype != 1:
        raise ValueError("Only type C photometry is supported (this file is type %s)." %
                         {2: "B", 3: "A"}.get(ptype, ptype))
    factor = mult * (bf if bf > 0 else 1.0)
    if not version.startswith("IESNA:LM-63-") and f2 > 0:
        factor *= f2      # LM-63-1986/1991: ballast-lamp photometric factor; "future use" (= 1) from 1995
    I = cand.reshape(nH, nV) * factor
    absolute = lm_lamp < 0
    # horizontal symmetry
    h0, h1 = H[0], H[-1]
    if nH == 1:
        mode = "rot"
    elif abs(h0) < 1e-6 and abs(h1 - 90) < 1e-6:
        mode = "quad"
    elif abs(h0) < 1e-6 and abs(h1 - 180) < 1e-6:
        mode = "c0"
    elif abs(h0 - 90) < 1e-6 and abs(h1 - 270) < 1e-6:
        mode = "c90"
    else:
        mode = "none"
    C, G, It = _expand(H, V, I, mode)
    G, It = _fill_gamma(G, It)
    to_m = 0.3048 if units == 1 else 1.0
    ph = Photometry(
        name=name or kw.get("LUMINAIRE") or kw.get("TEST") or "IES luminaire",
        manufacturer=kw.get("MANUFAC", ""), catalogue=kw.get("LUMCAT", ""),
        source="ies", C=C, G=G, I=It, absolute=absolute,
        power=watts, symmetry=mode, notes=notes)
    ph.lum_length = abs(length) * to_m
    ph.lum_width = abs(width) * to_m
    ph.lum_height = abs(height) * to_m
    ph.lum_area = (math.pi * (abs(width) * to_m) ** 2 / 4 if width < 0 else
                   abs(width * length) * to_m * to_m)
    tot = ph.flux_split()[0]
    if absolute:
        ph.lamp_flux = tot
        notes.append("Absolute photometry: lamp flux taken equal to luminaire flux.")
    else:
        ph.lamp_flux = n_lamps * lm_lamp
    lamp = (kw.get("LAMP", "") + " " + kw.get("LAMPCAT", "")).upper()
    for key, lt in (("LED", "LED"), ("SON", "HPS"), ("HPS", "HPS"), ("SODIUM", "HPS"),
                    ("HQI", "MH"), ("METAL", "MH"), ("CDM", "MH"), ("HG", "MV"),
                    ("MERCURY", "MV"), ("SOX", "LPS"), ("CFL", "CFL"), ("FLUOR", "FL")):
        if key in lamp:
            ph.lamp_type = lt
            break
    m = re.search(r"(\d{4})\s*K", " ".join(kw.values()))
    if m:
        ph.cct = float(m.group(1))
    return ph


# ---------------------------------------------------------------------------
# EULUMDAT
# ---------------------------------------------------------------------------
def read_ldt(text: str, name: str = "") -> Photometry:
    L = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def num(i, default=0.0):
        try:
            return float(L[i].strip().replace(",", "."))
        except (ValueError, IndexError):
            return default

    if len(L) < 40:
        raise ValueError("Not a EULUMDAT file (too short).")
    Isym = int(num(2)); Mc = int(num(3))
    Ng = int(num(5))
    lum_name = L[8].strip(); lum_no = L[9].strip()
    length = num(12); width = num(13); height = num(14)
    la_len = num(15); la_wid = num(16)
    lor = num(22) / 100.0
    conv = num(23, 1.0) or 1.0
    tilt = num(24)
    n_sets = int(num(25))
    k = 26
    nl = [num(k + j) for j in range(n_sets)]; k += n_sets
    ltype = [L[k + j].strip() for j in range(n_sets)]; k += n_sets
    flux = [num(k + j) for j in range(n_sets)]; k += n_sets
    cct = [L[k + j].strip() for j in range(n_sets)]; k += n_sets
    cri = [L[k + j].strip() for j in range(n_sets)]; k += n_sets
    watt = [num(k + j) for j in range(n_sets)]; k += n_sets
    k += 10                                             # direct ratios
    C_all = np.array([num(k + j) for j in range(Mc)]); k += Mc
    G = np.array([num(k + j) for j in range(Ng)]); k += Ng
    if Isym == 0:
        mc1, mc2 = 1, Mc
    elif Isym == 1:
        mc1, mc2 = 1, 1
    elif Isym == 2:
        mc1, mc2 = 1, Mc // 2 + 1
    elif Isym == 3:
        mc1 = 3 * Mc // 4 + 1
        mc2 = mc1 + Mc // 2
    elif Isym == 4:
        mc1, mc2 = 1, Mc // 4 + 1
    else:
        raise ValueError("Unknown EULUMDAT symmetry indicator %s." % Isym)
    nplanes = mc2 - mc1 + 1
    vals = []
    for ln in L[k:]:
        for tok in ln.replace(",", ".").split():
            try:
                vals.append(float(tok))
            except ValueError:
                pass
    need = nplanes * Ng
    if len(vals) < need:
        raise ValueError("EULUMDAT intensity block is incomplete (%d of %d)." % (len(vals), need))
    I = np.array(vals[:need]).reshape(nplanes, Ng)
    idx = [((mc1 - 1 + j) % Mc) for j in range(nplanes)]
    Cdef = C_all[idx] if Mc > 1 else np.array([0.0])
    mode = {0: "none", 1: "rot", 2: "c0", 3: "c90", 4: "quad"}[Isym]
    if mode == "c90":
        # stored C270 .. 360/0 .. C90: unwrap for the expander
        Cdef = np.mod(Cdef, 360.0)
    total_flux = float(sum(abs(f) for f in flux))
    absolute = any(n < 0 for n in nl)
    scale = total_flux / 1000.0 * conv
    C, G2, It = _expand(Cdef, G, I * scale, mode)
    G2, It = _fill_gamma(G2, It)
    ph = Photometry(name=name or lum_name or "EULUMDAT luminaire",
                    manufacturer=L[0].strip(), catalogue=lum_no, source="ldt",
                    C=C, G=G2, I=It, lamp_flux=total_flux, power=float(sum(watt)),
                    absolute=absolute, tilt_measurement=tilt, symmetry=mode)
    ph.lum_length = (la_len or length) / 1000.0
    ph.lum_width = (la_wid or width) / 1000.0
    ph.lum_height = height / 1000.0
    ph.lum_area = (math.pi * (ph.lum_length ** 2) / 4 if (la_wid or width) == 0
                   else ph.lum_length * ph.lum_width)
    lt = " ".join(ltype).upper()
    ph.lamp_type = ("LED" if "LED" in lt else "HPS" if ("SON" in lt or "HPS" in lt or "NAV" in lt)
                    else "MH" if ("HQI" in lt or "CDM" in lt or "MH" in lt or "HCI" in lt)
                    else "MV" if "HQL" in lt or "HG" in lt else "LED" if not lt.strip() else lt[:12])
    try:
        ph.cct = float(re.findall(r"\d{4}", cct[0])[0])
    except (IndexError, ValueError):
        pass
    try:
        ph.cri = float(re.findall(r"\d+", cri[0])[0])
    except (IndexError, ValueError):
        pass
    if lor > 0:
        calc = ph.lor
        if abs(calc - lor) > 0.05 and not absolute:
            ph.notes.append("Declared LOR %.1f %% differs from the integrated %.1f %%."
                            % (lor * 100, calc * 100))
    return ph


def read_any(text: str, filename: str = "") -> Photometry:
    head = text.lstrip()[:200].upper()
    fn = filename.lower()
    base = re.sub(r"\.(ies|ldt)$", "", filename.split("/")[-1].split("\\")[-1], flags=re.I)
    is_ies = fn.endswith(".ies") or head.startswith("IESNA") or "TILT=" in text.upper()[:5000]
    kind = "an IES (LM-63)" if is_ies else "a EULUMDAT"
    try:
        ph = read_ies(text, "") if is_ies else read_ldt(text, "")
    except ValueError:
        raise
    except (IndexError, ZeroDivisionError, TypeError, OverflowError) as exc:
        # a damaged or incomplete file: report it as such rather than as an internal error
        raise ValueError("%s could not be read as %s file — it looks incomplete or damaged (%s)."
                         % (filename or "The file", kind, type(exc).__name__)) from exc
    if not np.all(np.isfinite(ph.I)) or ph.flux_split()[0] <= 0:
        raise ValueError("%s contains no usable light distribution (all intensities zero or invalid)."
                         % (filename or "The file"))
    ph, _ = ph.orient_for_road()
    if not ph.name or ph.name.strip() in ("", "IES luminaire", "EULUMDAT luminaire"):
        ph.name = base or ph.name
    ph.notes.append("Read from %s" % (filename or "uploaded file"))
    return ph


def write_ldt(ph: Photometry) -> str:
    """Export to EULUMDAT (full symmetry, 5 deg C, 2.5 deg gamma) — cd/klm."""
    C = np.arange(0, 360, 5.0)
    G = np.arange(0, 180.01, 2.5)
    CC, GG = np.meshgrid(C, G, indexing="ij")
    k = 1000.0 / ph.lamp_flux if ph.lamp_flux else 1.0
    I = ph.intensity(CC, GG) * k
    out = ["StreetLighting", "1", "0", str(len(C)), "5", str(len(G)), "2.5", "",
           ph.name[:78], ph.catalogue[:78], "", "",
           "%d" % (ph.lum_length * 1000), "%d" % (ph.lum_width * 1000),
           "%d" % (ph.lum_height * 1000), "%d" % (ph.lum_length * 1000),
           "%d" % (ph.lum_width * 1000), "0", "0", "0", "0",
           "%.1f" % (100 * ph.flux_split()[1] / max(ph.luminaire_flux, 1e-9)),
           "%.1f" % (100 * ph.lor), "1", "%.1f" % ph.tilt_measurement, "1",
           "1", ph.lamp_type, "%.0f" % ph.lamp_flux, "%.0f" % ph.cct,
           "%.0f" % ph.cri, "%.1f" % ph.power] + ["0"] * 10
    out += ["%.1f" % c for c in C] + ["%.1f" % g for g in G]
    out += ["%.2f" % v for v in I.ravel()]
    return "\r\n".join(out) + "\r\n"


# ---------------------------------------------------------------------------
# generic optics
# ---------------------------------------------------------------------------
LAMP_TYPES = {
    # efficacy lm/W (system), typical CCT, CRI, LLMF at 12 000 h, LSF, display name
    "LED": dict(eff=150.0, cct=3000, cri=70, llmf=0.93, lsf=1.0, label="LED module"),
    "HPS": dict(eff=95.0, cct=2000, cri=25, llmf=0.91, lsf=0.92, label="High-pressure sodium (SON)"),
    "MH": dict(eff=85.0, cct=4200, cri=80, llmf=0.75, lsf=0.85, label="Metal halide (ceramic)"),
    "MV": dict(eff=45.0, cct=4000, cri=45, llmf=0.70, lsf=0.85, label="Mercury vapour (obsolete)"),
    "LPS": dict(eff=120.0, cct=1800, cri=0, llmf=0.88, lsf=0.92, label="Low-pressure sodium (SOX)"),
    "CFL": dict(eff=60.0, cct=4000, cri=82, llmf=0.85, lsf=0.90, label="Compact fluorescent"),
    "IND": dict(eff=75.0, cct=4000, cri=80, llmf=0.80, lsf=0.98, label="Induction"),
}

OPTICS = {
    # gamma of peak, C offset of peaks from the road axis toward the street side,
    # widths, house-side fraction, cut-off angle, near-nadir share, uplight share
    "type2": dict(label="Narrow road (IES Type II, medium)", gp=68, cp=12, wg=9, wc=14,
                  house=0.20, cutoff=82, base=0.30, up=0.0),
    "type3": dict(label="Two-lane road (IES Type III, medium)", gp=67, cp=22, wg=10, wc=17,
                  house=0.14, cutoff=82, base=0.28, up=0.0),
    "type3w": dict(label="Wide road (IES Type III, long throw)", gp=70, cp=25, wg=9, wc=16,
                   house=0.10, cutoff=84, base=0.22, up=0.0),
    "type4": dict(label="Forward throw (IES Type IV)", gp=62, cp=45, wg=12, wc=24,
                  house=0.05, cutoff=80, base=0.25, up=0.0),
    "type5": dict(label="Symmetric (IES Type V, squares/car parks)", gp=55, cp=90, wg=16, wc=360,
                  house=1.0, cutoff=80, base=0.35, up=0.0),
    "post": dict(label="Decorative post-top (semi cut-off)", gp=60, cp=90, wg=22, wc=360,
                 house=1.0, cutoff=100, base=0.30, up=0.06),
    "pedestrian": dict(label="Pedestrian / residential asymmetric", gp=60, cp=30, wg=13, wc=30,
                       house=0.30, cutoff=80, base=0.35, up=0.0),
}


def generic(optic: str = "type3", lamp_flux: float = 10000.0, power: float | None = None,
            lamp_type: str = "LED", lor: float | None = None, name: str | None = None,
            cct: float | None = None) -> Photometry:
    """Smooth, physically plausible road luminaire distribution.

    The street side is C = 90 deg (the side facing the carriageway).
    Intensities are normalised so that the luminaire flux equals
    lamp_flux * LOR.
    """
    o = OPTICS.get(optic, OPTICS["type3"])
    lt = LAMP_TYPES.get(lamp_type, LAMP_TYPES["LED"])
    if lor is None:
        lor = 1.0 if lamp_type == "LED" else 0.78
    if power is None:
        power = lamp_flux / lt["eff"]
    C = np.arange(0.0, 360.0 + 1e-9, 5.0)
    G = np.arange(0.0, 180.0 + 1e-9, 2.5)
    CC, GG = np.meshgrid(C, G, indexing="ij")

    def angdiff(a, b):
        return np.abs((a - b + 180.0) % 360.0 - 180.0)

    gp, cp, wg, wc = o["gp"], o["cp"], o["wg"], o["wc"]
    house = np.ones_like(CC)
    if wc >= 360:
        lobe = np.exp(-0.5 * ((GG - gp) / wg) ** 2)
    else:
        # two lobes either side of the road axis, displaced toward the street side
        c1, c2 = 0.0 + cp, 180.0 - cp
        lobe = (np.exp(-0.5 * (angdiff(CC, c1) / wc) ** 2) +
                np.exp(-0.5 * (angdiff(CC, c2) / wc) ** 2))
        lobe *= np.exp(-0.5 * ((GG - gp) / wg) ** 2)
        # house side (C 180..360) attenuation, blended smoothly near the road axis
        near_axis = np.minimum(angdiff(CC, 0.0), angdiff(CC, 180.0))
        house = np.where((CC > 180.0) & (CC < 360.0),
                         o["house"] + (1 - o["house"]) * np.exp(-(near_axis / 12.0) ** 2), 1.0)
        lobe = lobe * house
    base = np.where(GG < 90, np.clip(np.cos(GG * DEG), 0, 1) ** 1.2, 0.0) * (0.4 + 0.6 * house)
    shape = o["base"] * base / max(base.max(), 1e-9) + (1 - o["base"]) * lobe / max(lobe.max(), 1e-9)
    # cut-off: smooth roll-off to zero at the cut-off angle
    co = o["cutoff"]
    roll = np.clip((co - GG) / 8.0, 0.0, 1.0) ** 1.5
    shape = shape * roll
    if o["up"] > 0:
        shape = shape + o["up"] * np.where(GG > 90, np.sin((GG - 90) * 2 * DEG) ** 2, 0.0)
    ph = Photometry(name=name or "%s — %s" % (lt["label"], o["label"]), source="generic",
                    C=C, G=G, I=shape, lamp_flux=lamp_flux, power=power,
                    lamp_type=lamp_type, cct=cct or lt["cct"], cri=lt["cri"],
                    symmetry="c0" if wc < 360 else "rot")
    tot = ph.flux_split()[0]
    ph.I = shape * (lamp_flux * lor / tot)
    ph._cache = {}
    ph.lum_area = 0.10
    ph.notes.append("Generic optic generated from parameters — indicative only; "
                    "use the manufacturer's photometric file for final design.")
    return ph
