"""Fenolite single-sided base, EVA-RT-style, FINAL parts.
Origin = turbine centre, +y = front, mm, viewed from TOP (component side)."""
import math
from shapely.geometry import Polygon, Point, box, MultiPolygon
from shapely.ops import unary_union
from shapely import affinity
from geom import *

P = 2.54

# ---------- mechanical data measured from EVA-RT Gerber + STL ----------
TURBINE = (0.0, 0.0, 17.0)                      # x,y,drill
HOUSE_SCREWS = [(15.56, 15.56), (-15.56, 15.56), (15.56, -15.56), (-15.56, -15.56)]
GEARBOX_SCREWS = [(35.25, -3.73), (-35.25, -3.73), (35.25, -26.55), (-35.25, -26.55)]
CLAMP_SCREWS = [(43.75, -1.75), (-43.75, -1.75), (43.75, 10.75), (-43.75, 10.75)]
BATT_SLOTS = [(16.69, -28.21), (-16.69, -28.21)]

HOLES = ([(TURBINE[0], TURBINE[1], 17.0, 9.3)] +
         [(x, y, 2.0, 1.8) for x, y in HOUSE_SCREWS] +
         [(x, y, 2.0, 2.4) for x, y in GEARBOX_SCREWS] +
         [(x, y, 2.0, 2.4) for x, y in CLAMP_SCREWS])
SLOTS = [box(x - 3.5, y - 0.5, x + 3.5, y + 0.5) for x, y in BATT_SLOTS]

# bottom suction plate (printed 0.6 mm) under the board: NO component (tht lead or smd) here
SUCTION = box(-23.6, -28.0, 23.6, 21.5)
# real printed suction plate (suction_base.stl): chevron front, used for via keep-out (+0.5 mm)
SUCTION_REAL = Polygon([(-23.08, -27.5), (23.08, -27.5), (23.08, 17.1), (0.0, 20.9), (-23.08, 17.1)])

def housing_legs():
    """Real feet of the impeller housing (voxelised STL, both 45-deg rotations, +0.5 mm margin)."""
    import json, os
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pes_reais.json')
    return [Polygon(p) for p in json.load(open(fn))]

def top_keepouts_h():
    """Each entry: (name, polygon, min_height) -> a TOP component taller than min_height collides.
    Ring above the impeller only hits parts >11 mm; the fan window and feet hit everything."""
    ko = []
    for p in housing_legs():
        ko.append(('pes da carcaca', p, 0.0))
    ring = Point(0, 0).buffer(23.0, 48).difference(Point(0, 0).buffer(17.5, 48))
    ko.append(('anel carcaca', ring, 11.0))
    ko.append(('janela helice', Point(0, 0).buffer(17.5, 48), 0.0))
    for b in [box(30.3, -29.0, 40.2, -1.5), box(-40.2, -29.0, -30.3, -1.5)]:
        ko.append(('caixa reducao', b, 0.0))
    for b in [box(15.0, -16.5, 31.0, -6.0), box(-31.0, -16.5, -15.0, -6.0)]:
        ko.append(('motor', b, 2.8))   # motor belly ~3.4 mm above the board: low SMD fits under it
    ko.append(('bateria', box(-29.0, -32.0, 29.0, -15.0), 0.0))
    for x, y in CLAMP_SCREWS:
        ko.append(('presilha vareta', Point(x, y).buffer(2.6, 24), 0.0))
    return ko

def top_keepouts():
    d = {}
    for name, poly, _ in top_keepouts_h():
        d.setdefault(name, []).append(poly)
    return d

def bottom_keepouts():
    """Bottom side: suction plate + gearbox screw heads (nut captured in gearbox -> bolt head under board)."""
    ko = {'placa succao': [SUCTION]}
    ko['cabecas parafuso'] = [Point(x, y).buffer(2.6, 24) for x, y in GEARBOX_SCREWS]
    return ko

