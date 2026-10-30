# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""CIE 140:2019 Annex B — accuracy test of road lighting software.

The seven test situations of Table B.1 / Figure B.1 are run through the
engine and compared with the benchmark values of Table B.3.  The luminous
intensity tables and the R3 r-table come from CIE's test data set
957_TC_4-15_Test_Data.zip, which is not distributed with this program;
download it from CIE and pass its path:

    python -m streetlight.benchmark path/to/957_TC_4-15_Test_Data.zip [ldt|ies]

The zip is read in place (nothing is extracted).
"""
from __future__ import annotations

import sys
import zipfile

import numpy as np

from . import calc, photometry, rtables

# Table B.3: per observer lane (L, Uo, Ul, fTI %, Lv) and per situation (REI, Eh, Uh)
TABLE_B3 = {
    1: ([(0.26, 0.14, 0.56, 141, 0.877), (0.26, 0.15, 0.64, 49.7, 0.314)], (0.32, 2.50, 0.28)),
    2: ([(0.26, 0.35, 0.33, 101, 0.636), (0.26, 0.32, 0.33, 99, 0.626)], (0.47, 2.50, 0.32)),
    3: ([(0.55, 0.52, 0.68, 11.5, 0.130), (0.60, 0.54, 0.70, 11.3, 0.138)], (0.64, 7.80, 0.34)),
    4: ([(0.88, 0.54, 0.53, 13.8, 0.228), (0.87, 0.51, 0.53, 13.8, 0.227)], (0.61, 12.0, 0.49)),
    5: ([(0.44, 0.45, 0.79, 11.0, 0.105), (0.42, 0.57, 0.71, 10.4, 0.095), (0.41, 0.67, 0.75, 7.10, 0.063)],
        (0.76, 7.00, 0.28)),
    6: ([(1.17, 0.49, 0.62, 11.5, 0.239), (1.30, 0.49, 0.72, 8.00, 0.181)], (0.67, 16.2, 0.50)),
    7: ([(0.53, 0.45, 0.84, 15.6, 0.173), (0.58, 0.46, 0.91, 10.6, 0.127)], (0.62, 7.00, 0.50)),
}
# CIE lane 1 is the left-hand lane of Figure B.1.  In the model below the first row of
# luminaires is at low y; for these situations CIE's lane 1 is the lane at high y.
REVERSED_LANES = {2, 5, 6}
FM = 0.80          # Annex B: maintenance factor
AGE = 23.0         # Annex B: observer age
SURFACE = "CIE140-R3"


def _verge(w=20.0):
    return dict(kind="verge", width=w)


def _cw(w, n):
    return dict(kind="carriageway", width=w, lanes=n, surface=SURFACE)


def situation(k):
    """(section, rows, S, index of the relevant carriageway) for test situation k (Table B.1)."""
    if k in (1, 2, 3, 4, 7):
        W, n, H, T, tilt, S = {1: (10.0, 2, 4.0, 2.0, 0.0, 20.0), 2: (10.0, 2, 4.0, 2.0, 0.0, 20.0),
                               3: (7.5, 2, 10.0, 0.0, 5.0, 45.0), 4: (7.0, 2, 8.0, 0.0, 5.0, 35.0),
                               7: (8.0, 2, 10.0, 0.0, 5.0, 40.0)}[k]

        def row(y, side, ph=0.0):
            return dict(y=y, side=side, overhang=T, height=H, tilt=tilt, phase=ph, phot=k)
        sec = dict(elements=[_verge(), _cw(W, n), _verge()])
        if k in (2, 4):
            # staggered: consecutive luminaires S apart on opposite sides, i.e. 2S along one row
            return sec, [row(20.0, +1), row(20.0 + W, -1, 0.5)], 2 * S, 1
        return sec, [row(20.0, +1)], S, 1                  # single-sided
    if k == 5:
        # opposite, dual carriageway 10.5 m (3 lanes) + 1.5 m central reservation + 10.5 m
        def row(y, side):
            return dict(y=y, side=side, overhang=0.0, height=12.0, tilt=5.0, phase=0.0, phot=k)
        el = [_verge(), _cw(10.5, 3), dict(kind="median", width=1.5), _cw(10.5, 3), _verge()]
        return dict(elements=el), [row(20.0, +1), row(42.5, -1)], 54.0, 1
    if k == 6:
        # twin brackets at 180 deg on the centre of a 6 m central reservation; the luminaire
        # serving the relevant carriageway is 2.25 m outside its edge (T = -2.25 m)
        def row(side):
            return dict(y=30.0, side=side, overhang=0.75, height=18.0, tilt=5.0, phase=0.0, phot=k)
        el = [_verge(), _cw(7.0, 2), dict(kind="median", width=6.0), _cw(7.0, 2), _verge()]
        return dict(elements=el), [row(-1), row(+1)], 75.0, 1
    raise ValueError("CIE 140 Annex B has situations 1 to 7")


def read_cie_rtable(text: str) -> rtables.RTable:
    """CIE r-table file (R3-TAB.dat): header, n tan e values, n beta values, Q0, then
    r / Q0 x 10^4 column by column (beta outer, tan e inner)."""
    tok = [t.strip() for t in text.replace("\n", "\r").split("\r")]
    tok = [t for t in tok if t and t != "\x1a"]
    i = next(j for j, t in enumerate(tok) if t.isdigit())
    nt = int(tok[i]); T = [float(x) for x in tok[i + 1:i + 1 + nt]]; i += 1 + nt
    nb = int(tok[i]); B = [float(x) for x in tok[i + 1:i + 1 + nb]]; i += 1 + nb
    q0 = float(tok[i]); i += 1
    vals = np.array([float(x) for x in tok[i:i + nt * nb]])
    if not (np.allclose(T, rtables.TAN_E) and np.allclose(B, rtables.BETA)):
        raise ValueError("unexpected r-table grid")
    r = vals.reshape(nb, nt).T * q0 * 1e-4
    return rtables.RTable(SURFACE, r, Q0=q0, label="CIE 140 test data R3")


def run(zip_path: str, fmt: str = "ldt"):
    """Evaluate the seven situations; returns a list of per-situation dicts."""
    folder, ext = {"ldt": ("EULUMDAT", ".ldt"), "ies": ("IESNA", ".ies")}[fmt]
    with zipfile.ZipFile(zip_path) as z:
        names = {n.split("/")[-1].lower() + "|" + n.split("/")[-2].upper(): n
                 for n in z.namelist() if n.count("/") >= 1 and not n.endswith("/")}

        def read(fname, sub):
            return z.read(names[fname.lower() + "|" + sub.upper()]).decode("latin-1")
        rtables._TABLES[SURFACE] = read_cie_rtable(read("R3-TAB.dat", "Road Surface Data"))
        out = []
        for k in range(1, 8):
            ph = photometry.read_any(read("Sit%d%s" % (k, ext), folder), "Sit%d%s" % (k, ext))
            sec, rows, S, idx = situation(k)
            res = calc.evaluate(sec, rows, S, lambda key, ph=ph: ph, fM=FM,
                                options=dict(display=False, trees=False, age=AGE))
            a = [x for x in res["areas"] if x["index"] == idx][0]
            obs = a["observers"][::-1] if k in REVERSED_LANES else a["observers"]
            lanes, (rei, eh, uh) = TABLE_B3[k]
            cmp = []
            for j, (o, ref) in enumerate(zip(obs, lanes)):
                for name, v, r in zip(("L", "Uo", "Ul", "TI", "Lv"),
                                      (o["L_avg"], o["U0"], o["Ul"], o["TI"], o["Lv"]), ref):
                    cmp.append(dict(lane=j + 1, q=name, calc=float(v), ref=float(r)))
            for name, v, r in (("REI", a["REI"]["value"], rei), ("Eh", a["E_avg"], eh), ("Uh", a["U0_E"], uh)):
                cmp.append(dict(lane=None, q=name, calc=float(v), ref=float(r)))
            for c in cmp:
                c["dev_pct"] = (c["calc"] - c["ref"]) / c["ref"] * 100.0
                c["printed_match"] = _printed(c["q"], c["calc"]) == c["ref"]
            out.append(dict(situation=k, H=rows[0]["height"], values=cmp))
    return out


def _printed(q, v):
    """Round as Table B.3 prints the quantity."""
    if q in ("TI", "Eh"):
        return float("%.3g" % v)
    return round(v, 3 if q == "Lv" else 2)


def report(results) -> str:
    lines = ["CIE 140:2019 Annex B benchmark", ""]
    n = sum(len(r["values"]) for r in results)
    m = sum(c["printed_match"] for r in results for c in r["values"])
    for r in results:
        lines.append("Situation %d (H = %g m)" % (r["situation"], r["H"]))
        for c in r["values"]:
            lines.append("  %-6s %-4s calc %8.3f   ref %8.3f   %+5.1f %%%s" % (
                "lane %d" % c["lane"] if c["lane"] else "", c["q"], c["calc"], c["ref"], c["dev_pct"],
                "" if c["printed_match"] else "   *"))
    worst = max(abs(c["dev_pct"]) for r in results for c in r["values"])
    lines += ["", "%d of %d values equal Table B.3 at its printed precision (* = differs); "
              "largest deviation %.1f %%." % (m, n, worst)]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(report(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ldt")))
