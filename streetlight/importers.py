# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Import of road centrelines and profiles.

* DXF (ASCII): LWPOLYLINE, POLYLINE/VERTEX (2D and 3D), LINE chains
* GeoJSON: LineString / MultiLineString (lon, lat[, elevation])
* KML / KMZ text: <LineString><coordinates>
* GPX: track or route points with elevation
* CSV / text: x,y[,z] in metres, or lat,lon[,z], or chainage,z (profile)

Geographic coordinates are projected to local metres with a transverse
Mercator approximation about the first point (adequate for a few km).
"""
from __future__ import annotations

import json
import math
import re

R_EARTH = 6378137.0


def _project(lonlat):
    lon0, lat0 = lonlat[0][0], lonlat[0][1]
    c = math.cos(math.radians(lat0))
    out = []
    for p in lonlat:
        x = math.radians(p[0] - lon0) * R_EARTH * c
        y = math.radians(p[1] - lat0) * R_EARTH
        out.append([x, y] + ([float(p[2])] if len(p) > 2 and p[2] is not None else []))
    return out, dict(lon0=lon0, lat0=lat0)


def _longest(lines):
    def L(l):
        return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(l, l[1:]))
    lines = [l for l in lines if len(l) >= 2]
    if not lines:
        raise ValueError("No polyline with at least two points was found.")
    lines.sort(key=L, reverse=True)
    return lines


def read_dxf(text, scale=1.0):
    lines = text.replace("\r", "").split("\n")
    pairs = []
    for i in range(0, len(lines) - 1, 2):
        try:
            pairs.append((int(lines[i].strip()), lines[i + 1].strip()))
        except ValueError:
            continue
    polys, cur, ent = [], None, None
    vx = {}
    i = 0
    segs = []
    while i < len(pairs):
        code, val = pairs[i]
        if code == 0:
            if ent == "LWPOLYLINE" and cur:
                polys.append(cur)
            if ent == "VERTEX" and "x" in vx and cur is not None:
                cur.append([vx["x"], vx["y"]] + ([vx["z"]] if "z" in vx else []))
            if ent == "LINE" and len(vx) >= 4:
                segs.append(([vx["x"], vx["y"]], [vx["x2"], vx["y2"]]))
            if val == "SEQEND" and cur:
                polys.append(cur)
                cur = None
            ent = val
            vx = {}
            if val == "LWPOLYLINE":
                cur = []
            elif val == "POLYLINE":
                cur = []
        else:
            if ent == "LWPOLYLINE":
                if code == 10:
                    cur.append([float(val) * scale, 0.0])
                elif code == 20 and cur:
                    cur[-1][1] = float(val) * scale
            elif ent in ("VERTEX", "LINE"):
                if code == 10:
                    vx["x"] = float(val) * scale
                elif code == 20:
                    vx["y"] = float(val) * scale
                elif code == 30:
                    vx["z"] = float(val) * scale
                elif code == 11:
                    vx["x2"] = float(val) * scale
                elif code == 21:
                    vx["y2"] = float(val) * scale
        i += 1
    if ent == "LWPOLYLINE" and cur:
        polys.append(cur)
    # chain LINE entities
    if segs:
        chain = [list(segs[0][0]), list(segs[0][1])]
        rest = segs[1:]
        changed = True
        while rest and changed:
            changed = False
            for k, (a, b) in enumerate(rest):
                if math.hypot(a[0] - chain[-1][0], a[1] - chain[-1][1]) < 1e-3:
                    chain.append(list(b)); rest.pop(k); changed = True; break
                if math.hypot(b[0] - chain[-1][0], b[1] - chain[-1][1]) < 1e-3:
                    chain.append(list(a)); rest.pop(k); changed = True; break
        polys.append(chain)
    lines = _longest(polys)
    return dict(points=lines[0], alternatives=len(lines) - 1, source="DXF",
                has_z=any(len(p) > 2 for p in lines[0]))


def read_geojson(text):
    g = json.loads(text)
    lines = []

    def walk(o):
        t = o.get("type")
        if t == "FeatureCollection":
            for f in o["features"]:
                walk(f)
        elif t == "Feature":
            walk(o["geometry"])
        elif t == "LineString":
            lines.append(o["coordinates"])
        elif t == "MultiLineString":
            lines.extend(o["coordinates"])
        elif t == "GeometryCollection":
            for x in o["geometries"]:
                walk(x)
    walk(g)
    pts = _longest(lines)[0]
    proj, origin = _project(pts)
    return dict(points=proj, origin=origin, source="GeoJSON", has_z=any(len(p) > 2 for p in proj))


def read_kml(text):
    blocks = re.findall(r"<coordinates>(.*?)</coordinates>", text, flags=re.S | re.I)
    lines = []
    for b in blocks:
        pts = []
        for tok in b.split():
            v = [float(x) for x in tok.split(",") if x]
            if len(v) >= 2:
                pts.append(v)
        if len(pts) >= 2:
            lines.append(pts)
    pts = _longest(lines)[0]
    proj, origin = _project(pts)
    return dict(points=proj, origin=origin, source="KML", has_z=any(len(p) > 2 for p in proj))


def read_gpx(text):
    pts = []
    for m in re.finditer(r'<(?:trkpt|rtept)[^>]*lat="([-\d.]+)"[^>]*lon="([-\d.]+)"[^>]*>(.*?)</(?:trkpt|rtept)>',
                         text, flags=re.S):
        lat, lon, inner = float(m.group(1)), float(m.group(2)), m.group(3)
        e = re.search(r"<ele>([-\d.]+)</ele>", inner)
        pts.append([lon, lat] + ([float(e.group(1))] if e else []))
    if len(pts) < 2:
        raise ValueError("No track points found in the GPX file.")
    proj, origin = _project(pts)
    return dict(points=proj, origin=origin, source="GPX", has_z=any(len(p) > 2 for p in proj))


def read_csv(text):
    rows = []
    for ln in text.replace("\r", "").split("\n"):
        v = [x for x in re.split(r"[,;\t ]+", ln.strip()) if x]
        try:
            rows.append([float(x) for x in v])
        except ValueError:
            continue
    rows = [r for r in rows if len(r) >= 2]
    if len(rows) < 2:
        raise ValueError("Need at least two numeric rows.")
    # lat/lon detection
    if all(-90 <= r[0] <= 90 and -180 <= r[1] <= 180 for r in rows) and \
            max(abs(r[0]) for r in rows) > 1.5 and max(r[0] for r in rows) - min(r[0] for r in rows) < 1.0:
        pts = [[r[1], r[0]] + r[2:3] for r in rows]
        proj, origin = _project(pts)
        return dict(points=proj, origin=origin, source="CSV (lat, lon)", has_z=len(rows[0]) > 2)
    return dict(points=[r[:3] for r in rows], source="CSV (x, y)", has_z=len(rows[0]) > 2)


def read_profile_csv(text):
    """chainage, elevation [, vertical curve length]"""
    rows = []
    for ln in text.replace("\r", "").split("\n"):
        v = [x for x in re.split(r"[,;\t ]+", ln.strip()) if x]
        try:
            rows.append([float(x) for x in v])
        except ValueError:
            continue
    rows = [r[:3] for r in rows if len(r) >= 2]
    return dict(pvis=rows)


def read_any(text, filename=""):
    fn = filename.lower()
    t = text.lstrip()[:400]
    if fn.endswith(".dxf") or "SECTION" in t[:200]:
        return read_dxf(text)
    if fn.endswith((".geojson", ".json")) or t.startswith("{"):
        return read_geojson(text)
    if fn.endswith(".kml") or "<kml" in t.lower():
        return read_kml(text)
    if fn.endswith(".gpx") or "<gpx" in t.lower():
        return read_gpx(text)
    return read_csv(text)


def simplify(points, tol=0.5):
    """Douglas-Peucker simplification (keeps z)."""
    if len(points) < 3:
        return points

    def dp(pts):
        a, b = pts[0], pts[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1e-12
        dmax, idx = 0.0, 0
        for i in range(1, len(pts) - 1):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + b[0] * a[1] - b[1] * a[0]) / n
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol:
            return dp(pts[:idx + 1])[:-1] + dp(pts[idx:])
        return [a, b]
    return dp(points)


def profile_from_points(points, alignment):
    """Elevation PVIs from 3D points by projecting them on the chainage."""
    import numpy as np
    s = alignment.s
    out = []
    for p in points:
        if len(p) < 3:
            continue
        d = (alignment.x - p[0]) ** 2 + (alignment.y - p[1]) ** 2
        i = int(np.argmin(d))
        out.append([float(s[i]), float(p[2]), 0.0])
    out.sort()
    # thin to about one PVI per 20 m
    thin, last = [], -1e9
    for r in out:
        if r[0] - last >= 20 or r is out[-1]:
            thin.append(r)
            last = r[0]
    return thin