# ---------------- outline ----------------
def outline_poly():
    """EVA-RT-like contour (right half, mirrored) with: a modest central front extension to host
    the ESP, and two thin lateral arms carrying the mark sensors out to x=+-72."""
    half = [(5.25, 28.75), (5.25, 25.5), (6.75, 24.0), (8.25, 24.0), (8.25, 21.5),
            (11.5, 18.24), (16.75, 18.24), (20.0, 15.0),
            (48.0, 15.0), (48.0, 9.5),          # side strip front edge raised 13->15 (+2 mm)
            (72.0, 9.0), (72.0, 0.0), (48.0, 0.0),  # sensor arm
            (48.0, -4.0), (45.0, -4.0), (40.0, -9.0), (40.0, -32.0),
            (32.7, -32.0), (29.2, -28.5), (22.0, -28.5), (20.5, -30.0), (0.0, -30.0)]
    left = [(-x, y) for x, y in reversed(half)]
    body = Polygon(half + left[1:])
    # rear-left corner squared and extended 2.5 mm to carry the XT30 (battery lies across the back)
    body = unary_union([body, box(-40.0, -34.5, -27.5, -28.5)])
    # small central front nub to host the sensor header + ESP above the suction plate
    ext = box(-12.0, 18.0, 12.0, 43.0)
    return unary_union([body, ext]).simplify(0.01)

# ---------------- placement ----------------
def build():
    C = {}
    add = lambda c: C.__setitem__(c.ref, c) or c

    # --- central front nub: sensor header (front tip) + ESP (long axis along x, USB to the left) ---
    add(fp_header('J2', 0.0, 41.0, 0, 8, ['3V3', 'GND', 'NC', 'C0', 'S3', 'S2', 'S1', 'S0'], 'barra'))
    add(fp_esp32c3('U1', 0.0, 30.0, 90))
    add(fp_btn2('SW1', -29.6, 13.2, 0))    # button on the left front strip (keeps the nose short)
    # power cluster on the nub bottom, in the free band between the two ESP pin rows
    add(fp_sot223('U2', 0.0, 30.0, 0, ('GND', '3V3', 'VBAT', '3V3')))    # AMS1117-3.3
    add(fp_smd('C1', -5.5, 30.0, 90, '10uF'))                            # AMS in  VBAT-GND
    add(fp_smd('C2', 5.5, 30.0, 90, '22uF'))                             # AMS out 3V3-GND
    add(fp_smd('C7', 3.0, 30.0, 90, '1uF'))                              # ESP 3V3 decouple
    add(fp_smd('R3', -3.2, 33.6, 90, '10k'))                             # IO2 pull-up to 3V3

    # --- left motor driver (lying, pins 1-4 = rear row, outputs 5-8 = front row) ---
    add(fp_dip8('U3', -32.5, 6.8, 90, {'1': 'BI_A', '2': 'FI_A', '3': 'GND', '4': 'VBAT', '5': 'MA1', '6': 'MA1', '7': 'MA2', '8': 'MA2'}))
    add(fp_radial('C3', -24.4, 3.0, 90, 6.3, 2.5, '220uF'))             # in the housing air gap, like EVA-RT
    add(fp_smd('C4', -29.96, 0.9, 180, '100nF'))                         # under pins 3-4
    add(fp_wirepads('MA', -39.6, 10.9, 270, ['MA1', 'MA2'], 'MOT ESQ', pitch=3.0, d=1.8, drill=0.9))

    # --- right motor driver (same orientation) ---
    add(fp_dip8('U4', 32.5, 6.8, 90, {'1': 'BI_B', '2': 'FI_B', '3': 'GND', '4': 'VBAT', '5': 'MB1', '6': 'MB1', '7': 'MB2', '8': 'MB2'}))
    add(fp_radial('C5', 24.4, 3.0, 90, 6.3, 2.5, '220uF'))
    add(fp_smd('C6', 35.04, 0.9, 180, '100nF'))                          # under pins 3-4
    add(fp_smd('R6', 26.4, 7.6, 90, '10k'))                              # FI_B pull-down (IO6)
    add(fp_wirepads('MB', 39.6, 10.9, 270, ['MB2', 'MB1'], 'MOT DIR', pitch=3.0, d=1.8, drill=0.9))

    # --- turbine: pads + MOSFET (bottom SOT-23) + gate parts, below the right driver ---
    add(fp_wirepads('TP', 28.6, -3.4, 180, ['VBAT', 'TURB_N'], 'TURBINA'))
    add(fp_sot23('Q1', 25.6, -6.6, 0, ('GATE', 'GND', 'TURB_N')))
    add(fp_smd('R1', 28.4, -8.6, 0, '220R'))                             # gate series IO3->GATE
    add(fp_smd('R2', 25.0, -10.0, 0, '10k'))                             # gate pull-down

    # --- battery: XT30PW-M overhanging the back edge ---
    add(fp_xt30('J1', 0.0, -29.0, 180))

    # --- mark sensors on the lateral arms (bottom QRE) ---
    add(fp_qre('SL', -68.0, 4.5, 0))
    add(fp_smd('R4', -58.0, 2.0, 0, '150R'))                             # LED L  3V3->anode
    add(fp_smd('R8', -58.0, 7.0, 0, '47k'))                              # pull-up L 3V3->MK_L
    add(fp_qre('SR', 68.0, 4.5, 0))
    add(fp_smd('R5', 58.0, 2.0, 0, '150R'))
    add(fp_smd('R9', 58.0, 7.0, 0, '47k'))
    return C

