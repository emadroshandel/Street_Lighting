# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
"""Street Lighting calculation engine.

Modules
-------
photometry   I-table readers (IES LM-63, EULUMDAT) and generic optics
rtables      CIE road-surface r-tables R1..R4 and interpolation
geometry     luminaire attitude (orientation, tilt, rotation) -> (C, gamma)
calc         EN 13201-3 quality characteristics on a straight section
classes      EN 13201-2 / CEN/TR 13201-1 / IES RP-8 lighting classes
road         cross-section, alignment, vertical profile, obstacles
optimize     pole height / spacing / arrangement search
scheme       full-route point-by-point calculation with obstruction
electrical   feeder pillar, circuits, IEC 60364-5-52 cable sizing
structural   EN 40-3-1 wind load, column check, foundation
energy       EN 13201-5 PDI / AECI, life-cycle cost
importers    DXF / GeoJSON / CSV / KML centrelines and profiles
dxf          DXF R12 drawing writer
report       bilingual design report
api          JSON dispatch used by the HTTP server and by Pyodide
"""

APP_NAME = "Street Lighting"
APP_VERSION = "0.9.0"
