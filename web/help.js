/* Street Lighting — explanations behind every input.
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 *
 * Each input that needs one gets a small ? badge on its label:
 *
 *   hover the badge         the explanation appears beside it
 *   click the badge         it stays until dismissed (Esc or a click elsewhere)
 *   "Explain all" (top bar) every explanation is shown inline under its field
 *
 * An entry is [what it is, reasonable range, why the design needs it].
 * Keys are input ids; table inputs such as "tree_3_height" use "tree.height".
 */

export const HELP = {
  // ---------------------------------------------------------------- luminaire
  'lum.file': ['The photometric file published by the luminaire manufacturer: IES (LM-63, .ies) or EULUMDAT (.ldt). It lists the luminous intensity in every direction around the luminaire.',
    'One file per luminaire variant (optic, lumen package). Files of the same family can be loaded together and compared in the search.',
    'Everything on the road — luminance, illuminance, uniformity, glare — is computed from this table. A real file is the only basis for a final design.'],
  gLamp: ['The type of light source when no photometric file is available.',
    'LED for new schemes; HPS (sodium, orange), MH (metal halide, white), MV (mercury, obsolete), LPS (low-pressure sodium), CFL, induction for existing installations.',
    'Sets the typical efficacy (lm/W), colour temperature, colour rendering and lamp lumen maintenance used when the values are not entered.'],
  gOptic: ['The shape of the light distribution. Road optics throw light along the road and across it, and little behind the pole.',
    'Type II: narrow roads and paths, poles near the kerb. Type III: two-lane roads (the usual choice). Type III long throw: wide roads. Type IV: very wide roads from one side. Type V and post-top: squares, car parks.',
    'The optic decides how far apart poles can be for a given height. Generic optics are indicative; replace them by the real file.'],
  gFlux: ['Rated luminous flux of the lamp or LED module, in lumens.',
    'Footpaths 1 000–4 000 lm; residential streets 3 000–8 000 lm; collectors 8 000–15 000 lm; main roads 15 000–30 000 lm; motorways 25 000–45 000 lm. A 150 W HPS gives about 17 500 lm.',
    'Light levels are directly proportional to the flux: twice the lumens give twice the luminance at the same spacing.'],
  gPower: ['Total electrical power drawn by the luminaire including driver or ballast, in watts.',
    'LED about 1 W per 140–170 lm; HPS 150 W lamp ≈ 170 W with ballast. Leave empty to use the typical efficacy of the source.',
    'Used for the energy indicators (PDI, AECI), running cost, cable currents and voltage drop.'],
  gCct: ['Correlated colour temperature of the light, in kelvin.',
    '2 000 K (sodium), 2 700–3 000 K (warm, preferred in residential and ecological areas), 4 000 K (neutral, main roads).',
    'Only affects the colour of the night view and the report; lighting classes are photopic and do not depend on it.'],
  gName: ['A name for this luminaire in lists and the report.', 'Any text, e.g. "Existing 150 W SON".', 'Helps tell variants apart.'],
  'lum.use': ['Whether the design search may choose this luminaire.', 'Tick every variant you want compared.', 'The search ranks all ticked luminaires together by cost.'],
  'lum.dim': ['Whether the light output can be reduced (dimmable LED driver).',
    'LED drivers with DALI / 1–10 V / programmed dimming: tick. Discharge lamps on magnetic ballasts: untick.',
    'A dimmable luminaire is set to exactly the level the class needs, saving energy; a fixed one is used at full output.'],
  'lum.price': ['Purchase price of one luminaire, in the project currency.', 'Leave empty to estimate it from the power.', 'Part of the life-cycle cost used to rank the layouts.'],

  // ------------------------------------------------------- maintenance factor
  'mf.mode': ['The maintenance factor fM reduces the new (initial) light output to what remains just before maintenance: fM = LLMF × LSF × LMF (CIE 154).',
    'LED in a sealed IP66 luminaire: 0.75–0.85. HPS: 0.70–0.80. Dirty, old, open luminaires: 0.55–0.65.',
    'EN 13201-2 gives maintained values; a design without fM is over-optimistic by 15–35 %.'],
  mF: ['Overall maintenance factor fM entered directly.', '0.70–0.85 for most LED road schemes; never below 0.5 or above 0.95 in practice.',
    'All calculated levels are multiplied by this factor; the threshold increment uses initial (fM = 1) values as the standard requires.'],
  mLamp: ['Light source used for the maintenance calculation.', 'LED, HPS, MH …', 'Sets the lamp lumen maintenance (LLMF) and lamp survival (LSF) when they are not entered.'],
  mInt: ['How often the luminaires are cleaned, in years.', '1–3 years; 3 is common for sealed LED luminaires.', 'Dirt on the optic reduces the light (LMF); longer intervals lower fM.'],
  mPol: ['Air pollution category of the site (CIE 154).', 'Low: rural, residential. Medium: suburban, light traffic. High: city centre, industry, heavy traffic.', 'Governs how fast the optic gets dirty (LMF).'],
  mRel: ['How often all lamps are replaced together (group replacement), in years.', 'High-pressure sodium 3–4 years, metal halide 2–3 years; not used for LED.', 'Lamp output falls with burning hours (CIE 154 Table 3.1); later replacement means a lower LLMF.'],
  mSpot: ['Whether failed lamps are replaced soon after they fail.', 'Ticked for most maintained road lighting.', 'With spot replacement EN 13201-3 advises leaving lamp survival out of fM (LSF = 1); otherwise CIE 154 Table 3.2 applies.'],
  mIp: ['Ingress protection of the optical compartment.', 'IP66 / IP65 for modern road luminaires; IP54 / IP44 / IP23 for older or open luminaires.', 'CIE 154 Table 3.3 gives luminaire maintenance for IP6X, IP5X and IP2X; IP3X and IP4X are taken as IP2X (conservative). IEC 60364-7-714 asks for at least IP33.'],
  mLh: ['Hours at which the LED manufacturer states the remaining flux (the "L" rating).', 'Typically 50 000–100 000 h.', 'With the next value it gives the LED lumen depreciation (LLMF).'],
  mLx: ['Fraction of the initial flux remaining at the rated life, e.g. 0.90 for L90.', 'Good road LEDs: 0.90–0.95 at 100 000 h; L80 = 0.80; L70 = 0.70.', 'LED depreciation cannot be cleaned away, so it is taken at the end of the design life.'],
  mLife: ['Design life over which the LED flux must stay sufficient, in burning hours.', '50 000–100 000 h (about 12–25 years at 4 000 h a year).', 'A longer life means more depreciation and a lower fM, so more initial light is needed.'],
  mHrs: ['Burning hours per year.', 'About 4 000–4 400 h at mid latitudes (dusk to dawn).', 'Converts the cleaning interval into hours.'],

  // --------------------------------------------------------------------- road
  std: ['The family of lighting requirements.', 'EN 13201 (Europe, Iran, Middle East, CIE-based countries) or ANSI/IESNA RP-8-00 (North America, criteria of the 2000 edition; the current edition is RP-8-25, whose criteria differ).',
    'Decides which lighting classes can be chosen and how compliance is judged.'],
  'road.template': ['Ready-made cross-sections for common road types.', 'Pick the closest one, then edit widths, lanes and classes.', 'A quick start; every value can be changed.'],
  'strip.kind': ['What the strip is used for.', 'Carriageway (traffic lanes), footway, verge (grass), median, cycle track, parking, hard shoulder.',
    'Carriageways are judged by road luminance (M classes) or illuminance; footways and cycle tracks by illuminance (P classes). Verges and medians carry poles and trees.'],
  'strip.width': ['Width of the strip across the road, in metres.', 'Traffic lane 2.75–3.75 m; footway 1.5–4 m; verge 0.5–3 m; median 1–10 m; cycle track 1.5–3 m.',
    'Sets where poles can stand, how far the light must reach and the calculation grid.'],
  'strip.lanes': ['Number of traffic lanes in the carriageway.', '1–4 per direction.',
    'EN 13201-3 places three calculation points across each lane and an observer in the centre of each lane in turn.'],
  'strip.cls': ['The lighting class (performance level) this strip must meet.',
    'M1 (motorways) … M6 (minor roads); C0 … C5 (conflict areas: junctions, roundabouts); P1 … P6 (footways, residential streets); HS for hemispherical criteria. Use "Which class?" if unsure.',
    'The class sets the minimum luminance or illuminance, the uniformity and the glare limit — the targets of the whole design.'],
  'strip.surface': ['The reflection class of the carriageway surface (CIE r-table).',
    'R3 for ordinary asphalt (most roads); R2 for asphalt with light aggregate; R1 for concrete; R4 for very smooth, glossy asphalt.',
    'Road luminance (what a driver sees) depends on how the surface reflects light toward the driver. A specular surface (R3, R4) looks brighter beyond the luminaire.'],
  'strip.faces': ['Tick when people must be recognisable by their faces (busy streets, public spaces, areas with crime risk).',
    'P classes only.', 'Adds the minimum vertical and semi-cylindrical illuminance at 1.5 m height of EN 13201-2 Table 3.'],
  oUl: ['Apply the longitudinal uniformity Ul of the M class.', 'On for long uninterrupted roads; EN 13201-2 says it applies only there.',
    'Ul limits the bright-dark banding along the lane centre that makes driving tiring.'],
  oREI: ['Apply the edge illuminance ratio REI of the M class.', 'On unless the adjacent areas have their own lighting class.',
    'REI makes sure the kerb zone and footway edge are lit, so pedestrians stepping out are visible.'],
  oTIP: ['Apply the glare limit fTI of EN 13201-2 Annex C to P classes.', 'Optional; off by default.',
    'Limits glare for pedestrians and cyclists where low luminaires face them.'],
  'road.classhelp': ['A short questionnaire that picks the class with the parameter-weighting method of CEN/TR 13201-1.',
    'Answer for the speed, traffic, users, parked cars, ambient brightness and navigation difficulty.',
    'Gives a defensible class instead of a guess; confirm against national rules.'],

  // -------------------------------------------------------------------- route
  'route.mode': ['How the road alignment is described.',
    'Straight: a length only. Straights and bends: a list of segments. Draw / import: click points on the plan or load DXF, GeoJSON, KML, GPX or CSV.',
    'Bends and hills change where poles go and how far apart they can be.'],
  rLen: ['Length of a straight road, in metres.', '50 m – several km.', 'Sets the number of poles, cable lengths and the energy totals.'],
  'seg.type': ['Straight or circular bend.', '', 'Bends get shorter spacing and poles on the outside.'],
  'seg.length': ['Length of the segment along the road, in metres.', 'Straights 20–2 000 m; for a bend either the length or the angle.', 'Builds the alignment and the chainage.'],
  'seg.radius': ['Radius of the bend, in metres.', 'Urban bends 15–150 m; roads 150–1 000 m; above 1 000 m treated as straight.', 'Tighter bends (R < 300 m) reduce spacing and move poles to the outside.'],
  'seg.angle': ['Angle turned by the bend, in degrees.', '5–180°.', 'With the radius gives the bend length.'],
  'seg.turn': ['Direction of the bend when travelling along the chainage.', 'Left or right.', 'Decides which side is the outside of the bend.'],
  rRad: ['Bend radius used at each drawn point (fillet).', 'Urban 20–100 m; rural 150–500 m; 0 for sharp corners.', 'Turns the drawn polyline into a smooth road with real bends.'],
  rGrid: ['Spacing of the background grid of the drawing pad.', '10, 25 or 50 m.', 'Only a drawing aid; points snap to 0.5 m.'],
  'pvi.0': ['Chainage of an elevation point (PVI), in metres from the start.', '0 to the route length.', 'With the elevation, defines the vertical profile.'],
  'pvi.1': ['Road elevation at that chainage, in metres (any datum).', 'Grades up to about 8 % on urban roads, 6 % on main roads.', 'Slopes change the angle at which light hits the road.'],
  'pvi.2': ['Length of the vertical curve centred on this point, in metres.', '0 for a sharp grade change; 60–300 m for real crests and sags.',
    'A crest hides luminaires and shows them at low angles (glare); the layout shortens spacing there and checks glare (EN 13201-2 A.3.1).'],
  rCf: ['Cross-fall of the road surface across the section, in percent.', '1.5–3 % (drainage camber); up to 7 % superelevation on bends.', 'Tilts the surface relative to the luminaires.'],
  'tree.y': ['Position of the tree line across the section, in metres from side A (the first strip edge).', 'Usually in a verge or footway.', 'Decides which part of the road the crowns shade.'],
  'tree.s0': ['Chainage where the tree line starts, in metres.', '', 'Only that stretch is shaded.'],
  'tree.s1': ['Chainage where the tree line ends, in metres.', '', 'If the trees cover more than half of the route, the design search accounts for them.'],
  'tree.spacing': ['Distance between trees along the line, in metres.', '5–12 m for street trees.', 'Closer trees form a continuous canopy that blocks more light.'],
  'tree.crown_base': ['Height of the lowest branches above the ground, in metres.', '2.5–5 m for street trees (lifted crowns).', 'A luminaire can be mounted below the crown base; the search tries this.'],
  'tree.height': ['Height of the tree top, in metres.', '6–15 m.', 'A luminaire above the crowns lights over them; the search tries this too.'],
  'tree.crown_radius': ['Horizontal radius of the crown, in metres.', '1.5–4 m.', 'Defines the shading volume and the arm length needed to reach past it.'],
  'tree.density': ['Foliage extinction coefficient κ (1/m): how much light is lost per metre inside the crown, T = e^(−κ·chord).',
    '0.3 light / winter, 0.6 average, 1.0–1.5 dense summer foliage.', 'Higher density means deeper shadows under the crowns.'],
  'cross.s': ['Chainage of a pedestrian crossing, in metres.', '', 'Adds one luminaire before the crossing in each traffic direction to light pedestrians from the drivers’ side (EN 13201-2 Annex B).'],
  'junc.s': ['Chainage of a junction, in metres.', '', 'A pole is placed at the junction mouth, the conflict area where vehicles turn.'],
  'junc.side': ['Side of the road the junction joins.', 'Side A, side B or both (crossroads).', 'Recorded for the layout and the drawing.'],
  'nop.s0': ['Start of a stretch where no pole may stand, in metres.', 'Driveways, gates, bridges, buried services.', 'Poles are moved clear of the stretch.'],
  'nop.s1': ['End of the no-pole stretch, in metres.', '', ''],
  'nop.reason': ['Why poles are not allowed here.', 'e.g. driveway, bridge, gas main.', 'Appears in the column schedule.'],
  'ohl.s0': ['Start of an overhead power line along the road, in metres.', '', 'Columns under the line are limited in height.'],
  'ohl.s1': ['End of the overhead line, in metres.', '', ''],
  'ohl.y': ['Position of the line across the section, in metres from side A.', '', 'Only poles within a few metres of the line are limited.'],
  'ohl.height': ['Height of the lowest conductor, in metres.', 'LV 6–8 m; MV 8–10 m.', 'Pole height is kept 1.5 m below it for safe clearance.'],

  // ------------------------------------------------------------------- design
  sH: ['Mounting heights to try, in metres, separated by commas.', 'Footpaths 3–5 m; residential 5–8 m; collectors 8–10 m; main roads 10–12 m; motorways 12–16 m. Empty = chosen from the road width.',
    'Higher poles allow longer spacing and better uniformity but cost more and spill more light.'],
  sO: ['Arm (bracket) lengths to try, in metres.', '0–2.5 m; longer arms reach past trees or toward the road centre.', 'Moves the luminaire over the road, improving the far side and the luminance.'],
  sT: ['Upward tilt angles of the luminaire to try, in degrees.', '0–15°; modern LED optics are designed for 0–5°.', 'Tilt throws light further across the road but raises glare and upward light.'],
  sSb: ['Distance of the pole from the kerb (the edge of the carriageway), in metres.', '0.5–1.5 m (passive safety and door clearance).', 'Sets where the pole stands; the arm is measured from the pole.'],
  'design.arr': ['How the poles are arranged across the road.',
    'Single-sided: roads up to about 1–1.2 × H wide. Staggered: 1–1.5 × H. Opposite: wider than 1.5 × H. Twin central: dual carriageways with a median.',
    'The arrangement decides how evenly both sides of the road are lit.'],
  'design.full': ['With more than four luminaires, a quick first pass (3 heights, 2 arm lengths, one tilt, 1 m spacing steps) ranks them all, and only the 3 cheapest are searched in full. Tick this to search every luminaire in full instead.',
    'Leave it off for normal work; tick it to check a close decision.',
    'The quick pass usually finds the same winner in about a third of the time; the full search cannot miss a luminaire that only does well at a height or arm the quick pass skipped.'],
  cCur: ['Currency for all costs.', 'USD, EUR, IRR …', 'Labels only.'],
  cPb: ['Fixed cost of one column (excluding the height-related part).', 'Local prices.', 'Life-cycle ranking: fewer, taller poles versus more, shorter ones.'],
  cPm: ['Extra column cost per metre of height.', 'Local prices.', 'Penalises tall columns in the ranking.'],
  cAm: ['Cost of the arm per metre.', 'Local prices.', 'Penalises long arms.'],
  cFd: ['Foundation and installation cost per column.', 'Local prices.', 'Fixed cost per pole.'],
  cLw: ['Luminaire price per watt when no price is entered.', 'LED road luminaires about 2–5 per watt.', 'Estimates the luminaire cost.'],
  cCb: ['Cable plus trench cost per metre of route.', 'Local prices.', 'Opposite and staggered layouts need two cable runs.'],
  cEp: ['Electricity price per kWh.', 'Local tariff for public lighting.', 'Running cost over the life of the scheme.'],
  cHr: ['Burning hours per year.', '4 000–4 400 h.', 'Converts power into energy.'],
  cYr: ['Life of the scheme for the cost comparison, in years.', '15–25 years.', 'Longer lives weight running costs more than investment.'],
  cDr: ['Discount rate for future costs.', '0.03–0.10.', 'Converts yearly costs to a present value (NPV).'],
  mA: ['Arrangement of your own layout.', 'See "Arrangements".', 'Checks a layout you already have, e.g. an existing installation.'],
  mP: ['Luminaire for your own layout.', '', ''],
  mH: ['Mounting height of your layout, in metres.', '4–16 m.', ''],
  mS: ['Spacing between poles of one row, in metres.', 'About 3–5 × the mounting height.', 'The single most important cost driver.'],
  mO: ['Arm length of your layout, in metres.', '0–2.5 m.', ''],
  mT: ['Tilt of the luminaire, in degrees.', '0–15°.', ''],
  mF2: ['Light output as a fraction of the rated flux.', '0.3–1.0 for dimmable LEDs; 1.0 for fixed output.', 'Lets you check a dimmed setting.'],

  // ------------------------------------------------------------------- layout
  lM: ['Safety margin on the design spacing along the route.', '0.90–1.00; 0.95 recommended.', 'The straight-road spacing is at the limit; a small margin absorbs grades, cross-fall and construction tolerances.'],
  lC: ['Spacing factor on crests.', '0.75–0.90.', 'On a crest the luminaires beyond are seen at low angles and the road surface is hidden; shorter spacing restores uniformity.'],
  lI: ['How many times failing stretches may be tightened.', '3–8.', 'Each round shortens spacing by 10 % where spans fail; more rounds give compliance at the cost of more poles.'],
  lT: ['Minimum clear distance between a pole and a tree trunk, in metres.', '1–2 m.', 'Poles are moved so they do not stand in a tree.'],
  lB: ['Shorten the spacing on bends.', 'On.', 'Spacing falls from 100 % at R ≥ 1 000 m to 55 % at R ≤ 50 m, then every span is checked.'],
  lO: ['Move single-sided poles to the outside of bends.', 'On for R < 300 m.', 'Luminaires on the outside light the curve ahead and guide the driver visually; on the inside they leave the outer edge dark.'],
  lX: ['Add a luminaire before each pedestrian crossing in each direction.', 'On.', 'Lights pedestrians from the side facing traffic (positive contrast), EN 13201-2 Annex B.'],
  lJ: ['Place a pole at each junction.', 'On.', 'Conflict areas need light where vehicles turn and cross.'],

  // --------------------------------------------------------------- electrical
  eSys: ['Earthing arrangement of the supply.', 'TN-S / TN-C-S (common for utility supplies); TT (separate earth electrode at the pillar, common for street lighting in many countries).',
    'Decides how earth faults are cleared: by the breaker (TN) or by an RCD (TT).'],
  eU: ['Phase-to-neutral voltage U₀, in volts.', '230 V (400 V three-phase) in Iran, Europe, Australia; 120/277 V elsewhere.', 'Sets currents, voltage drop and the fault-loop limit.'],
  eMat: ['Conductor material.', 'Copper (smaller, dearer) or aluminium (larger, cheaper; 16 mm² minimum).', 'Changes resistance, current capacity and cost.'],
  eIns: ['Cable insulation.', 'XLPE (90 °C, usual for buried cables) or PVC (70 °C).', 'XLPE carries more current for the same size.'],
  eMeth: ['How the cable is laid (IEC 60364-5-52 reference methods).', 'D2: directly in the ground. D1: in a buried duct.', 'Heat escapes differently, which changes the current the cable can carry.'],
  eDev: ['Protective device at the start of each feeder.', 'MCB type C (usual for LED drivers with inrush current), B, D, or gG fuse.', 'Must trip fast enough on an earth fault and not trip on switch-on inrush.'],
  eGk: ['For gG fuses only: the current that blows the fuse within 0.4 s, divided by its rating, read from the fuse maker\'s time-current curve.', 'Typically 5–8 for gG fuses of 6–63 A. Leave empty to use the IEC 60269 gate Imax(0.1 s), which is guaranteed but about twice as strict.', 'Sets the largest fault-loop impedance that still disconnects in 0.4 s (IEC 60364-4-41).'],
  eDu: ['Maximum voltage drop from the pillar to the farthest luminaire, in percent.', '3 % for lighting supplied from the public LV network; up to 6 % from a private transformer (IEC 60364-5-52 Table G.52.1).',
    'Too much drop dims luminaires and can stop drivers; it is often what sizes long cables.'],
  ePf: ['Power factor of the luminaires.', 'LED drivers 0.90–0.98; HPS with compensation 0.85–0.92.', 'Converts power to current.'],
  eTg: ['Ground temperature at cable depth, in °C.', '15–25 °C temperate; 25–35 °C hot climates.', 'Hotter ground lowers the current a buried cable can carry (Table B.52.15).'],
  eRs: ['Thermal resistivity of the soil, in K·m/W.', 'Moist soil 1.0; average 1.5–2.5 (reference 2.5); dry sand 3.0.', 'Dry soil holds heat around the cable and lowers its rating (Table B.52.16).'],
  eZe: ['Earth-fault loop impedance of the supply at the pillar, in ohms.', '0.2–0.8 Ω for TN supplies (ask the network operator).', 'Added to the cable impedance to check that a fault at the last luminaire trips the breaker in time.'],
  eIk: ['Prospective short-circuit current at the pillar, in amperes.', '3–10 kA in urban areas.', 'The smallest cable must survive this current until the device trips (adiabatic check).'],
  eRa: ['Resistance of the earth electrode at the pillar (TT only), in ohms.', '10–100 Ω.', 'With the RCD rating it must keep touch voltage below 50 V: RA × IΔn ≤ 50 V.'],
  eIdn: ['Rated residual current of the RCD (TT only), in amperes.', '0.03, 0.1 or 0.3 A.', 'Smaller ratings tolerate higher electrode resistance but may trip on leakage of many drivers.'],
  eDrv: ['How many LED drivers one B16 breaker can switch on without tripping (from the driver datasheet).', '10–30 typical.', 'Inrush current of many drivers can trip breakers at switch-on; the check scales this to the actual breaker.'],
  ePc: ['Cost of one feeder pillar (cabinet, switchgear, metering).', 'Local prices.', 'Balances more pillars against longer and larger cables.'],

  // --------------------------------------------------------------- structural
  wV: ['Reference wind speed Vref: 10-minute mean at 10 m height, 50-year return period, terrain category II (EN 40-3-1 5.2.2); the 25-year return period of lighting columns is applied by Cs = √0.92.', 'Read it from the national wind map; about 22–30 m/s in most of Iran and Europe, more on coasts.',
    'Wind on the column, arm and luminaire is the main load on a lighting column.'],
  wT: ['Terrain category around the column (EN 40-3-1 Table 1).', 'I open sea / flat country, II farmland with hedges and houses (EN 40 default), III suburbs, industrial areas, forests, IV city centres. UK guidance (PD 6547): III below 8 m, II from 8 m.', 'Rougher terrain slows the wind near the ground; the exposure coefficient follows EN 40-3-1 Table 2.'],
  wG: ['Steel grade of the column.', 'S235, S275 or S355 (usual for tapered columns).', 'Sets the yield strength in the EN 40-3-3 bending and torsion resistance (γm = 1.05).'],
  wL: ['Partial load factor class of EN 40-3-3 Table 1.', 'A: wind × 1.4, dead load × 1.2 (default). B: 1.2 and 1.2 (recommended in the UK by PD 6547).', 'The national annex or the client decides; class A is the safer choice.'],
  wD: ['Deflection class of EN 40-3-3 Table 4.', 'Limit on the sway of the luminaire connection: class 1 = 0.04 (h + w), 2 = 0.06 (h + w), 3 = 0.10 (h + w); UK practice uses class 3.', 'A stiffer column keeps the light pattern steady in wind but is heavier.'],
  soilT: ['Type of soil around the foundation.', 'Sand / gravel (cohesionless) or clay (cohesive).', 'Selects the Broms method for the embedment depth.'],
  soilP: ['Friction angle φ of a sandy soil, in degrees.', 'Loose sand 28°, medium 32°, dense 36–40°.', 'Higher φ gives more passive resistance and a shallower foundation.'],
  soilC: ['Undrained shear strength cu of a clay, in kPa.', 'Soft 20–40, firm 40–75, stiff 75–150.', 'Stronger clay holds the column with a shallower foundation.'],
  soilD: ['Diameter of the bored concrete foundation, in metres.', '0.4–0.8 m.', 'A wider foundation needs less depth.'],
  soilQ: ['Ground quality for the PD 6547 planting-depth check.', 'Good (G 630): compact sand and gravel, hard clay. Average (G 390): fine sand, medium clay. Poor (G 230): soft clay, made-up ground.', 'The deeper of this and the Broms result is used.'],

  // ------------------------------------------------------------------- energy
  nK: ['How the lighting is operated through the night.', 'Full output; dimmed after midnight (bi-power); three levels.', 'Dimming at low-traffic hours is the cheapest energy saving (EN 13201-5 Annex A).'],
  nH: ['Burning hours per year.', '4 000–4 400 h.', 'Base of the energy figures.'],
  nR: ['Fraction of the burning hours run at the reduced level.', '0.3–0.6 (e.g. midnight to dawn).', ''],
  nL: ['Light and power level during the reduced hours, as a fraction of full.', '0.5–0.7; the lower class one step down is common.', ''],
  nP: ['Electricity price per kWh.', 'Local public-lighting tariff.', 'Yearly running cost.'],
  nC: ['Grid emission factor, kg CO₂ per kWh.', 'Iran ≈ 0.6; EU average ≈ 0.25; coal-heavy grids 0.8–1.0.', 'Converts energy into CO₂.'],
  nS: ['Standby power of each luminaire when off (driver, control node), in watts.', '0.2–1.0 W.', 'Counted over the daytime hours in AECI (EN 13201-5).'],
  nY: ['Years for the cost totals.', '15–25.', ''],

  // ------------------------------------------------------------------- report
  repLang: ['Language of the report.', 'English, Persian (right-to-left) or both side by side.', ''],
  repBy: ['Name of the designer or company shown on the cover.', '', ''],
  repFor: ['Name of the client shown on the cover.', '', ''],
};

