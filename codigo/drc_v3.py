"""Independent DRC + connectivity + render for the routed v3 board (vector, shapely-based)."""
import pickle, math, sys
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
import design as D
import router2 as R2

CLR, EDGE, MINW = 0.6, 0.6, 0.7


def load(tag='v3'):
    R = pickle.load(open(f'route_{tag}.pkl', 'rb'))
    C = D.build()
    nets = {n: ps for n, ps in D.nets_from(C).items() if not n.startswith('NC_')}
    return R, C, nets


def copper(R, C, nets):
    """per net, per layer: list of (kind, geom)."""
    cu = {}
    for n, ps in nets.items():
        for p in ps:
            for L in getattr(p, 'layers', ('B',)):
                cu.setdefault(n, {}).setdefault(L, []).append(('pad', p.geom(), f'{p.ref}.{p.pin}'))
            if p.side == 'tht' and len(getattr(p, 'layers', ('B',))) == 1:
                L2 = 'T' if p.layers[0] == 'B' else 'B'
                cu.setdefault(n, {}).setdefault(L2, []).append(('ring', Point(p.x, p.y).buffer(max(p.drill / 2 + 0.45, 0.8), 16), f'{p.ref}.{p.pin}'))
    for n, tr in R['tracks'].items():
        for L, coords, w in tr:
            if len(coords) >= 2:
                cu.setdefault(n, {}).setdefault(L, []).append(('trk', LineString(coords).buffer(w / 2, 8), f'trilha {w}'))
    for n, vs in R['vias'].items():
        for x, y in vs:
            for L in ('T', 'B'):
                cu.setdefault(n, {}).setdefault(L, []).append(('via', Point(x, y).buffer(R2.VIA_D / 2, 16), f'via({x:.1f},{y:.1f})'))
    for n, ex in R.get('extra', {}).items():
        for L, coords in ex:
            cu.setdefault(n, {}).setdefault(L, []).append(('area', Polygon(coords), 'area'))
    return cu