NETMAP = {
    'U1.5V': 'NC_5V', 'U1.GND': 'GND', 'U1.3V3': '3V3',
    'U1.IO10': 'FI_A', 'U1.IO7': 'BI_A', 'U1.IO6': 'FI_B', 'U1.IO5': 'BI_B',
    'U1.IO8': 'S0', 'U1.IO9': 'S1', 'U1.IO20': 'S2', 'U1.IO21': 'S3',
    'U1.IO4': 'C0', 'U1.IO3': 'GATE_D', 'U1.IO2': 'BTN', 'U1.IO1': 'MK_R', 'U1.IO0': 'MK_L',
    'J2.1': '3V3', 'J2.2': 'GND', 'J2.3': 'NC_J2', 'J2.4': 'C0', 'J2.5': 'S3', 'J2.6': 'S2', 'J2.7': 'S1', 'J2.8': 'S0',
    'U2.1': 'GND', 'U2.2': '3V3', 'U2.3': 'VBAT', 'U2.4': '3V3',
    'C1.1': 'VBAT', 'C1.2': 'GND', 'C2.1': '3V3', 'C2.2': 'GND', 'C7.1': '3V3', 'C7.2': 'GND',
    'R3.1': '3V3', 'R3.2': 'BTN',
    'J1.1': 'VBAT', 'J1.2': 'GND', 'J1.M1': 'GND', 'J1.M2': 'GND',
    'U3.1': 'BI_A', 'U3.2': 'FI_A', 'U3.3': 'GND', 'U3.4': 'VBAT', 'U3.5': 'MA1', 'U3.6': 'MA1', 'U3.7': 'MA2', 'U3.8': 'MA2',
    'U4.1': 'BI_B', 'U4.2': 'FI_B', 'U4.3': 'GND', 'U4.4': 'VBAT', 'U4.5': 'MB1', 'U4.6': 'MB1', 'U4.7': 'MB2', 'U4.8': 'MB2',
    'C3.1': 'VBAT', 'C3.2': 'GND', 'C4.1': 'GND', 'C4.2': 'VBAT', 'C5.1': 'VBAT', 'C5.2': 'GND', 'C6.1': 'GND', 'C6.2': 'VBAT',
    'R6.1': 'FI_B', 'R6.2': 'GND',
    'MA.1': 'MA1', 'MA.2': 'MA2', 'MB.1': 'MB1', 'MB.2': 'MB2', 'TP.1': 'VBAT', 'TP.2': 'TURB_N',
    'Q1.1': 'GATE', 'Q1.2': 'GND', 'Q1.3': 'TURB_N', 'R1.1': 'GATE_D', 'R1.2': 'GATE', 'R2.1': 'GATE', 'R2.2': 'GND',
    'SW1.1': 'BTN', 'SW1.2': 'GND',
    'SL.1': 'LEDA_L', 'SL.2': 'GND', 'SL.3': 'GND', 'SL.4': 'MK_L',
    'SR.1': 'LEDA_R', 'SR.2': 'GND', 'SR.3': 'GND', 'SR.4': 'MK_R',
    'R4.1': '3V3', 'R4.2': 'LEDA_L', 'R8.1': '3V3', 'R8.2': 'MK_L',
    'R5.1': '3V3', 'R5.2': 'LEDA_R', 'R9.1': '3V3', 'R9.2': 'MK_R',
}

WIDTHS = {'VBAT': [1.2, 0.9], 'MA1': [1.0, 0.8], 'MA2': [1.0, 0.8], 'MB1': [1.0, 0.8], 'MB2': [1.0, 0.8],
          'TURB_N': [1.0, 0.8], '3V3': [0.9, 0.7], 'GND': [1.0, 0.8]}