const LBL = ['', 'Typical: ', 'Why it matters: '];
export function helpHTML(key) {
  const h = HELP[key];
  if (!h) return '';
  return h.map((t, i) => t ? `<p>${i ? `<b>${LBL[i]}</b>` : ''}${t}</p>` : '').join('');
}
export const qm = (key, what = '') => HELP[key] ? `<button type="button" class="qm" data-help="${key}" aria-label="Explain${what ? ' ' + what : ' this'}" aria-expanded="false">?</button>` : '';

function keyOf(el) {
  if (el.dataset && el.dataset.act) return 'lum.' + el.dataset.act;
  const id = el.id || '';
  const m = id.match(/^([a-z]+)_\d+_(\w+)$/i);
  return m ? m[1] + '.' + m[2] : id;
}

/* Add badges (and hidden inline text) to every known input inside root. */
export function decorate(root) {
  // badges placed directly in headings and table headers: name them after that heading or column
  root.querySelectorAll('.qm[aria-label="Explain this"]').forEach(b => {
    const host = b.closest('th, h3, h4, .strip.head > span, label');
    const t = host ? host.textContent.replace('?', '').replace(/\s+/g, ' ').trim() : '';
    if (t) b.setAttribute('aria-label', 'Explain “' + t + '”');
  });
  root.querySelectorAll('input, select, textarea').forEach(el => {
    const key = keyOf(el);
    if (!HELP[key]) return;
    const lab = el.closest('label');
    if (!lab || lab.querySelector('.qm')) return;
    const span = lab.classList.contains('f') ? lab.querySelector('span') : null;
    // the field's own name, read before the badge is added, so the badge says what it explains
    // and the input keeps a clean accessible name (without "Explain" inside it)
    const name = ((span || lab).textContent || '').replace(/\s+/g, ' ').trim();
    if (name && !el.hasAttribute('aria-label') && !el.hasAttribute('aria-labelledby')) el.setAttribute('aria-label', name);
    const badge = document.createElement('span');
    badge.innerHTML = qm(key, name ? '“' + name + '”' : '');
    const b = badge.firstChild;
    if (span) span.appendChild(b); else lab.appendChild(b);
    if (lab.classList.contains('f')) {
      const d = document.createElement('div');
      d.className = 'fh';
      d.innerHTML = helpHTML(key);
      lab.appendChild(d);
    }
  });
}

