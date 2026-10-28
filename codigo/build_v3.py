"""v3 = Erick's editor layout (layout_erick.json) + tidy-up. Double-sided routing data (pad layers)."""
import json, os, re, inspect
from geom import *
import build_v2

HERE = os.path.dirname(os.path.abspath(__file__))

# which through-hole parts can ALSO be soldered on the top layer (lead accessible from the component side).
# DIP-8 sits on its lead shoulders and electrolytics stand ~1 mm off the board: both can be soldered on top
# (standard practice on home-made double-sided boards without plated holes). ESP module is flush: bottom only.
TOP_SOLDERABLE = {'MA', 'MB', 'TP', 'J1', 'J2', 'U3', 'U4', 'C3', 'C5'}

# tidy-up applied on top of Erick's positions (ref -> (x, y, ang))
TWEAKS = {
    'U1': (0.0, 32.5, 90),       # ESP 2.5 mm forward: turn band between suction-plate edge and the rear pin row
    'J2': (0.0, 45.3, 0),        # header ahead of the ESP: 3V3 via + top jog fit between the rows
    'U3': (-34.5, 7.4, 270),     # inputs (pins 1-2) on the inner end of the top row, outputs on the bottom row
    'MA': (-34.5, 0.6, 0),       # motor pads just below U3 outputs (pitch 5.08: MA1 under FO, MA2 under BO)
    'MB': (28.5, 12.5, 0),       # centred over U4, same height as MA (symmetric)
    'C4': (-37.04, 12.31, 0),    # 100 nF across U3 pins 4-3 (bottom), offset toward the edge
    'C6': (31.04, -0.31, 180),   # 100 nF soldered straight across U4 pins 3-4 (bottom)
    'R6': (27.23, -2.95, 90),    # FI_B pull-down hanging from U4 pin 2 (bottom)
    'R7': (-34.5, 8.9, 0),       # FI_A (IO6) pull-down between U3 pins 2 and 3, under the DIP (bottom)
    'C3': (-26.0, 11.5, 180),    # 1 mm away from the U3 body
    'C1': (22.0, -26.9, 180),    # AMS input cap right under its IN (VBAT) and GND pins
    'C2': (26.6, -18.0, 90),     # AMS output cap beside the tab (3V3 low pad, GND high pad), off the housing foot
    # mark-sensor resistors moved to the arm roots (Erick's suggestion): only LEDA + MK (+GND) enter each arm
    'R4': (-45.0, 2.4, 0),       # LED L 470R: VBAT end toward the body, LEDA end feeds the arm's lower row
    'R5': (45.0, 6.6, 180),      # LED R 470R: LEDA end feeds the arm's upper row (SR rotated 180)
    'SR': (68.0, 4.5, 180),      # same pin arrangement as SL: anode/collector toward the root, K/E outboard
}


def _factories():
    src = inspect.getsource(build_v2.build_v2)
    f = {}
    for line in src.splitlines():
        m = re.search(r"add\((fp_\w+)\('(\w+)',\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)(.*)\)\)", line)
        if m:
            f[m.group(2)] = (m.group(1), m.group(6))
    return f


def build_v3():
    L = json.load(open(os.path.join(HERE, 'layout_erick.json')))
    C = {}
    for ref, (fn, rest) in _factories().items():
        p = L['comps'].get(ref)
        if p is None and ref not in TWEAKS:
            continue
        x, y, a = (p['x'], p['y'], p['ang']) if p else TWEAKS[ref]
        if ref in TWEAKS:
            x, y, a = TWEAKS[ref]
        C[ref] = eval(f"{fn}('{ref}', {x}, {y}, {a}{rest})")
    for ref, c in C.items():
        for pd in c.pads:
            if pd.side == 'tht':
                pd.layers = ('B', 'T') if ref in TOP_SOLDERABLE else ('B',)
            elif pd.side == 'top':
                pd.layers = ('T',)
            else:
                pd.layers = ('B',)
    return C


def outline_v3():
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    L = json.load(open(os.path.join(HERE, 'layout_erick.json')))
    poly = Polygon(L['outline'])
    # nose 1 mm wider each side (12 -> 13): room for one track + GND strip past the ESP ends
    poly = unary_union([poly, box(-14.5, 18.24, 14.5, 47.0)])
    poly = poly.difference(box(-14.6, 32.5 - 5.2, -12.4, 32.5 + 5.2))   # notch: USB-C plug fits flush
    return poly.buffer(0)
