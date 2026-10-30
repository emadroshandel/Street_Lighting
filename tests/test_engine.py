# Street Lighting — engine tests.  Run:  python -m unittest discover -s tests -v
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
import json
import math
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from streetlight import (api, calc, classes, electrical, energy, optimize, photometry, road,  # noqa: E402
                         rtables, scheme, structural)
from streetlight.geometry import Luminaire  # noqa: E402


def _example():
    with open(os.path.join(os.path.dirname(HERE), "examples", "urban_street.json"), encoding="utf-8") as f:
        return json.load(f)


def iso(I=1000.0):
    return photometry.Photometry(name="iso", C=np.array([0.0, 360.0]), G=np.array([0.0, 180.0]),
                                 I=np.full((2, 2), I), lamp_flux=4 * math.pi * I)


class Photometry(unittest.TestCase):
    def test_point_source_illuminance(self):
        l = Luminaire(0, 0, 10, phot=iso())
        P = np.array([[0, 0, 0], [10, 0, 0], [0, 5, 0]], float)
        E = calc.horizontal_E([l], P)
        exp = [10.0, 1000 * (10 / math.sqrt(200)) / 200, 1000 * (10 / math.sqrt(125)) / 125]
        np.testing.assert_allclose(E, exp, rtol=1e-9)

    def test_flux_integration(self):
        self.assertAlmostEqual(iso().luminaire_flux / (4 * math.pi * 1000), 1.0, places=4)
        g = photometry.generic("type3", 12000.0)
        self.assertAlmostEqual(g.luminaire_flux, 12000.0, delta=12)

    def test_ldt_round_trip(self):
        g = photometry.generic("type4", 9000.0, 60.0)
        back = photometry.read_ldt(photometry.write_ldt(g))
        C = np.array([0, 30, 75, 120, 200, 300.0])
        G = np.array([0, 20, 45, 62.5, 70, 80.0])
        np.testing.assert_allclose(back.intensity(C, G), g.intensity(C, G), rtol=2e-3, atol=0.5)
        self.assertAlmostEqual(back.lamp_flux, 9000.0)

    def test_ies_reader_symmetry(self):
        txt = """IESNA:LM-63-2002
[TEST] synthetic
TILT=NONE
1 1000 1 3 2 1 2 0.5 0.3 0.1
1 1 50
0 45 90
0 90
100 80 10
200 160 20
"""
        ph = photometry.read_ies(txt)
        self.assertEqual(ph.symmetry, "quad")
        # quadrant symmetry: C=270 equals C=90, C=180 equals C=0
        self.assertAlmostEqual(float(ph.intensity(270, 45)), 160.0)
        self.assertAlmostEqual(float(ph.intensity(180, 45)), 80.0)


class RTables(unittest.TestCase):
    def test_s1_descriptor(self):
        for n in ("R1", "R2", "R3", "R4"):
            t = rtables.get(n)
            S1 = float(t(2.0, 0.0) / t(0.0, 0.0))
            self.assertAlmostEqual(S1, t.S1, delta=0.01, msg=n)