// ---------------------------------------------------------------- tooltip
let tip = null, pinned = null, timer = null;
function tipEl() {
  if (tip) return tip;
  tip = document.createElement('div');
  tip.id = 'fieldtip';
  tip.setAttribute('role', 'tooltip');
  tip.hidden = true;
  document.body.appendChild(tip);
  tip.addEventListener('mousedown', e => e.stopPropagation());
  return tip;
}
let shownFor = null;
function show(btn) {
  const t = tipEl();
  if (shownFor && shownFor !== btn) shownFor.removeAttribute('aria-describedby');
  shownFor = btn;
  btn.setAttribute('aria-describedby', 'fieldtip');   // screen readers read the explanation with the button
  t.innerHTML = helpHTML(btn.dataset.help) + (pinned === btn ? '' : '');
  t.hidden = false;
  const a = btn.getBoundingClientRect();
  const w = t.offsetWidth, h = t.offsetHeight;
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  let x = a.left + a.width / 2 - 24, y = a.bottom + 8;
  if (x + w > vw - 8) x = vw - w - 8;
  if (x < 8) x = 8;
  if (y + h > vh - 8) y = Math.max(8, a.top - h - 8);
  t.style.left = x + 'px';
  t.style.top = y + 'px';
}
function hide() {
  if (tip) tip.hidden = true;
  if (shownFor) { shownFor.removeAttribute('aria-describedby'); shownFor = null; }
}
function setPinned(b) {
  if (pinned) pinned.setAttribute('aria-expanded', 'false'), pinned.classList.remove('on');
  pinned = b;
  if (b) { b.classList.add('on'); b.setAttribute('aria-expanded', 'true'); }
}