DEFAULT_W = [0.8, 0.7]

def nets_from(C):
    nets = {}
    for c in C.values():
        for p in c.pads:
            key = f'{c.ref}.{p.pin}'
            n = NETMAP.get(key, 'NC_' + key)
            p.net = n
            nets.setdefault(n, []).append(p)
    return nets

def collision_report(C):
    """Check every placed component against the keepouts and the outline (height-aware)."""
    out = outline_poly().buffer(0.3)
    toph = top_keepouts_h()
    botko = bottom_keepouts()
    allow_suction = {'J1'}          # the XT30 sits in the back free strip; pins checked below anyway
    allow_batt = {'J1'}             # XT30 is the battery connector
    msgs = []
    for ref, c in sorted(C.items()):
        for p in c.pads:
            # only bottom SMD and through-hole leads reach the bottom face (suction plate); top SMD is fine
            if p.side in ('bottom', 'tht') and ref not in allow_suction and SUCTION.buffer(-0.1).contains(Point(p.x, p.y)):
                msgs.append(f'  [SUCCAO] {ref}.{p.pin} ({p.net}) em ({p.x:.1f},{p.y:.1f})')
            if not out.contains(Point(p.x, p.y)):
                tag = 'AVISO fixacao fora da placa' if getattr(p, 'opt', False) else 'FORA DA PLACA'
                msgs.append(f'  [{tag}] {ref}.{p.pin} em ({p.x:.1f},{p.y:.1f})')
            for hx, hy, hd, rk in HOLES:
                if p.geom().distance(Point(hx, hy)) < rk - 1e-6 and not getattr(p, 'opt', False):
                    msgs.append(f'  [COBRE PERTO DE FURO] {ref}.{p.pin} a {p.geom().distance(Point(hx, hy)):.2f} mm do furo ({hx},{hy})')
        if c.body is None:
            continue
        if c.side == 'bottom':
            for name, polys in botko.items():
                for poly in polys:
                    if c.body.intersection(poly).area > 0.3:
                        msgs.append(f'  [BOTTOM x {name}] {ref} ({c.value})')
                        break
        else:
            for name, poly, min_h in toph:
                if name == 'bateria' and ref in allow_batt:
                    continue
                if c.height > min_h and c.body.intersection(poly).area > 0.3:
                    msgs.append(f'  [TOP x {name}] {ref} ({c.value}) h={c.height}')
                    break
    # pad-to-pad clearance between different nets (copper is all on the bottom layer)
    allp = [p for c in C.values() for p in c.pads]
    geo = [p.geom() for p in allp]
    for i in range(len(allp)):
        for j in range(i + 1, len(allp)):
            a, b = allp[i], allp[j]
            if a.ref == b.ref or (a.net and a.net == b.net and not a.net.startswith('NC_')):
                continue
            d = geo[i].distance(geo[j])
            if d < 0.6:
                msgs.append(f'  [FOLGA PAD {d:.2f}mm] {a.ref}.{a.pin}({a.net}) x {b.ref}.{b.pin}({b.net})')
    # top bodies overlapping each other (PTH parts share the top side)
    tops = [c for c in C.values() if c.side == 'top' and c.body is not None and c.kind != 'wire']
    for i in range(len(tops)):
        for j in range(i + 1, len(tops)):
            if tops[i].body.intersection(tops[j].body).area > 0.3:
                msgs.append(f'  [CORPOS SOBREPOSTOS] {tops[i].ref} x {tops[j].ref}')
    return msgs


# ===================== v2 (double-sided) overrides =====================
from build_v2 import build_v2, NETMAP_V2
build_v1, NETMAP_V1 = build, NETMAP
build = build_v2
NETMAP.clear(); NETMAP.update(NETMAP_V2)


# ===================== v3 (Erick's layout from the editor) =====================
from build_v3 import build_v3, outline_v3
build = build_v3
outline_poly = outline_v3
BATTERY_HOLDER_H = 3.0   # EVA-RT battery_holder.stl: battery rests 3 mm above the board

def _tk_v3():
    ko = []
    for name, poly, mh in _tk_v2():
        if name == 'bateria':
            mh = BATTERY_HOLDER_H - 0.5      # low SMD (<=2.5 mm) may sit under the battery, like EVA-RT's ATmega
        ko.append((name, poly, mh))
    return ko
_tk_v2 = top_keepouts_h
top_keepouts_h = _tk_v3