class StandardCalculation(unittest.TestCase):
    def setUp(self):
        self.ph = photometry.generic("type3", 12000.0)
        self.sec = dict(elements=[dict(kind="footway", width=2.0, cls="P4"),
                                  dict(kind="carriageway", width=7.0, lanes=2, cls="M4", surface="R3"),
                                  dict(kind="footway", width=2.0, cls="P4")])
        self.rows = optimize.make_rows("single_left", optimize.pole_lines(self.sec), 11, 0, 10, "g")

    def test_grid_counts(self):
        self.assertEqual(calc.n_long(25), 10)
        self.assertEqual(calc.n_long(40.5), 14)
        self.assertEqual(calc.n_trans(2.0), 3)
        self.assertEqual(calc.n_trans(10.0), 7)

    def test_route_reproduces_standard(self):
        S = 40.5
        std = calc.evaluate(self.sec, self.rows, S, lambda k: self.ph, 0.8, dict(display=False))
        a = std["areas"][1]
        rt = road.Route(road.from_segments([dict(type="straight", length=600)]),
                        road.Profile([(0, 0), (600, 0)]), self.sec)
        rt.ref_y = 0.0
        poles = road.layout(rt, dict(S=S, rows=self.rows))
        res = scheme.evaluate_route(rt, poles, lambda k: self.ph, 0.8, dict(display=False))
        sp = res["areas"][1]["spans"][6]
        self.assertAlmostEqual(sp["L_avg"], a["L_avg"], places=6)
        self.assertAlmostEqual(sp["U0_L"], a["U0_L"], places=6)
        self.assertAlmostEqual(sp["Ul"], a["Ul"], places=6)
        self.assertAlmostEqual(sp["E_avg"], a["E_avg"], places=6)

    def test_flux_linearity(self):
        a = calc.evaluate(self.sec, self.rows, 35, lambda k: self.ph, 0.8, dict(display=False, ti=False))
        rows2 = [dict(r, flux=0.5) for r in self.rows]
        b = calc.evaluate(self.sec, rows2, 35, lambda k: self.ph, 0.8, dict(display=False, ti=False))
        self.assertAlmostEqual(b["areas"][1]["L_avg"], 0.5 * a["areas"][1]["L_avg"], places=9)
        self.assertAlmostEqual(b["areas"][1]["U0_L"], a["areas"][1]["U0_L"], places=9)

    def test_classes(self):
        self.assertEqual(classes.M_CLASSES["M3"][0], 1.0)
        self.assertEqual(classes.P_CLASSES["P4"][:2], (5.0, 1.0))
        self.assertEqual(classes.select_class("M", dict(speed="moderate", volume="moderate", composition="mixed",
                                                        separation="no", junctions="moderate", parked="absent",
                                                        ambient="moderate", navigation="easy"))["cls"], "M5")


class Electrical(unittest.TestCase):
    def test_single_phase_drop(self):
        cfg = dict(electrical.DEFAULT, three_phase=False, pole_cable_extra=0.0, _heights=[0.0])
        fc = electrical.feeder_calc([2300.0 * 0.95], [100.0], 10, cfg, phases=[0])
        I = 10.0
        R = 0.0225 / 10 * 100
        X = 0.08e-3 * 100
        exp = 2 * (R * 0.95 + X * math.sin(math.acos(0.95))) * I / 230 * 100
        self.assertAlmostEqual(fc["du_max"], exp, places=2)


class Structural(unittest.TestCase):
    def test_exposure_category_II(self):
        self.assertAlmostEqual(structural.ce(10.0, "II"), 2.35, delta=0.01)


class Api(unittest.TestCase):
    def test_example_project(self):
        with open(os.path.join(os.path.dirname(HERE), "examples", "urban_street.json")) as f:
            pr = json.load(f)
        pr["search"]["heights"] = [10.0, 11.0]
        pr["search"]["overhangs"] = [0.0]
        pr["search"]["tilts"] = [10.0]
        o = api.dispatch("/api/optimize", dict(project=pr))
        self.assertTrue(o["candidates"])
        self.assertTrue(o["best"]["ok"])
        json.dumps(api.clean(o))


