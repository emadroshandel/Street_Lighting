{
  "name": "Urban collector — demo",
  "standard": "EN13201",
  "luminaires": {
    "led80": {"source": "generic", "name": "LED 80 W, Type III optic", "optic": "type3", "lamp_type": "LED",
              "lamp_flux": 12000, "power": 80, "cct": 3000, "dimmable": true, "dim_min": 0.3,
              "weight": 9, "wind_area": 0.11, "price": 320},
    "hps150": {"source": "generic", "name": "HPS 150 W (existing type)", "optic": "type3", "lamp_type": "HPS",
               "lamp_flux": 17500, "power": 170, "lor": 0.78, "dimmable": false,
               "weight": 14, "wind_area": 0.16, "price": 180}
  },
  "maintenance": {"mode": "direct", "fM": 0.8},
  "section": {
    "elements": [
      {"kind": "footway", "name": "Footway A", "width": 2.5, "cls": "P4"},
      {"kind": "verge", "name": "Verge A", "width": 1.0},
      {"kind": "carriageway", "name": "Carriageway", "width": 7.0, "lanes": 2, "cls": "M4", "surface": "R3"},
      {"kind": "verge", "name": "Verge B", "width": 1.0},
      {"kind": "footway", "name": "Footway B", "width": 2.5, "cls": "P4"}
    ],
    "options": {"apply_Ul": true, "apply_REI": true}
  },
  "search": {"phots": ["led80"], "setback": 0.6},
  "costs": {"currency": "USD", "energy_price": 0.12},
  "route": {
    "mode": "segments", "heading": 0,
    "segments": [{"type": "straight", "length": 220}, {"type": "arc", "radius": 150, "angle": 45, "turn": "L"},
                 {"type": "straight", "length": 260}],
    "profile": {"pvis": [[0, 1200, 0], [260, 1208, 160], [600, 1203, 0]], "crossfall": 2.0},
    "features": {
      "tree_lines": [{"y": 13.0, "s0": 300, "s1": 560, "spacing": 9, "crown_base": 3.5, "height": 9,
                      "crown_radius": 2.6, "density": 0.6}],
      "crossings": [{"s": 120}],
      "junctions": [{"s": 420, "side": "left"}],
      "no_pole": [{"s0": 470, "s1": 482, "reason": "driveway"}],
      "overhead_lines": []
    },
    "layout": {"margin": 0.95, "max_iter": 6}
  },
  "electrical": {"system": "TN-S", "material": "Cu", "insulation": "XLPE", "method": "D2", "device": "C",
                 "du_max": 3.0, "Ze": 0.35},
  "structural": {"wind": {"Vref": 27, "terrain": "III"}, "soil": {"type": "cohesionless", "phi": 30}},
  "energy": {"kind": "bipower", "hours": 4100, "reduce_from": 0.5, "level": 0.5, "price": 0.12, "co2": 0.55}
}
