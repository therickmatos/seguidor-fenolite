"""Route the v3 board (double-sided) and report."""
import time, json, pickle, sys
import numpy as np
from shapely.geometry import Point, box, Polygon
from shapely.ops import unary_union
import design as D
import router2 as R2


def setup():
    C = D.build()
    nets = D.nets_from(C)
    # MA rotated 180 so pad1 (MA1/FO) sits above the FO pins: no crossing
    nets = {n: ps for n, ps in nets.items() if not n.startswith('NC_')}
    outline = D.outline_poly()
    # keep-outs
    tk = D.top_keepouts_h()
    via_forbid = []
    for name, poly, mh in tk:
        if name in ('pes da carcaca', 'caixa reducao', 'presilha vareta', 'janela helice'):
            via_forbid.append(poly)
    via_forbid.append(D.SUCTION)                                   # via solder blob under the suction plate
    via_forbid += [Point(x, y).buffer(2.6, 24) for x, y in D.GEARBOX_SCREWS]
    for c in C.values():                                           # no via under a component body (either face)
        if c.body is not None and c.kind != 'wire':
            via_forbid.append(c.body.buffer(0.3))
        for g in getattr(c, 'extra', []):
            pass
    esp = C['U1']
    top_trace_forbid = [esp.body.buffer(0.2), box(9.9, 23.5, 14.5, 41.7)]   # no top copper under the ESP / antenna
    antenna = box(9.9, 23.5, 14.5, 41.7)                           # ESP antenna end (USB is on the left)
    ko_bot = [Point(x, y).buffer(2.6, 24) for x, y in D.GEARBOX_SCREWS]
    ko_both = [s.buffer(0.5) for s in D.SLOTS]
    widths = {'VBAT': [1.5, 1.2, 1.0, 0.8], 'MA1': [1.4, 1.2, 1.0, 0.8], 'MA2': [1.4, 1.2, 1.0, 0.8],
              'MB1': [1.4, 1.2, 1.0, 0.8], 'MB2': [1.4, 1.2, 1.0, 0.8], 'TURB_N': [1.2, 1.0, 0.8],
              '3V3': [1.0, 0.9, 0.8, 0.7]}
    default_w = [0.9, 0.8, 0.7]
    b = R2.Board2(outline, C, nets, D.HOLES, widths, default_w, ko_both=ko_both, ko_top=[], ko_bot=ko_bot,
                  via_forbid=via_forbid, top_trace_forbid=top_trace_forbid)
    b.failed = []
    # heat spreader for the AMS1117 tab (3V3) on top, below the right motor
    u2 = C['U2']
    tab = u2.pad('4')
    b.extra['3V3'] = [('T', box(tab.x - 3.4, tab.y - 1.1, tab.x + 3.4, tab.y + 3.2))]
    b.refresh('3V3')
    b.prepare()
    return C, nets, b, antenna


ORDER = ['S0', 'S1', 'S2', 'S3', 'C0',
         'FI_A', 'BI_A', 'GATE_D', 'MK_L', 'BTN', 'BI_B', 'FI_B', 'MK_R',
         'VBAT', 'MA1', 'MA2', 'MB1', 'MB2', 'TURB_N', 'GATE',
         'LEDA_L', 'LEDA_R', '3V3', 'GND']


def run(order=ORDER, tag='v3'):
    C, nets, b, antenna = setup()
    t0 = time.time()
    for n in order:
        if n in nets:
            t1 = time.time()
            ok = b.route_net(n, verbose=True)
            print(f'  {n:7s} {"ok" if ok else "FALHOU"}  vias={len(b.vias.get(n, []))}  {time.time()-t1:.1f}s', flush=True)
    for n in nets:
        if n not in order:
            b.route_net(n, verbose=True)
    print(f'roteamento {time.time()-t0:.0f}s; falhas: {b.failed}')
    ko = {'T': b.g.raster([antenna])}
    pours = R2.pour(b, 'GND', keep_out=ko)
    groups, lab, find = R2.gnd_islands(b, pours)
    print('GND grupos antes da costura:', [len(x) for x in groups])
    st = R2.stitch(b, pours, 'GND', spacing=5.0)
    pours = R2.pour(b, 'GND', keep_out=ko)
    groups, lab, find = R2.gnd_islands(b, pours)
    print(f'costura: {len(st)} vias de GND; grupos depois: {[len(x) for x in groups]}')
    for it in range(12):
        if len(groups) <= 1:
            break
        isl = groups[-1]
        ok = R2.repair_island(b, pours, lab, find, isl, w=0.8) or R2.repair_island(b, pours, lab, find, isl, w=0.7)
        print(f'  reparo ilha {isl}: {"ok" if ok else "FALHOU"}')
        pours = R2.pour(b, 'GND', keep_out=ko)
        groups, lab, find = R2.gnd_islands(b, pours)
        if not ok:
            groups = groups[:-1] if len(groups) > 1 else groups
    groups, lab, find = R2.gnd_islands(b, pours)
    print(f'GND grupos finais: {[len(x) for x in groups]}')
    for gg in groups[1:]:
        print('   ilha:', gg)
    sig_vias = sum(len(v) for n, v in b.vias.items() if n != 'GND')
    print('vias de sinal/potencia:', sig_vias, {n: len(v) for n, v in b.vias.items() if n != 'GND' and v})
    pickle.dump(dict(tracks={n: [(L, list(ls.coords), w) for L, ls, w in v] for n, v in b.tracks.items()},
                     vias=b.vias, failed=b.failed, extra={n: [(L, list(p.exterior.coords)) for L, p in v] for n, v in b.extra.items()}),
                open(f'route_{tag}.pkl', 'wb'))
    b.pours = pours
    pickle.dump(dict(pours={L: pours[L] for L in pours}, grid=(b.g.x0, b.g.y0, b.g.W, b.g.H)), open(f'pours_{tag}.pkl', 'wb'))
    return C, nets, b, pours, groups


if __name__ == '__main__':
    run()