class StandardsRegression(unittest.TestCase):
    """Checks added in the pre-release review against the standards' text."""

    def test_en40_beta_metal_figure1(self):
        # EN 40-3-1:2013 5.2.4 NOTE: beta = 1.00240 - 0.00500 T^4 + 0.05144 T^3 - 0.22793 T^2 + 0.67262 T
        for T, fig in [(0.0, 1.0), (0.5, 1.29), (1.0, 1.49), (1.5, 1.645), (2.0, 1.765), (3.5, 2.03)]:
            self.assertAlmostEqual(structural.beta_metal(T), fig, delta=0.015)
        self.assertAlmostEqual(structural.CS_25Y ** 2, 0.92, places=9)      # 5.2.2, 25-year return period

    def test_ti_screening_plane_is_transverse(self):
        # a luminaire 10 m to the side, 8.5 m above the eye, 22 m ahead: inside a 20 deg cone
        # measured with the horizontal distance, but above the transverse 20 deg plane -> excluded
        l = Luminaire(22.0, 10.0, 10.0, phot=iso())
        Lv, n = calc.veiling_luminance([l], (0.0, 0.0, 1.5))
        self.assertEqual(n, 0)
        l2 = Luminaire(24.0, 10.0, 10.0, phot=iso())                       # 8.5 / 24 < tan 20
        self.assertEqual(calc.veiling_luminance([l2], (0.0, 0.0, 1.5))[1], 1)

    def test_ti_low_mounting_observer(self):
        self.assertEqual(calc.observer_start(1.0), (-60.0, False))           # CIE 140:2019 8.4
        x, screen = calc.observer_start(10.0)
        self.assertAlmostEqual(x, -2.75 * 8.5)
        self.assertTrue(screen)

    def _rei(self, elements):
        edges = calc.element_edges(elements)
        ei = [e["kind"] for e in elements].index("carriageway")
        l = Luminaire(0.0, edges[ei][0] + 1.0, 10.0, phot=iso())
        return calc._rei([l], elements, edges, ei, np.array([0.0, 5.0]), 1.0, 3.5)

    def test_rei_not_beside_classed_area(self):
        r = self._rei([dict(kind="footway", width=2, cls="P4"), dict(kind="carriageway", width=7, lanes=2),
                       dict(kind="verge", width=3)])
        self.assertIsNone(r["low"])                                           # EN 13201-2 Table 1 note d
        self.assertIsNotNone(r["high"])
        self.assertIn("own lighting class", r["skipped"]["low"])

    def test_rei_narrow_median_is_one_carriageway(self):
        r = self._rei([dict(kind="verge", width=3), dict(kind="carriageway", width=7, lanes=2),
                       dict(kind="median", width=4), dict(kind="carriageway", width=7, lanes=2)])
        self.assertIsNone(r["high"])                                          # EN 13201-3 8.6
        self.assertIsNotNone(r["low"])

    def test_damaged_photometric_files(self):
        for name, text in [("a.ies", "IESNA:LM-63-2002\nTILT=NONE\n1 2 3"), ("a.ldt", "x\n" * 50)]:
            with self.assertRaises(ValueError):
                photometry.read_any(text, name)

    def test_electrical_input_validation(self):
        with self.assertRaises(ValueError):
            electrical._validate(dict(electrical.DEFAULT, U0=0))
        with self.assertRaises(ValueError):
            electrical._validate(dict(electrical.DEFAULT, max_pillars=0))


