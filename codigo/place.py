import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle, Rectangle
from shapely.geometry import Point
import design as D

def polys(g):
    if g is None or g.is_empty: return []
    return list(g.geoms) if hasattr(g, 'geoms') else [g]

def render(fn='placement.png'):
    C = D.build()
    nets = D.nets_from(C)
    out = D.outline_poly()
    fig, ax = plt.subplots(figsize=(15, 11), dpi=100)
    for p in polys(out):
        ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc='#e9dcc0', ec='#5a4630', lw=1.4, zorder=0))
    # keepouts
    for name, pls in D.top_keepouts().items():
        for p in pls:
            for g in polys(p):
                ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fc='#8aa0ff', ec='#4452c0', lw=0.5, alpha=0.22, zorder=1))
    for p in polys(D.SUCTION):
        ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc='none', ec='#2a9d8f', lw=1.0, ls='--', zorder=2))
    for x, y in D.GEARBOX_SCREWS:
        ax.add_patch(Circle((x, y), 2.6, fc='#f4a26133', ec='#e76f51', lw=0.5, ls=':', zorder=2))
    # holes / slots
    for x, y, d, rk in D.HOLES:
        ax.add_patch(Circle((x, y), d / 2, fc='white', ec='k', lw=0.7, zorder=3))
        ax.add_patch(Circle((x, y), rk, fc='none', ec='#aaa', lw=0.4, ls=':', zorder=3))
    for s in D.SLOTS:
        ax.add_patch(MPoly(list(s.exterior.coords), closed=True, fc='white', ec='k', lw=0.6, zorder=3))
    # components
    for ref, c in C.items():
        col = '#1d3557' if c.side == 'top' else '#9b2226'
        for p in polys(c.body):
            ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc=col + '18', ec=col, lw=0.9,
                               ls='-' if c.side == 'top' else '--', zorder=4))
        if getattr(c, 'usb', None) is not None:
            for p in polys(c.usb):
                ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc='#555', ec='k', lw=0.4, zorder=5))
        ax.text(c.x, c.y, ref, fontsize=6, ha='center', va='center', color=col, zorder=7,
                bbox=dict(fc='white', ec='none', alpha=0.65, pad=0.4))
        for p in c.pads:
            fc = '#c05030' if p.side == 'bottom' else '#d9a441'
            if p.shape == 'circle':
                ax.add_patch(Circle((p.x, p.y), p.w / 2, fc=fc, ec='k', lw=0.3, zorder=6))
                if p.drill:
                    ax.add_patch(Circle((p.x, p.y), p.drill / 2, fc='white', ec='none', zorder=6))
            else:
                ax.add_patch(Rectangle((p.x - p.w / 2, p.y - p.h / 2), p.w, p.h, fc=fc, ec='k', lw=0.3, zorder=6))
    ax.set_xlim(-78, 78); ax.set_ylim(-36, 46); ax.set_aspect('equal')
    ax.set_title('Posicionamento v1 — azul=keepout topo, tracejado verde=placa succao (sem PTH/SMD), '
                 'vermelho=SMD no cobre', fontsize=9)
    ax.grid(True, lw=0.2, alpha=0.5)
    b = out.bounds
    ax.text(0, -34, f'placa {b[2]-b[0]:.0f} x {b[3]-b[1]:.0f} mm (EVA-RT ~100x61 + bracos)', ha='center', fontsize=8)
    fig.tight_layout(); fig.savefig(fn); plt.close(fig)
    print('nets:', len(nets), ' comps:', len(C))
    print('OUTLINE %.0f x %.0f mm' % (b[2] - b[0], b[3] - b[1]))
    msgs = D.collision_report(C)
    if msgs:
        print('COLISOES/AVISOS:')
        print('\n'.join(msgs))
    else:
        print('sem colisoes')

if __name__ == '__main__':
    render()
