"""Extract EVA-RT geometry: outline (GKO), drills, and STL cross-sections."""
import re, json, glob, math
import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union, polygonize

G = 'EVA-RT/pcb_files/gerber/'
M = 'EVA-RT/3d_models/'


def parse_gerber_lines(fn):
    txt = open(fn).read()
    fmt = re.search(r'%FSLAX(\d)(\d)Y(\d)(\d)\*%', txt)
    dec = int(fmt.group(2)) if fmt else 4
    unit = 'MM' if '%MOMM*%' in txt else 'IN'
    sc = 10 ** dec
    x = y = 0.0
    segs, arcs = [], []
    mode = 'G01'
    for cmd in txt.replace('\n', '').split('*'):
        if cmd.startswith('G01'): mode = 'G01'; cmd = cmd[3:]
        elif cmd.startswith('G02'): mode = 'G02'; cmd = cmd[3:]
        elif cmd.startswith('G03'): mode = 'G03'; cmd = cmd[3:]
        m = re.match(r'(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0([123])$', cmd)
        if not m:
            continue
        nx = int(m.group(1)) / sc if m.group(1) else x
        ny = int(m.group(2)) / sc if m.group(2) else y
        i = int(m.group(3)) / sc if m.group(3) else 0
        j = int(m.group(4)) / sc if m.group(4) else 0
        d = m.group(5)
        if d == '1':
            if mode == 'G01':
                segs.append(((x, y), (nx, ny)))
            else:
                cx, cy = x + i, y + j
                r = math.hypot(x - cx, y - cy)
                a0 = math.atan2(y - cy, x - cx); a1 = math.atan2(ny - cy, nx - cx)
                if mode == 'G03':  # ccw
                    while a1 <= a0: a1 += 2 * math.pi
                else:
                    while a1 >= a0: a1 -= 2 * math.pi
                n = max(4, int(abs(a1 - a0) / math.radians(5)))
                pts = [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
                for p, q in zip(pts[:-1], pts[1:]):
                    segs.append((p, q))
        x, y = nx, ny
    return segs, unit


def parse_drill(fn):
    tools, holes, cur = {}, [], None
    for line in open(fn):
        line = line.strip()
        m = re.match(r'T(\d+)C([\d.]+)', line)
        if m:
            tools[m.group(1)] = float(m.group(2)); continue
        m = re.match(r'^T(\d+)$', line)
        if m:
            cur = m.group(1); continue
        m = re.match(r'X(-?[\d.]+)Y(-?[\d.]+)(?:G85X(-?[\d.]+)Y(-?[\d.]+))?', line)
        if m and cur:
            h = dict(d=tools[cur], x=float(m.group(1)), y=float(m.group(2)))
            if m.group(3):
                h['x2'] = float(m.group(3)); h['y2'] = float(m.group(4))
            holes.append(h)
    return holes


def section(mesh, z):
    """Cross-section at height z as a shapely (Multi)Polygon."""
    s = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None:
        return None
    p2, T = s.to_2D(to_2D=np.eye(4))
    polys = [p.buffer(0) for p in p2.polygons_full]
    return unary_union(polys) if polys else None


def shadow(mesh, z0, z1):
    """XY shadow of the part between heights z0..z1 (union of triangles touching the band)."""
    v = mesh.vertices[mesh.faces]
    zmin, zmax = v[:, :, 2].min(1), v[:, :, 2].max(1)
    sel = (zmax >= z0) & (zmin <= z1)
    tris = [Polygon(t[:, :2]).buffer(0.01) for t in v[sel]]
    tris = [t for t in tris if t.area > 0]
    return unary_union(tris).buffer(-0.01) if tris else None


if __name__ == '__main__':
    out = {}
    segs, unit = parse_gerber_lines(G + 'Gerber_BoardOutlineLayer.GKO')
    lines = [LineString(s) for s in segs if s[0] != s[1]]
    polys = list(polygonize(unary_union(lines)))
    polys.sort(key=lambda p: -p.area)
    print('GKO unit', unit, 'n segs', len(segs), 'polys', [round(p.area, 1) for p in polys[:6]])
    for p in polys[:4]:
        print('  bounds', [round(v, 2) for v in p.bounds])
    out['outline_polys'] = [list(map(lambda c: (round(c[0], 3), round(c[1], 3)), p.exterior.coords)) for p in polys[:4]]

    for fn in ['Drill_PTH_Through.DRL', 'Drill_NPTH_Through.DRL']:
        hs = parse_drill(G + fn)
        print(fn, len(hs))
        for h in hs:
            print('   ', h)
        out[fn] = hs

    for name in ['suction_base', 'impeller_base_1', 'gearbox', 'barilla_clamp', 'battery_holder', 'sensor_sledge', 'wheel_rim', 'bead']:
        m = trimesh.load(M + name + '.stl')
        b = m.bounds
        zs = np.linspace(b[0][2] + 0.05, b[1][2] - 0.05, 8)
        print(f'\n== {name}  bounds {b.round(2).tolist()}  vol {m.volume:.0f} mm3  (PLA ~{m.volume*1.24/1000:.2f} g)')
        out[name] = {}
        for z in zs:
            s = section(m, z)
            if s is None or s.is_empty:
                continue
            geoms = list(s.geoms) if hasattr(s, 'geoms') else [s]
            desc = ', '.join(f'[{g.bounds[0]:.1f},{g.bounds[1]:.1f} .. {g.bounds[2]:.1f},{g.bounds[3]:.1f}] A={g.area:.0f} holes={len(g.interiors)}' for g in geoms[:6])
            print(f'  z={z:5.2f}: {len(geoms)} parts: {desc}')
            out[name][f'{z:.2f}'] = [list(g.exterior.coords) for g in geoms]
    json.dump(out, open('eva_geom.json', 'w'))
