import json, math
import numpy as np, trimesh
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MP
from shapely.geometry import Polygon, Point
from analise_eva import shadow, section

M = 'EVA-RT/3d_models/'
res = {}

def polys(g):
    if g is None or g.is_empty: return []
    return list(g.geoms) if hasattr(g, 'geoms') else [g]

def draw(ax, g, **kw):
    for p in polys(g):
        ax.add_patch(MP(list(p.exterior.coords), closed=True, **kw))
        for h in p.interiors:
            ax.add_patch(MP(list(h.coords), closed=True, fc='white', ec=kw.get('ec', 'k'), lw=0.5))

fig, axs = plt.subplots(2, 3, figsize=(18, 12))
# 1) impeller base: shadows per band
m = trimesh.load(M + 'impeller_base_1.stl')
ax = axs[0, 0]
bands = [(0, 2, '#e63946'), (2, 6, '#f4a261'), (6, 11, '#2a9d8f'), (11, 12.5, '#457b9d'), (12.5, 14.2, '#1d3557')]
for z0, z1, c in bands[::-1]:
    s = shadow(m, z0 + 0.01, z1)
    draw(ax, s, fc=c, ec='k', lw=0.3, alpha=0.45)
    res[f'impeller_{z0}_{z1}'] = [list(p.exterior.coords) for p in polys(s)]
    print('impeller band', z0, z1, [(round(p.area), [round(v, 1) for v in p.bounds]) for p in polys(s)][:8])
for x in (15.556, -15.556):
    for y in (15.556, -15.556):
        ax.add_patch(plt.Circle((x, y), 1, fc='none', ec='k'))
ax.add_patch(plt.Circle((0, 0), 8.5, fc='none', ec='k'))
ax.set_title('impeller_base_1: sombra por faixa de z (vermelho z<2 ... azul-escuro z>12.5)')
ax.set_aspect('equal'); ax.set_xlim(-30, 30); ax.set_ylim(-30, 30); ax.grid(lw=0.3)

# polar analysis of legs at z 0..2
s = shadow(m, 0.01, 2.0)
for p in polys(s):
    c = p.centroid
    ang = [math.degrees(math.atan2(y, x)) for x, y in p.exterior.coords]
    rr = [math.hypot(x, y) for x, y in p.exterior.coords]
    print(f'  leg z<2: centroid ({c.x:.1f},{c.y:.1f}) r {min(rr):.1f}-{max(rr):.1f} ang {min(ang):.1f}..{max(ang):.1f} area {p.area:.0f}')
s = shadow(m, 2.0, 11.0)
for p in polys(s):
    rr = [math.hypot(x, y) for x, y in p.exterior.coords]
    print(f'  z2-11 part: bounds {[round(v,1) for v in p.bounds]} r {min(rr):.1f}-{max(rr):.1f} area {p.area:.0f} holes {len(p.interiors)}')

# 2) suction base
m = trimesh.load(M + 'suction_base.stl')
ax = axs[0, 1]
s = shadow(m, 0.0, 0.6)
draw(ax, s, fc='#90be6d', ec='k', lw=0.5, alpha=0.6)
for p in polys(s):
    print('suction part bounds', [round(v, 2) for v in p.bounds], 'area', round(p.area), 'holes', len(p.interiors))
    for h in p.interiors:
        hp = Polygon(h)
        print('   hole', [round(v, 2) for v in hp.bounds], round(hp.area, 1))
res['suction'] = [list(p.exterior.coords) for p in polys(s)]
ax.set_title('suction_base (coords do STL)'); ax.set_aspect('equal'); ax.grid(lw=0.3)
ax.autoscale_view()

# 3) gearbox: shadow in xy and side profiles
m = trimesh.load(M + 'gearbox.stl')
ax = axs[0, 2]
for z0, z1, c in [(-2.5, 0, '#e63946'), (0, 3, '#f4a261'), (3, 12, '#2a9d8f')][::-1]:
    s = shadow(m, z0 + 0.01, z1)
    draw(ax, s, fc=c, ec='k', lw=0.3, alpha=0.5)
    print('gearbox band', z0, z1, [(round(p.area), [round(v, 2) for v in p.bounds]) for p in polys(s)])
ax.set_title('gearbox xy (vermelho = abaixo de z=0: pinos)'); ax.set_aspect('equal'); ax.grid(lw=0.3); ax.autoscale_view()
# side section (plane x = 4.75) -> yz profile
ax = axs[1, 0]
for xc, c in [(1.0, '#e76f51'), (4.75, '#264653'), (8.5, '#2a9d8f')]:
    sec = m.section(plane_origin=[xc, 0, 0], plane_normal=[1, 0, 0])
    if sec is not None:
        for e in sec.discrete:
            ax.plot(e[:, 1], e[:, 2], color=c, lw=0.8, label=f'x={xc}')
ax.set_title('gearbox: perfis yz (seções em x)'); ax.set_aspect('equal'); ax.grid(lw=0.3)
# yz section along plane y=const to find bores (circles in xz)
ax = axs[1, 1]
for yc, c in [(-5.0, '#e76f51'), (0.0, '#264653'), (5.0, '#2a9d8f'), (12.0, '#9b2226')]:
    sec = m.section(plane_origin=[0, yc, 0], plane_normal=[0, 1, 0])
    if sec is not None:
        for e in sec.discrete:
            ax.plot(e[:, 0], e[:, 2], color=c, lw=0.8)
ax.set_title('gearbox: perfis xz (seções em y=-5,0,5,12)'); ax.set_aspect('equal'); ax.grid(lw=0.3)

# 4) clamp, battery holder, sledge, wheel
ax = axs[1, 2]
off = {'barilla_clamp': (0, 0), 'barilla_connection': (15, 0), 'battery_holder': (0, -15), 'sensor_sledge': (15, -15), 'bead': (30, 0), 'wheel_rim': (35, -20)}
for n, (dx, dy) in off.items():
    mm = trimesh.load(M + n + '.stl')
    s = shadow(mm, mm.bounds[0][2], mm.bounds[1][2])
    from shapely import affinity
    s = affinity.translate(s, dx, dy)
    draw(ax, s, fc='#adb5bd', ec='k', lw=0.4, alpha=0.6)
    ax.text(dx, dy + 9, n, fontsize=7, ha='center')
    ax.plot(dx, dy, 'r+')
ax.set_title('outras peças (cruz = origem do STL)'); ax.set_aspect('equal'); ax.grid(lw=0.3); ax.autoscale_view()
fig.tight_layout(); fig.savefig('stl_analise.png', dpi=80)
json.dump(res, open('stl_geom.json', 'w'))
