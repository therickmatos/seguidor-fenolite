"""Diagnostic: GND pour components per layer, coloured by union-find group, + via-legal mask."""
import sys, pickle
import numpy as np
from scipy import ndimage
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
import design as D
import router2 as R2
import final_v3 as F


def groups_map(b, pours):
    groups, lab, find = R2.gnd_islands(b, pours)
    # root of each pad group
    roots = []
    for gp in groups:
        ref, pin = gp[0].split('.')
        p = [q for q in b.nets['GND'] if q.ref == ref and q.pin == pin][0]
        rr = None
        for L in b.pad_layers[(p.ref, p.pin)]:
            l, off = lab[L]
            r, c = b.g.rc(p.x, p.y)
            if l[r, c]:
                rr = find(off + int(l[r, c]))
        roots.append(rr)
    gm = {}
    for L in R2.LAYERS:
        l, off = lab[L]
        m = np.full(l.shape, -1, int)
        for k in np.unique(l[l > 0]):
            rt = find(off + int(k))
            gi = roots.index(rt) if rt in roots else 99
            m[l == k] = gi
        gm[L] = m
    return groups, gm


def main(tag='x2', spacing=3.5):
    C, nets, b, antenna = F.build_board(tag)
    ko = {'T': b.g.raster([antenna]), 'B': b.g.raster([antenna])}
    pours = R2.pour(b, 'GND', keep_out=ko)
    R2.stitch(b, pours, 'GND', spacing=spacing)
    pours = R2.pour(b, 'GND', keep_out=ko)
    groups, gm = groups_map(b, pours)
    for i, gp in enumerate(groups):
        print(i, gp)
    vneed = R2.VIA_D / 2 + R2.CLR + R2.MARGIN
    ok = b.via_ok.copy()
    for L in R2.LAYERS:
        d = ndimage.distance_transform_edt(~b.other_mask('GND', L)) * R2.RES
        ok &= d >= vneed
    g = b.g
    ext = [g.x0, g.x0 + g.W * R2.RES, g.y0, g.y0 + g.H * R2.RES]
    cols = np.array([[0.2, 0.6, 0.2, 0.6], [0.9, 0.2, 0.6, 0.6], [0.2, 0.3, 0.9, 0.6], [0.9, 0.6, 0.1, 0.6], [0.5, 0.1, 0.9, 0.6]])
    fig, axs = plt.subplots(1, 2, figsize=(26, 10), dpi=100)
    out = D.outline_poly()
    for ax, L in zip(axs, R2.LAYERS):
        ax.add_patch(MPoly(list(out.exterior.coords), closed=True, fc='#f4ecd8', ec='k', lw=1, zorder=0))
        img = np.zeros(gm[L].shape + (4,))
        for gi in range(len(groups)):
            img[gm[L] == gi] = cols[gi % len(cols)]
        img[gm[L] == 99] = [0.5, 0.5, 0.5, 0.5]
        ax.imshow(img, origin='lower', extent=ext, zorder=1, interpolation='nearest')
        okimg = np.zeros(ok.shape + (4,)); okimg[ok] = [0, 0, 0, 0.25]
        ax.imshow(okimg, origin='lower', extent=ext, zorder=2, interpolation='nearest')
        for n, tr in b.tracks.items():
            for LL, ls, w in tr:
                if LL == L:
                    xs, ys = ls.xy
                    ax.plot(xs, ys, color='k' if n != 'GND' else 'g', lw=1.2, zorder=3)
                    mid = ls.interpolate(0.5, normalized=True)
                    ax.text(mid.x, mid.y, n, fontsize=6, color='navy', zorder=6)
        for n, vs in b.vias.items():
            for x, y in vs:
                ax.add_patch(Circle((x, y), 0.9, fc='cyan' if n == 'GND' else 'orange', ec='k', lw=0.4, zorder=4))
        for ref, c in C.items():
            for p in c.pads:
                gp = p.geom()
                ax.add_patch(MPoly(list(gp.exterior.coords), closed=True, fc='none', ec='k', lw=0.4, zorder=4))
            ax.text(c.x, c.y, ref, fontsize=7, zorder=6, color='darkred')
        ax.set_xlim(out.bounds[0] - 1, out.bounds[2] + 1); ax.set_ylim(out.bounds[1] - 1, out.bounds[3] + 1)
        ax.set_aspect('equal'); ax.grid(lw=0.3, alpha=0.5)
        ax.set_xticks(range(-72, 73, 4)); ax.set_yticks(range(-36, 49, 4)); ax.tick_params(labelsize=6)
        ax.set_title(L)
    fig.tight_layout(); fig.savefig(f'/projects/sandbox/diag_{tag}.png'); plt.close(fig)


if __name__ == '__main__':
    main(*(sys.argv[1:2] or ['x2']))