export function initHelp() {
  document.addEventListener('mouseover', e => {
    const b = e.target.closest && e.target.closest('.qm');
    if (!b || pinned) return;
    clearTimeout(timer);
    timer = setTimeout(() => show(b), 80);
  });
  document.addEventListener('mouseout', e => {
    const b = e.target.closest && e.target.closest('.qm');
    if (!b || pinned) return;
    clearTimeout(timer);
    timer = setTimeout(hide, 120);
  });
  document.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('.qm');
    if (b) {
      e.preventDefault();
      e.stopPropagation();
      if (pinned === b) { setPinned(null); hide(); return; }
      setPinned(b); show(b);
      return;
    }
    if (pinned && !(tip && tip.contains(e.target))) { setPinned(null); hide(); }
  }, true);
  // keyboard: the explanation also appears when Tab reaches a badge (WCAG 1.4.13, 2.1.1)
  document.addEventListener('focusin', e => {
    const b = e.target.closest && e.target.closest('.qm');
    if (b && !pinned && b.matches(':focus-visible')) show(b);
  });
  document.addEventListener('focusout', e => {
    const b = e.target.closest && e.target.closest('.qm');
    if (b && !pinned) hide();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && (pinned || (tip && !tip.hidden))) { setPinned(null); hide(); }
  });
  document.addEventListener('scroll', () => { if (!pinned) hide(); else show(pinned); }, true);
}