def drc(R, C, nets, verbose=True):
    cu = copper(R, C, nets)
    out = D.outline_poly()
    errs = []
    # 1) clearance between different nets on the same layer (tracks/vias vs anything)
    for L in ('T', 'B'):
        items = []
        for n, d in cu.items():
            for kind, g, lbl in d.get(L, []):
                items.append((n, kind, g, lbl))
        from shapely.strtree import STRtree
        geoms = [it[2] for it in items]
        tree = STRtree(geoms)
        for i, (n, kind, g, lbl) in enumerate(items):
            if kind not in ('trk', 'via', 'area'):
                continue
            for j in tree.query(g.buffer(CLR - 0.02)):
                if j == i:
                    continue
                n2, k2, g2, l2 = items[j]
                if n2 == n:
                    continue
                d = g.distance(g2)
                if d < CLR - 0.02:
                    errs.append(f'[{L}] folga {d:.2f} mm: {n} ({lbl}) x {n2} ({l2})')
    # 2) edge clearance and holes for tracks/vias
    edge = out.exterior
    for n, d in cu.items():
        for L, lst in d.items():
            for kind, g, lbl in lst:
                if kind not in ('trk', 'via'):
                    continue
                if not out.contains(g):
                    errs.append(f'[{L}] {n} {lbl} sai da placa')
                elif g.distance(edge) < EDGE - 0.02:
                    errs.append(f'[{L}] {n} {lbl} a {g.distance(edge):.2f} mm da borda')
                for hx, hy, hd, rk in D.HOLES:
                    if g.distance(Point(hx, hy)) < rk - 0.02:
                        errs.append(f'[{L}] {n} {lbl} a {g.distance(Point(hx, hy)):.2f} mm do furo ({hx},{hy})')
    # 3) min width
    for n, tr in R['tracks'].items():
        for L, coords, w in tr:
            if w < MINW - 1e-6:
                errs.append(f'{n}: trilha {w} < {MINW}')
    # 4) vias in forbidden zones
    for n, vs in R['vias'].items():
        for x, y in vs:
            if D.SUCTION_REAL.buffer(0.5 + 0.9).contains(Point(x, y)):
                errs.append(f'via {n} ({x:.1f},{y:.1f}) dentro da placa de succao')
    # 5) connectivity per net (vector union across layers through vias / 2-layer pads)
    disc = []
    for n, ps in nets.items():
        if len(ps) < 2:
            continue
        lay = {L: unary_union([g for k, g, l in cu[n].get(L, []) if k != 'ring']) for L in ('T', 'B')}
        parts = []
        for L in ('T', 'B'):
            gg = lay[L]
            for p in (gg.geoms if hasattr(gg, 'geoms') else [gg]):
                if not p.is_empty:
                    parts.append((L, p))
        parent = list(range(len(parts)))
        def f(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        links = [Point(x, y) for x, y in R['vias'].get(n, [])] + [Point(p.x, p.y) for p in ps if len(getattr(p, 'layers', ())) == 2]
        for pt in links:
            ids = [i for i, (L, p) in enumerate(parts) if p.buffer(0.05).contains(pt)]
            for a in ids[1:]:
                parent[f(a)] = f(ids[0])
        grp = {}
        for p in ps:
            pt = Point(p.x, p.y)
            ids = [i for i, (L, q) in enumerate(parts) if L in getattr(p, 'layers', ('B',)) and q.buffer(0.05).contains(pt)]
            key = f(ids[0]) if ids else ('solto', p.ref, p.pin)
            grp.setdefault(key, []).append(f'{p.ref}.{p.pin}')
        if len(grp) > 1:
            disc.append((n, list(grp.values())))
    if verbose:
        print(f'DRC: {len(errs)} violacoes')
        for e in errs[:60]:
            print('  ', e)
        print(f'Conectividade: {len(disc)} redes abertas')
        for n, g in disc:
            print('  ', n, g)
    return errs, disc, cu


def render(R, C, nets, fn, title='', pours=None, grid=None):
    fig, axs = plt.subplots(1, 2, figsize=(22, 8.5), dpi=110)
    out = D.outline_poly()
    for ax, L, col in ((axs[0], 'T', '#c0392b'), (axs[1], 'B', '#1f6fb2')):
        ax.add_patch(MPoly(list(out.exterior.coords), closed=True, fc='#efe3c6', ec='#5a4630', lw=1.4, zorder=0))
        if pours is not None and grid is not None:
            import numpy as np
            m = pours[L]
            ext = [grid.x0, grid.x0 + grid.W * R2.RES, grid.y0, grid.y0 + grid.H * R2.RES]
            img = np.zeros(m.shape + (4,)); img[m] = [0.75, 0.55, 0.3, 0.45]
            ax.imshow(img, origin='lower', extent=ext, zorder=1, interpolation='nearest')
        for n, tr in R['tracks'].items():
            for LL, coords, w in tr:
                if LL != L or len(coords) < 2:
                    continue
                g = LineString(coords).buffer(w / 2, 8)
                for p in (g.geoms if hasattr(g, 'geoms') else [g]):
                    ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc=col, ec='none', alpha=0.9, zorder=3))
        for n, ex in R.get('extra', {}).items():
            for LL, coords in ex:
                if LL == L:
                    ax.add_patch(MPoly(coords, closed=True, fc=col, ec='none', alpha=0.9, zorder=3))
        for ref, c in C.items():
            for p in c.pads:
                lay = getattr(p, 'layers', ('B',))
                g = p.geom()
                fc = col if L in lay else '#bbbbbb'
                ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fc=fc, ec='k', lw=0.3, zorder=4))
                if p.drill:
                    ax.add_patch(Circle((p.x, p.y), p.drill / 2, fc='white', ec='none', zorder=5))
            if c.side in ('top', 'bottom') and ((c.side == 'top') == (L == 'T')) and c.body is not None:
                ax.add_patch(MPoly(list(c.body.exterior.coords), closed=True, fc='none', ec='#333', lw=0.5, ls=':', zorder=6))
            ax.text(c.x, c.y, ref, fontsize=6, ha='center', va='center', zorder=7, color='#111',
                    bbox=dict(fc='white', ec='none', alpha=0.5, pad=0.2))
        for n, vs in R['vias'].items():
            for x, y in vs:
                ax.add_patch(Circle((x, y), R2.VIA_D / 2, fc='#2a9d8f' if n == 'GND' else '#f4a261', ec='k', lw=0.4, zorder=8))
                ax.add_patch(Circle((x, y), 0.4, fc='white', ec='none', zorder=9))
        for x, y, d, rk in D.HOLES:
            ax.add_patch(Circle((x, y), d / 2, fc='white', ec='k', lw=0.6, zorder=8))
        ax.set_xlim(out.bounds[0] - 2, out.bounds[2] + 2); ax.set_ylim(out.bounds[1] - 2, out.bounds[3] + 2)
        ax.set_aspect('equal'); ax.grid(lw=0.2, alpha=0.4)
        ax.set_title(f'{"CIMA (componentes)" if L == "T" else "BAIXO (cobre, visto de CIMA = transparente)"} — {title}', fontsize=10)
    fig.tight_layout(); fig.savefig(fn); plt.close(fig)


if __name__ == '__main__':
    R, C, nets = load()
    drc(R, C, nets)
    render(R, C, nets, 'route_v3_check.png', 'teste')