class SecondReferenceCheck(unittest.TestCase):
    """Spot values from the standards and the worked example named in each test."""

    def test_en40_exposure_table2(self):
        # EN 40-3-1:2013 Table 2
        for (cat, z), v in {("I", 20): 3.21, ("II", 20): 2.81, ("III", 20): 2.28, ("IV", 20): 1.72,
                            ("I", 1): 1.88, ("II", 3): 1.80, ("III", 7): 1.63, ("IV", 10): 1.56,
                            ("III", 12): 1.91, ("II", 6): 2.04}.items():
            self.assertAlmostEqual(structural.ce(z, cat), v, delta=0.006, msg=(cat, z))

    def test_en40_shape_coefficient_figure3(self):
        sc = structural.shape_coefficient
        self.assertAlmostEqual(sc(1.5e5), 1.2)
        self.assertAlmostEqual(sc(4e5), 0.5)
        self.assertAlmostEqual(sc(1e6), 0.6)
        self.assertAlmostEqual(sc(3e5), 0.85)
        self.assertAlmostEqual(sc(5e5, "octagonal_sharp"), 1.3)

    def test_en40_3_3_closed_section_hk_example(self):
        # worked example of an independent EN 40-3-3 column design report: CHS 76 x 4, fy 310, gamma_m 1.0 -> Mup 6.43 kNm, Tu 5.05 kNm
        Mup, Tu, f = structural.closed_resistance(0.076, 0.004, 310.0, gm=1.0)
        self.assertAlmostEqual(Mup / 1e3, 6.43, delta=0.01)
        self.assertAlmostEqual(Tu / 1e3, 5.05, delta=0.01)
        self.assertAlmostEqual(f["eps"], 0.35, delta=0.01)
        # beta of the same report: T = 0.54 s -> 1.307, T = 0.13 s -> 1.086
        self.assertAlmostEqual(structural.beta_metal(0.54), 1.307, delta=0.002)
        self.assertAlmostEqual(structural.beta_metal(0.13), 1.086, delta=0.002)

    def test_en40_3_3_factors(self):
        self.assertEqual(structural.phi1(0.8), 1.0)
        self.assertAlmostEqual(structural.phi1(1.5), (0.8 / 1.5) ** 0.35)
        self.assertIsNone(structural.phi1(2.1))
        self.assertAlmostEqual(structural.phi5(0.0, 0.0), 10.0)          # Figure 4 at theta 0, R/L 0

    def test_cie154_tables(self):
        mf = energy.maintenance_factor
        r = mf("HPS", relamp_years=8000 / 4100, hours_year=4100, interval_years=2.0, ip="IP66", pollution="high")
        self.assertAlmostEqual(r["LLMF"], 0.94, places=3)               # Table 3.1, S at 8 000 h
        self.assertEqual(r["LSF"], 1.0)                                  # spot replacement
        self.assertAlmostEqual(r["LMF"], 0.88, places=3)                # Table 3.3, IP6X high, 2 years
        r = mf("MV", relamp_years=10000 / 4100, hours_year=4100, spot_replacement=False, ip="IP54",
               interval_years=1.0, pollution="low")
        self.assertAlmostEqual(r["LSF"], 0.82, places=3)                # Table 3.2, Q at 10 000 h
        self.assertAlmostEqual(r["LMF"], 0.92, places=3)                # IP5X low, 1 year
        self.assertEqual(energy.ip_row("IP44"), "IP2X")
        self.assertAlmostEqual(mf("LED", ip="IP23", pollution="medium", interval_years=3.0)["LMF"], 0.53)

    def test_iec60228_resistances(self):
        # IEC 60228:2023 Table 4, class 2 plain copper / aluminium, ohm/km at 20 C
        self.assertEqual(electrical.R20["Cu"][16], 1.15)
        self.assertEqual(electrical.R20["Cu"][185], 0.0991)
        self.assertEqual(electrical.R20["Al"][70], 0.443)

    def test_iec60269_gg_gates(self):
        tc = electrical.trip_current
        self.assertEqual(tc("gG", 32, 5.0), 150.0)       # IEC 60269-1 Table 3, Imax(5 s)
        self.assertEqual(tc("gG", 63, 5.0), 320.0)
        self.assertEqual(tc("gG", 10, 5.0), 46.5)        # IEC 60269-2-1 Table III
        self.assertEqual(tc("gG", 16, 0.4), 150.0)       # Imax(0.1 s) as the guaranteed 0.4 s bound
        self.assertEqual(tc("gG", 13, 5.0), 65.0)        # between ratings -> next larger (16 A)
        self.assertEqual(tc("gG", 16, 0.4, gg_k04=6.0), 96.0)
        self.assertEqual(tc("C", 16, 0.4), 160.0)

    def test_iec60364_7_714_notes(self):
        notes = electrical.installation_notes([dict(H=1.0), dict(H=10.0)])
        self.assertTrue(any("2.8 m" in n for n in notes))
        self.assertTrue(any("IP33" in n for n in notes))


