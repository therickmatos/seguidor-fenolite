import time, sys
import numpy as np
from scipy import ndimage
from shapely.geometry import Point
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
from router import Board, RES, CLR, EDGE
import design as D

def make_board():
    C = D.build()
    nets = D.nets_from(C)
    outline = D.outline_poly()
    extra = [s.buffer(0.5) for s in D.SLOTS] + [Point(x, y).buffer(2.6, 16) for x, y in D.GEARBOX_SCREWS]
    b = Board(outline, D.HOLES, C, nets, D.WIDTHS, D.DEFAULT_W, keepout_copper=extra)
    return b

def compute_pour(b, gnd='GND'):
    g = b.g
    other = b.other_mask(gnd)
    d_other = ndimage.distance_transform_edt(~other) * RES
    pour = (d_other >= CLR) & (b.d_out >= EDGE) & (b.d_ko >= 0.05)
    rad = int(round(0.35 / RES))
    yy, xx = np.mgrid[-rad:rad + 1, -rad:rad + 1]
    st = (xx ** 2 + yy ** 2) <= rad ** 2
    pour = ndimage.binary_opening(pour, structure=st)
    gcu = pour | b.copper[gnd]
    lab, n = ndimage.label(gcu, structure=np.ones((3, 3)))
    pad_lab = {}
    for p in b.nets[gnd]:
        r, c = g.to_rc(p.x, p.y)
        pad_lab[f'{p.ref}.{p.pin}'] = int(lab[r, c])
    return pour, lab, pad_lab

def islands(pad_lab):
    groups = {}
    for k, v in pad_lab.items():
        groups.setdefault(v, []).append(k)
    return sorted(groups.values(), key=len, reverse=True)

def render(b, fn, pour=None, title=''):
    fig, ax = plt.subplots(figsize=(16, 10), dpi=100)
    ob = b.outline
    for p in ([ob] if ob.geom_type == 'Polygon' else ob.geoms):
        ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc='#e9dcc0', ec='#5a4630', lw=1.2, zorder=0))
    g = b.g
    ext = [g.x0 - RES / 2, g.x0 + (g.W - 0.5) * RES, g.y0 - RES / 2, g.y0 + (g.H - 0.5) * RES]
    cu = np.zeros((g.H, g.W, 4))
    if pour is not None:
        cu[pour] = [0.80, 0.52, 0.26, 0.5]
    allcu = np.zeros((g.H, g.W), bool)
    for n, m in b.copper.items():
        if not n.startswith('NC_'):
            allcu |= m
    cu[allcu] = [0.76, 0.40, 0.12, 0.96]
    ax.imshow(cu, origin='lower', extent=ext, zorder=1, interpolation='nearest')
    for x, y, d, rk in D.HOLES:
        ax.add_patch(Circle((x, y), d / 2, fc='white', ec='k', lw=0.6, zorder=3))
    for s in D.SLOTS:
        ax.add_patch(MPoly(list(s.exterior.coords), closed=True, fc='white', ec='k', lw=0.5, zorder=3))
    for ref, c in b.comps.items():
        ax.text(c.x, c.y, ref, fontsize=5.5, ha='center', va='center', color='#1d3557', zorder=6,
                bbox=dict(fc='white', ec='none', alpha=0.55, pad=0.3))
        for p in c.pads:
            if p.side == 'tht' and p.drill:
                ax.add_patch(Circle((p.x, p.y), p.drill / 2, fc='white', ec='none', zorder=5))
    for net, a, bb in b.jumpers:
        ax.plot([a[0], bb[0]], [a[1], bb[1]], color='#d00000', lw=2.0, zorder=7)
        for pt in (a, bb):
            ax.add_patch(Circle(pt, 0.5, fc='white', ec='#d00000', lw=1.0, zorder=8))
    ax.set_xlim(ob.bounds[0] - 3, ob.bounds[2] + 3)
    ax.set_ylim(ob.bounds[1] - 3, ob.bounds[3] + 3)
    ax.set_aspect('equal'); ax.set_title(title, fontsize=10); ax.grid(True, lw=0.2, alpha=0.4)
    fig.tight_layout(); fig.savefig(fn); plt.close(fig)

def run(order, fn='routed.png'):
    b = make_board()
    t0 = time.time()
    skip = {'GND'}  # GND is the pour, not a routed net
    for net in order:
        if net in b.nets and net not in skip:
            b.route_net(net)
    for net in b.nets:
        if net not in order and net not in skip and not net.startswith('NC_') and len(b.nets[net]) > 1:
            b.route_net(net)
    sig = len(b.jumpers)
    pour, lab, pad_lab = compute_pour(b)
    grp = islands(pad_lab)
    # realistic single-sided fix: stitch each GND island to the main pour with one jumper
    gnd_stitch = stitch_gnd(b, lab, grp)
    dt = time.time() - t0
    tot = len(b.jumpers)
    print(f'tempo {dt:.0f}s  jumpers_sinais={sig}  stitches_GND={gnd_stitch}  TOTAL={tot}  ilhas_GND_restantes={len(grp)-1}')
    from collections import Counter
    print('jumpers por net:', dict(Counter(j[0] for j in b.jumpers)))
    render(b, fn, pour, title=f'jumpers sinais={sig} + GND={gnd_stitch} = {tot}')
    return b, grp

def stitch_gnd(b, lab, grp):
    """One jumper per GND island -> nearest cell of the main (largest) GND region."""
    if len(grp) <= 1:
        return 0
    g = b.g
    main = lab == max(range(1, lab.max() + 1), key=lambda k: (lab == k).sum())
    import numpy as np
    mr, mc = np.nonzero(main)
    n = 0
    for isl in grp[1:]:
        p = b.nets['GND'][0]
        for pad in b.nets['GND']:
            if f'{pad.ref}.{pad.pin}' == isl[0]:
                p = pad; break
        r0, c0 = g.to_rc(p.x, p.y)
        d2 = (mr - r0) ** 2 + (mc - c0) ** 2
        k = int(d2.argmin())
        x1, y1 = g.to_xy(mr[k], mc[k])
        b.jumpers.append(('GND', (p.x, p.y), (x1, y1)))
        n += 1
    return n

if __name__ == '__main__':
    order = ['VBAT', 'MA1', 'MA2', 'MB1', 'MB2', 'TURB_N', '3V3',
             'S0', 'S1', 'S2', 'S3', 'C0', 'FI_A', 'BI_A', 'FI_B', 'BI_B',
             'GATE', 'GATE_D', 'BTN', 'MK_L', 'MK_R', 'LEDA_L', 'LEDA_R']
    run(order)
