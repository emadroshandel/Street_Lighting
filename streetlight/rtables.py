# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Road surface reflection tables (reduced luminance coefficients).

The four standard dry surfaces R1..R4 of the CIE classification are given as
r x 10^4 at the tan(epsilon) / beta directions of EN 13201-3:2015 Table 3.
Values transcribed from ANSI/IESNA RP-8-00 Tables A1..A4 (identical to the
CIE standard tables).  Q0, S1 and S2 are the published table descriptors.

Interpolation follows EN 13201-3 clause 5.3.2 (linear in tan(epsilon) and in
beta).  Blank cells of the standard tables (large tan(epsilon) at large beta)
"should not be used for calculation"; where a luminaire nevertheless falls
in that region the last tabulated value of the row is held, which is the
usual software convention and has negligible effect on results.

Note on R4, beta = 180 deg: this column is extrapolated from the 165 deg
column with the local trend (marked below).  At beta = 180 deg the luminaire
is behind the observation point, where r is small and the effect on L, Uo and
Ul is negligible; users who hold CIE 144 can replace the column through the
user r-table import.
"""
from __future__ import annotations

import numpy as np

TAN_E = np.array([0, .25, .5, .75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5, 4, 4.5, 5,
                  5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12.0])
BETA = np.array([0, 2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 60, 75, 90, 105, 120, 135,
                 150, 165, 180.0])

_R1 = """
655 655 655 655 655 655 655 655 655 655 655 655 655 655 655 655 655 655 655 655
619 619 619 619 610 610 610 610 610 610 610 610 610 601 601 601 601 601 601 601
539 539 539 539 539 539 521 521 521 521 521 503 503 503 503 503 503 503 503 503
431 431 431 431 431 431 431 431 431 431 395 386 371 371 371 371 371 386 395 395
341 341 341 341 323 323 305 296 287 287 278 269 269 269 269 269 269 278 278 278
269 269 269 260 251 242 224 207 198 189 189 180 180 180 180 180 189 198 207 224
224 224 224 215 198 180 171 162 153 148 144 144 139 139 139 144 148 153 162 180
189 189 189 171 153 139 130 121 117 112 108 103 99 99 103 108 112 121 130 139
162 162 157 135 117 108 99 94 90 85 85 83 84 84 86 90 94 99 103 111
121 121 117 95 79 66 60 57 54 52 51 50 51 52 54 58 61 65 69 75
94 94 86 66 49 41 38 36 34 33 32 31 31 33 35 38 40 43 47 51
81 80 66 46 33 28 25 23 22 22 21 21 22 22 24 27 29 31 34 38
71 69 55 32 23 20 18 16 15 14 14 14 15 17 19 20 22 23 25 27
63 59 43 24 17 14 13 12 12 11 11 11 12 13 14 14 16 17 19 21
57 52 36 19 14 12 10 9.0 9.0 8.8 8.7 8.7 9.0 10 11 13 14 15 16 16
51 47 31 15 11 9.0 8.1 7.8 7.7 7.7
47 42 25 12 8.5 7.2 6.5 6.3 6.2
43 38 22 10 6.7 5.8 5.2 5.0
40 34 18 8.1 5.6 4.8 4.4 4.2
37 31 15 6.9 4.7 4.0 3.8
35 28 14 5.7 4.0 3.6 3.2
33 25 12 4.8 3.6 3.1 2.9
31 23 10 4.1 3.2 2.8
30 22 9.0 3.7 2.8 2.5
29 20 8.2 3.2 2.4 2.2
28 18 7.3 3.0 2.2 1.9
27 16 6.6 2.7 1.9 1.7
26 15 6.1 2.4 1.7
25 14 5.6 2.2 1.6
"""

_R2 = """
390 390 390 390 390 390 390 390 390 390 390 390 390 390 390 390 390 390 390 390
411 411 411 411 411 411 411 411 411 411 379 368 357 357 346 346 346 335 335 335
411 411 411 411 403 403 384 379 370 346 325 303 281 281 271 271 271 260 260 260
379 379 379 368 357 346 325 303 281 260 238 216 206 206 206 206 206 206 206 206
335 335 335 325 292 291 260 238 216 195 173 152 152 152 152 152 141 141 141 141
303 303 292 271 238 206 184 152 130 119 108 100 103 106 108 108 114 114 119 119
271 271 260 227 179 152 141 119 108 93 80 76 76 80 84 87 89 91 93 95
249 238 227 195 152 124 106 91 78 67 61 52 54 58 63 67 69 71 73 74
227 216 195 152 117 95 80 67 61 52 45 40 41 45 49 52 54 56 57 58
195 190 146 110 74 58 48 40 35 30 27 24 26 28 30 33 35 38 40 41
160 155 115 67 43 33 26 21 18 17 16 16 17 17 18 21 22 24 26 27
146 131 87 41 25 18 15 13 12 11 11 11 11 11 12 14 15 17 18 21
132 113 67 27 15 12 10 9.4 8.7 8.2 7.9 7.6 7.9 8.7 9.6 11 12 13 15 17
118 95 50 20 12 8.9 7.4 6.6 6.3 6.1 5.7 5.6 5.8 6.3 7.1 8.4 10 12 13 14
106 81 38 14 8.2 6.3 5.4 5.0 4.8 4.7 4.5 4.4 4.8 5.2 6.2 7.4 8.5 9.5 10 11
96 69 29 11 6.3 5.1 4.4 4.1 3.9 3.8
87 58 22 8.0 5.0 3.9 3.5 3.4 3.2
78 50 17 6.1 3.8 3.1 2.8 2.7
71 43 14 4.9 3.1 2.5 2.3 2.2
67 38 12 4.1 2.6 2.1 1.9
63 33 10 3.4 2.2 1.8 1.7
58 28 8.7 2.9 1.9 1.6 1.5
55 25 7.4 2.5 1.7 1.4
52 23 6.5 2.2 1.5 1.3
49 21 5.6 1.9 1.4 1.2
47 18 5.0 1.7 1.3 1.2
44 16 4.4 1.6 1.2 1.1
42 14 4.0 1.5 1.1
41 13 3.6 1.4 1.1
"""

_R3 = """
294 294 294 294 294 294 294 294 294 294 294 294 294 294 294 294 294 294 294 294
326 326 321 321 317 312 308 308 303 298 294 280 271 262 258 253 249 244 240 240
344 344 339 339 326 317 308 298 289 276 262 235 217 204 199 199 199 199 194 194
357 353 353 339 321 303 285 267 244 222 204 176 158 149 149 149 145 136 136 140
362 362 352 326 276 249 226 204 181 158 140 118 104 100 100 100 100 100 100 100
357 357 348 298 244 208 176 154 136 118 104 83 73 70 71 74 77 77 77 78
353 348 326 267 217 176 145 117 100 86 78 72 60 57 58 60 60 60 61 62
339 335 303 231 172 127 104 89 79 70 62 51 45 44 45 46 45 45 46 47
326 321 280 190 136 100 82 71 62 54 48 39 34 34 34 35 36 36 37 38
289 280 222 127 86 65 54 44 38 34 25 23 22 23 24 24 24 24 24 25
253 235 163 85 53 38 31 25 23 20 18 15 15 14 15 15 16 16 17 17
217 194 122 60 35 25 22 19 16 15 13 9.9 9.0 9.0 9.9 11 11 12 12 13
190 163 90 43 26 20 16 14 12 9.9 9.0 7.4 7.0 7.1 7.5 8.3 8.7 9.0 9.0 9.9
163 136 73 31 20 15 12 9.9 9.0 8.3 7.7 5.4 4.8 4.9 5.4 6.1 7.0 7.7 8.3 8.5
145 109 60 24 16 12 9.0 8.2 7.7 6.8 6.1 4.3 3.2 3.3 3.7 4.3 5.2 6.5 6.9 7.1
127 94 47 18 14 9.9 7.7 6.9 6.1 5.7
113 77 36 15 11 9.0 8.0 6.5 5.1
104 68 30 11 8.3 6.4 5.1 4.3
95 60 24 8.5 6.4 5.1 4.3 3.4
87 53 21 7.1 5.3 4.4 3.6
83 47 17 6.1 4.4 3.6 3.1
78 42 15 5.2 3.7 3.1 2.6
73 38 12 4.3 3.2 2.4
69 34 9.9 3.8 3.5 2.2
65 32 9.0 3.3 2.4 2.0
62 29 8.0 3.0 2.1 1.9
59 26 7.1 2.6 1.9 1.8
56 24 6.3 2.4 1.8
53 22 5.6 2.1 1.8
"""

# R4: 180 deg column extrapolated (see module note)
_R4 = """
264 264 264 264 264 264 264 264 264 264 264 264 264 264 264 264 264 264 264 264
297 317 317 317 317 310 304 290 284 277 271 244 231 224 224 218 218 211 211 211
330 343 343 343 330 310 297 284 277 264 251 218 198 185 178 172 172 165 165 165
376 383 370 350 330 304 277 251 231 211 198 165 139 132 132 125 125 125 119 119
396 396 396 330 290 251 218 198 185 165 145 112 86 86 86 86 86 87 87 87
403 409 370 310 251 211 178 152 132 115 103 77 66 65 65 63 65 66 67 68
409 396 356 284 218 172 139 115 100 88 79 61 50 50 50 50 52 55 55 55
409 396 343 251 178 139 108 88 75 66 59 44 37 37 37 38 40 41 42 43
409 383 317 224 145 106 86 71 59 53 45 33 29 29 29 30 32 33 34 35
396 356 264 152 100 73 55 45 37 32 28 21 20 20 20 21 22 24 25 26
370 304 211 95 63 44 30 25 21 17 16 13 12 12 13 13 15 16 17 18
343 271 165 63 40 26 19 15 13 12 11 9.8 9.1 8.8 8.8 9.4 11 12 13 14
317 238 132 45 24 16 13 11 9.6 9.0 8.4 7.5 7.4 7.4 7.5 7.9 8.6 9.4 11 12.6
297 211 106 33 17 11 9.2 7.9 7.3 6.6 6.3 6.1 6.1 6.2 6.5 6.7 7.1 7.7 8.7 9.7
277 185 79 24 13 8.3 7.0 6.3 5.7 5.1 5.0 5.0 5.1 5.4 5.5 5.8 6.1 6.3 6.9 7.5
257 161 59 19 9.9 7.1 5.7 5.0 4.6 4.2
244 140 46 13 7.7 5.7 4.8 4.1 3.8
231 122 37 11 5.9 4.6 3.7 3.2
218 106 32 9.0 5.0 3.8 3.2 2.6
205 94 26 7.5 4.4 3.3 2.8
193 82 22 6.3 3.7 2.9 2.4
184 74 19 5.3 3.2 2.5 2.1
174 66 16 4.6 2.8 2.1
169 59 13 4.1 2.5 2.0
164 53 12 3.7 2.2 1.7
158 49 11 3.3 2.1 1.7
153 45 9.5 3.0 2.0 1.7
149 41 8.4 2.6 1.7
145 37 7.7 2.5 1.7
"""

DESCRIPTORS = {
    "R1": dict(Q0=0.10, S1=0.25, S2=1.53, label="R1 — mostly diffuse (concrete, light aggregate)"),
    "R2": dict(Q0=0.07, S1=0.58, S2=1.80, label="R2 — mixed (asphalt with >15 % light aggregate)"),
    "R3": dict(Q0=0.07, S1=1.11, S2=2.38, label="R3 — slightly specular (typical asphalt)"),
    "R4": dict(Q0=0.08, S1=1.55, S2=3.03, label="R4 — mostly specular (very smooth asphalt)"),
}


def _parse(block):
    rows = [ln.split() for ln in block.strip().splitlines()]
    assert len(rows) == len(TAN_E), len(rows)
    t = np.full((len(TAN_E), len(BETA)), np.nan)
    tabulated = np.zeros_like(t, dtype=bool)
    for i, r in enumerate(rows):
        vals = [float(v) for v in r]
        t[i, :len(vals)] = vals
        tabulated[i, :len(vals)] = True
        # hold the last tabulated value across the blank cells
        t[i, len(vals):] = vals[-1]
    return t * 1e-4, tabulated


class RTable:
    def __init__(self, name, table, tabulated=None, Q0=None, S1=None, S2=None, label=""):
        self.name = name
        self.r = np.asarray(table, float)
        self.tab = tabulated if tabulated is not None else np.ones_like(self.r, bool)
        self.T = TAN_E
        self.B = BETA
        self.label = label or name
        self.Q0 = Q0 if Q0 is not None else self.q0()
        self.S1 = S1
        self.S2 = S2

    def __call__(self, tan_e, beta):
        """Reduced luminance coefficient r (sr^-1), bilinear in tan(eps) and beta."""
        t = np.asarray(tan_e, float)
        b = np.abs(np.asarray(beta, float))
        b = np.where(b > 180.0, 360.0 - b, b)
        T, B, R = self.T, self.B, self.r
        it = np.clip(np.searchsorted(T, t, side="right") - 1, 0, len(T) - 2)
        ib = np.clip(np.searchsorted(B, b, side="right") - 1, 0, len(B) - 2)
        ft = np.clip((t - T[it]) / (T[it + 1] - T[it]), 0.0, 1.0)
        fb = np.clip((b - B[ib]) / (B[ib + 1] - B[ib]), 0.0, 1.0)
        r0 = R[it, ib] + ft * (R[it + 1, ib] - R[it, ib])
        r1 = R[it, ib + 1] + ft * (R[it + 1, ib + 1] - R[it, ib + 1])
        out = r0 + fb * (r1 - r0)
        return np.where(t > T[-1], 0.0, out)

    def q0(self):
        """Average luminance coefficient Q0 by numerical integration (CIE 144)."""
        # Q0 = (1/Omega0) * integral q dOmega over incidence directions up to tan e = 12
        n_e, n_b = 400, 181
        e_max = np.arctan(12.0)
        e = (np.arange(n_e) + 0.5) * e_max / n_e
        b = np.linspace(0, 180, n_b)
        EE, BB = np.meshgrid(e, b, indexing="ij")
        q = self(np.tan(EE), BB) / np.cos(EE) ** 3
        dO = np.sin(EE) * (e_max / n_e) * (np.pi / (n_b - 1))
        w = np.ones(n_b); w[0] = w[-1] = 0.5
        num = float((q * dO * w[None, :]).sum()) * 2
        den = float((dO * w[None, :]).sum()) * 2
        return num / den

    def to_dict(self):
        return dict(name=self.name, label=self.label, Q0=self.Q0, S1=self.S1, S2=self.S2,
                    tan_e=self.T.tolist(), beta=self.B.tolist(),
                    r=np.round(self.r * 1e4, 2).tolist())


_TABLES = {}


def get(name: str = "R3") -> RTable:
    name = (name or "R3").upper()
    if name not in _TABLES:
        src = {"R1": _R1, "R2": _R2, "R3": _R3, "R4": _R4}.get(name)
        if src is None:
            raise KeyError("Unknown road surface %s" % name)
        t, tab = _parse(src)
        d = DESCRIPTORS[name]
        _TABLES[name] = RTable(name, t, tab, d["Q0"], d["S1"], d["S2"], d["label"])
    return _TABLES[name]


def read_rtable(text: str, name: str = "custom") -> RTable:
    """Read a user r-table.

    Accepted: DIALux 'RTable.v1' (.rtb) or a plain grid with 29 rows of 20
    values (r x 10^4, rows tan e = 0..12, columns beta = 0..180).
    """
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if lines and lines[0].lower().startswith("rtable"):
        nt = int(float(lines[2]))
        T = [float(x) for x in lines[3:3 + nt]]
        nb = int(float(lines[3 + nt]))
        B = [float(x) for x in lines[4 + nt:4 + nt + nb]]
        vals = [float(x) for x in lines[4 + nt + nb:]]
        q0 = None
        if len(vals) == nt * nb + 1:
            q0 = vals[0]
            vals = vals[1:]
        arr = np.array(vals[:nt * nb]).reshape(nb, nt).T
        if not np.allclose(T, TAN_E) or not np.allclose(B, BETA):
            raise ValueError("Only the standard tan e / beta grid is supported.")
        scale = 1e-4 if arr.max() > 5 else 1.0
        return RTable(name, arr * scale, Q0=q0, label=name)
    nums = [float(x) for ln in lines for x in ln.replace(",", " ").split()]
    if len(nums) < 29 * 20:
        raise ValueError("Expected 29 x 20 values (r x 10^4).")
    arr = np.array(nums[:580]).reshape(29, 20) * 1e-4
    return RTable(name, arr, label=name)