class CIE140Benchmark(unittest.TestCase):
    """CIE 140:2019 Formula (26), file orientation, and Annex B when the test data are present."""

    def test_formula26_age_factor_on_5_over_theta2_only(self):
        ph = iso(1000.0)
        l = Luminaire(300.0, 0.0, 1.5 + 300.0 * math.tan(math.radians(0.2)), phot=ph)
        eye = (0.0, 0.0, 1.5)
        Lv, n = calc.veiling_luminance([l], eye, age=60.0, screen=False)
        self.assertEqual(n, 1)
        v = np.array(l.pos) - np.array(eye)
        d = np.linalg.norm(v)
        sight = np.array([math.cos(math.radians(-1)), 0.0, math.sin(math.radians(-1))])
        ct = v @ sight / d
        th = math.degrees(math.acos(ct))
        self.assertTrue(0.1 < th <= 1.5)
        E = 1000.0 * ct / d ** 2
        self.assertAlmostEqual(Lv, E * (10 / th ** 3 + 5 * (1 + (60 / 62.5) ** 4) / th ** 2), places=9)

    def test_road_file_with_along_road_axis_on_c90_is_turned(self):
        ref = photometry.generic("type3", 10000.0)
        self.assertLess(ref.mirror_deviation(90), 0.01)
        turned = ref.rotated(-90.0)                         # along-road axis now on C90-C270
        self.assertLess(turned.mirror_deviation(0), 0.01)
        back, done = turned.orient_for_road()
        self.assertTrue(done)
        g = np.arange(0, 90, 7.5)
        for c in (0, 35, 90, 160, 270):
            # turned by +90: the street side may come out on C90 or C270, both are handled later
            a = ref.intensity(np.full_like(g, c), g)
            b = back.intensity(np.full_like(g, c), g)
            b2 = back.intensity(np.full_like(g, c + 180.0), g)
            self.assertTrue(np.allclose(a, b, rtol=1e-6, atol=1e-6) or np.allclose(a, b2, rtol=1e-6, atol=1e-6))
        same, done = ref.orient_for_road()
        self.assertFalse(done)
        self.assertIs(same, ref)
        rot, done = iso().orient_for_road()                 # rotationally symmetric: left alone
        self.assertFalse(done)

    def test_annex_b(self):
        z = os.environ.get("CIE140_TEST_DATA") or os.path.join(
            os.path.dirname(HERE), "References", "Ref2ndCheck", "957_TC_4-15_Test_Data.zip")
        if not os.path.isfile(z):
            self.skipTest("CIE 140 test data zip not present")
        from streetlight import benchmark
        for fmt in ("ldt", "ies"):
            for r in benchmark.run(z, fmt):
                low = r["H"] <= 4.0
                for c in r["values"]:
                    q, dv = c["q"], c["calc"] - c["ref"]
                    msg = "%s situation %d lane %s %s: %.4f vs %.4f" % (fmt, r["situation"], c["lane"], q,
                                                                    c["calc"], c["ref"])
                    if q in ("L", "Uo", "Ul", "REI", "Uh"):
                        self.assertLessEqual(abs(dv), 0.02, msg)
                    elif q == "Eh":
                        self.assertLessEqual(abs(c["dev_pct"]), 1.5 if low else 0.6, msg)
                    else:                                    # TI, Lv
                        self.assertLessEqual(abs(c["dev_pct"]), 6.0 if low else 2.0, msg)


class RouteLayoutRegressions(unittest.TestCase):
    def test_crossing_does_not_stack_a_third_column(self):
        """A regular column close to a crossing takes the crossing luminaire's place (was: 3 columns within 2 m)."""
        import copy
        pr = _example()
        out = api.optimize_ep(dict(project=pr))
        c = copy.deepcopy([c for c in out["candidates"] if c["arrangement"] == "single_left"][0])
        c["S"] = 25.5
        for r in c["rows"]:
            r.update(height=9.0, overhang=0.5, tilt=5.0)
        poles = road.layout(api._route(pr), c, (pr.get("route") or {}).get("layout"))
        for side in {round(p["y"], 2) for p in poles}:
            ss = sorted(p["s"] for p in poles if round(p["y"], 2) == side)
            gaps = [b - a for a, b in zip(ss, ss[1:])] or [99.0]
            self.assertGreater(min(gaps), 5.0, "columns %.1f m apart on line y = %.2f" % (min(gaps), side))
        near = [p for p in poles if abs(p["s"] - 120.0) < 3.0]
        self.assertEqual(len(near), 2)                       # one each side, before the crossing

    def _example_layout(self, change):
        import copy
        with open(os.path.join(os.path.dirname(HERE), "examples", "urban_street.json"), encoding="utf-8") as f:
            pr = json.load(f)
        cand = api.optimize_ep(dict(project=copy.deepcopy(pr)))["candidates"][0]
        change(pr)
        return road.layout(api._route(pr), cand, (pr.get("route") or {}).get("layout"))

    def test_column_left_in_no_pole_zone_is_reported(self):
        poles = self._example_layout(
            lambda pr: pr["route"]["features"].update(no_pole=[dict(s0=0, s1=10000, reason="test")]))
        self.assertTrue(poles and all(p.get("conflict") for p in poles))

    def test_overhead_line_too_low_is_reported_not_hidden(self):
        poles = self._example_layout(lambda pr: pr["route"]["features"].update(
            overhead_lines=[dict(s0=0, s1=10000, height=3.0)]))
        self.assertTrue(all(p["H"] >= road.MIN_MOUNTING_HEIGHT for p in poles))
        self.assertTrue(all(p.get("conflict") for p in poles))

    def test_route_check_fails_on_conflicting_columns(self):
        import copy
        with open(os.path.join(os.path.dirname(HERE), "examples", "urban_street.json"), encoding="utf-8") as f:
            pr = json.load(f)
        cand = api.optimize_ep(dict(project=copy.deepcopy(pr)))["candidates"][0]
        pr["route"]["features"]["no_pole"] = [dict(s0=0, s1=10000, reason="test")]
        out = api.route_ep(dict(project=pr, candidate=cand, refine=False, auto_tilt=False))
        self.assertFalse(out["ok"])
        self.assertFalse([c for c in out["checks"] if c["name"] == "Column positions"][0]["ok"])

    def test_classed_strip_needs_a_width(self):
        with open(os.path.join(os.path.dirname(HERE), "examples", "urban_street.json"), encoding="utf-8") as f:
            pr = json.load(f)
        pr["section"]["elements"][2]["width"] = 0
        with self.assertRaises(ValueError):
            api.optimize_ep(dict(project=pr))


