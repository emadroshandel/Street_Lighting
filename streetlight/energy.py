# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Energy performance (EN 13201-5:2015) and running cost.

PDI  D_P = P / sum(E_i A_i)                   W / (lx m2)      Formula (1)
AECI D_E = sum(P_j t_j) / A                    Wh / m2 / year   Formula (3)

The operating profile is a list of (power fraction, hours per year) plus the
quiescent (standby) power during the remaining hours of the year.
"""
from __future__ import annotations

import math
import re

HOURS_YEAR = 8760.0


def pdi_aeci(areas, system_power, profile=None, standby_W=0.0, length=None):
    """areas: list of dict(E_avg, area_m2) for the lit sub-areas.

    system_power: W of all luminaires (and devices) lighting those areas.
    profile: [(fraction, hours)] e.g. [(1.0, 2000), (0.5, 2100)] (bi-power).
    """
    profile = profile or [(1.0, 4100.0)]
    EA = sum(a["E_avg"] * a["area"] for a in areas)
    A = sum(a["area"] for a in areas)
    Dp = system_power / EA if EA > 0 else float("nan")
    on_hours = sum(h for _, h in profile)
    energy = sum(system_power * f * h for f, h in profile) + standby_W * max(HOURS_YEAR - on_hours, 0)
    De = energy / A if A > 0 else float("nan")
    return dict(PDI=Dp, AECI=De, area=A, EA=EA, energy_Wh=energy, kWh=energy / 1000.0,
                on_hours=on_hours, profile=profile, system_power=system_power)


def profile_from(kind="full", hours=4100.0, reduce_from=0.5, level=0.5):
    """Common operating profiles (EN 13201-5 Annex A)."""
    if kind == "full":
        return [(1.0, hours)]
    if kind == "bipower":
        return [(1.0, hours * (1 - reduce_from)), (level, hours * reduce_from)]
    if kind == "tripower":
        return [(1.0, hours * 0.35), (0.7, hours * 0.25), (level, hours * 0.40)]
    return [(1.0, hours)]


def summary(design_power_W, lit_areas, profile=None, standby_W=0.0, price=0.12, co2=0.55,
            years=20, discount=0.06, capex=0.0, maint=0.0):
    r = pdi_aeci(lit_areas, design_power_W, profile, standby_W)
    kwh = r["kWh"]
    cost = kwh * price
    ann = (1 - (1 + discount) ** -years) / discount if discount > 0 else years
    r.update(cost_year=cost, co2_t_year=kwh * co2 / 1000.0, npv=capex + (cost + maint) * ann,
             price=price, co2_factor=co2, years=years, discount=discount, capex=capex, maint=maint)
    return r


# CIE 154:2003 Table 3.1 (LLMF) and Table 3.2 (LSF) at 4, 6, 8, 10, 12 thousand operating hours
CIE154_HOURS = [4000.0, 6000.0, 8000.0, 10000.0, 12000.0]
CIE154_LLMF = {"HPS": [0.98, 0.97, 0.94, 0.91, 0.90], "MH": [0.82, 0.78, 0.76, 0.74, 0.73],
               "MV": [0.87, 0.83, 0.80, 0.78, 0.76], "LPS": [0.98, 0.96, 0.93, 0.90, 0.87],
               "CFL": [0.91, 0.88, 0.86, 0.85, 0.84], "FD": [0.95, 0.94, 0.93, 0.92, 0.91]}
CIE154_LSF = {"HPS": [0.98, 0.96, 0.94, 0.92, 0.89], "MH": [0.98, 0.97, 0.94, 0.92, 0.88],
              "MV": [0.93, 0.91, 0.87, 0.82, 0.76], "LPS": [0.92, 0.86, 0.80, 0.74, 0.62],
              "CFL": [0.98, 0.94, 0.90, 0.78, 0.50], "FD": [0.99, 0.99, 0.99, 0.98, 0.96]}
# CIE 154:2003 Table 3.3 (LMF) by optical compartment IP and pollution, at 1, 1.5, 2, 2.5, 3 years
CIE154_YEARS = [1.0, 1.5, 2.0, 2.5, 3.0]
CIE154_LMF = {
    "IP2X": {"high": [0.53, 0.48, 0.45, 0.43, 0.42], "medium": [0.62, 0.58, 0.56, 0.54, 0.53],
             "low": [0.82, 0.80, 0.79, 0.78, 0.78]},
    "IP5X": {"high": [0.89, 0.87, 0.84, 0.80, 0.76], "medium": [0.90, 0.88, 0.86, 0.84, 0.82],
             "low": [0.92, 0.91, 0.90, 0.89, 0.88]},
    "IP6X": {"high": [0.91, 0.90, 0.88, 0.85, 0.83], "medium": [0.92, 0.91, 0.89, 0.88, 0.87],
             "low": [0.93, 0.92, 0.91, 0.90, 0.90]},
}


def _interp(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for x0, x1, y0, y1 in zip(xs, xs[1:], ys, ys[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def ip_row(ip):
    """CIE 154 Table 3.3 row for an IP code: first digit 6 -> IP6X, 5 -> IP5X, lower -> IP2X (the only
    lower row of the table, so IP3X / IP4X are taken conservatively as IP2X)."""
    m = re.match(r"\s*IP\s*(\d)", str(ip).upper())
    d = int(m.group(1)) if m else 6
    return "IP6X" if d >= 6 else "IP5X" if d == 5 else "IP2X"


def maintenance_factor(lamp="LED", llmf=None, lsf=None, lmf=None, ip="IP66", pollution="medium",
                       interval_years=3.0, hours_year=4100.0, l_rating=(100000.0, 0.90),
                       design_life_h=100000.0, relamp_years=None, spot_replacement=True):
    """Overall maintenance factor fM = LLMF x LSF x LMF (CIE 154:2003).

    LLMF: LED from the declared lumen maintenance Lx at the rated hours (exponential), at the design
          life; discharge and fluorescent lamps from CIE 154 Table 3.1 at the group-replacement age
          (relamp_years x hours_year, interpolated between 4 000 and 12 000 h).
    LSF:  1.0 with spot replacement of failed lamps (EN 13201-3 advises not to include LSF then);
          otherwise CIE 154 Table 3.2 at the same age.  LED: 1.0.
    LMF:  CIE 154 Table 3.3 by optical-compartment IP and pollution at the cleaning interval (1-3 years).
    """
    notes = []
    lamp = str(lamp).upper()
    relamp_years = interval_years if relamp_years is None else float(relamp_years)
    age_h = relamp_years * hours_year
    if llmf is None:
        if lamp == "LED":
            hrs, x = l_rating
            if not (hrs > 0 and 0 < x <= 1):
                raise ValueError("LED lumen maintenance needs rated hours > 0 and an L-ratio between 0 and 1.")
            # exponential decay through (0, 1) and (hrs, x), evaluated at the design life
            llmf = math.exp(math.log(x) * design_life_h / hrs)
        elif lamp in CIE154_LLMF:
            llmf = _interp(CIE154_HOURS, CIE154_LLMF[lamp], age_h)
            if age_h > CIE154_HOURS[-1]:
                notes.append("lamps replaced after %.0f h: beyond CIE 154 Table 3.1 (12 000 h), the 12 000 h "
                             "value is used — take the manufacturer's data" % age_h)
        else:
            llmf = 0.80
            notes.append("no CIE 154 lumen-maintenance data for %s: 0.80 assumed — use the manufacturer's value"
                         % lamp)
    if lsf is None:
        if lamp == "LED" or spot_replacement:
            lsf = 1.0
        elif lamp in CIE154_LSF:
            lsf = _interp(CIE154_HOURS, CIE154_LSF[lamp], age_h)
        else:
            lsf = 0.92
            notes.append("no CIE 154 survival data for %s: LSF 0.92 assumed" % lamp)
    row = ip_row(ip)
    if lmf is None:
        tbl = CIE154_LMF[row]
        if pollution not in tbl:
            raise ValueError("Pollution category must be low, medium or high (CIE 154).")
        if interval_years > 3.0:
            notes.append("cleaning every %.1f years is beyond CIE 154 Table 3.3 (3 years): the 3-year value "
                         "is used and is optimistic" % interval_years)
        lmf = _interp(CIE154_YEARS, tbl[pollution], interval_years)
    if row == "IP2X" and lamp == "LED":
        notes.append("IP rating below IP5X: CIE 154 recommends at least IP5X optics; IEC 60364-7-714 "
                     "requires IP33 or better for external lighting equipment")
    return dict(fM=llmf * lsf * lmf, LLMF=llmf, LSF=lsf, LMF=lmf, interval_years=interval_years,
                relamp_years=relamp_years, ip_row=row, spot_replacement=bool(spot_replacement),
                notes=notes,
                note="CIE 154:2003 Tables 3.1-3.3; " + ("LED LLMF from the declared lumen maintenance"
                                                        if lamp == "LED" else
                                                        "LSF %s" % ("1 (spot replacement, EN 13201-3)"
                                                                    if spot_replacement else "Table 3.2"))
                + ("; " + "; ".join(notes) if notes else "") + ".")