class SearchManyLuminaires(unittest.TestCase):
    def _project(self, n, full=False):
        import copy
        pr = _example()
        base = pr["luminaires"]["led80"]
        pr["luminaires"] = {}
        for i in range(n):
            L = copy.deepcopy(base)
            L["name"] = "LED %d" % i
            L["lamp_flux"] = base["lamp_flux"] * (1 + 0.06 * (i - 2))
            L["power"] = base["power"] * (1.0 if i == 3 else 1.12)       # L3 is the efficient one
            pr["luminaires"]["L%d" % i] = L
        pr["search"] = dict(phots=list(pr["luminaires"]), heights=[8, 10], overhangs=[0, 1], tilts=[0, 5],
                            arrangements=["single_left", "staggered"], full=full)
        return pr

    def test_quick_pass_then_full_search_of_three(self):
        auto = api.optimize_ep(dict(project=self._project(5)))
        self.assertEqual(auto["mode"], "screened")
        self.assertEqual(len(auto["screening"]), 5)
        self.assertEqual(sum(x["searched"] for x in auto["screening"]), 3)
        self.assertEqual(auto["candidates"][0]["phot"], "L3")
        full = api.optimize_ep(dict(project=self._project(5, full=True)))
        self.assertEqual(full["mode"], "full")
        self.assertEqual(full["screening"], [])
        self.assertEqual({c["phot"] for c in full["candidates"]} >= {"L3"}, True)
        top = lambda o: (o["candidates"][0]["phot"], o["candidates"][0]["arrangement"], o["candidates"][0]["H"],
                         o["candidates"][0]["S"])
        self.assertEqual(top(auto), top(full))

    def test_every_luminaire_gets_its_own_budget(self):
        o = api.optimize_ep(dict(project=self._project(3)))
        self.assertEqual(o["mode"], "full")
        found = {c["phot"] for c in o["candidates"]} | {x["phot"] for x in o["no_design"]}
        self.assertEqual(found, {"L0", "L1", "L2"})
        self.assertEqual(o["incomplete"], [])


class ServerSafety(unittest.TestCase):
    def test_only_public_files_are_served(self):
        sys.path.insert(0, os.path.dirname(HERE))
        import server
        pub = server.Handler._public_path
        self.assertIsNotNone(pub("/web/index.html"))
        self.assertIsNotNone(pub("/examples/urban_street.json"))
        for bad in ["/References/x.pdf", "/../etc/passwd", "/web/../server.py", "/LICENSE",
                    "/_work/a.tgz", "/streetlight/../tests/test_engine.py",
                    "/../" + os.path.basename(os.path.dirname(HERE)) + "2/x"]:
            self.assertIsNone(pub(bad), bad)


if __name__ == "__main__":
    unittest.main()
