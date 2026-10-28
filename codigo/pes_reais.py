"""Real impeller-housing feet footprint in the ROBOT frame (from voxel data), both 45-deg rotations unioned."""
import json, math
import numpy as np
from shapely.geometry import box, Point
from shapely.ops import unary_union
from shapely import affinity

d = json.load(open('vox_geom.json'))
polys = []
for key in ['imp_0_1.0', 'imp_1.0_6.0', 'imp_6.0_11.0']:
    m = np.array(d[key]['mask'], bool)
    o = d[key]['origin']; p = d[key]['pitch']
    xs, ys = np.nonzero(m)
    cells = [box(o[0] + i * p, o[1] + j * p, o[0] + (i + 1) * p, o[1] + (j + 1) * p) for i, j in zip(xs, ys)]
    polys.append(unary_union(cells))
feet = unary_union(polys).buffer(0.05).buffer(-0.05)
both = unary_union([affinity.rotate(feet, 45, origin=(0, 0)), affinity.rotate(feet, -45, origin=(0, 0))])
both = both.buffer(0.5)            # 0.5 mm margin
print('area', round(both.area), 'parts', len(getattr(both, 'geoms', [both])))
out = []
for g in getattr(both, 'geoms', [both]):
    c = g.centroid
    rr = [math.hypot(x, y) for x, y in g.exterior.coords]
    aa = [math.degrees(math.atan2(y, x)) % 360 for x, y in g.exterior.coords]
    print(f'  pe c=({c.x:.1f},{c.y:.1f}) r {min(rr):.1f}-{max(rr):.1f} ang {min(aa):.0f}..{max(aa):.0f}')
    out.append([(round(x, 3), round(y, 3)) for x, y in g.simplify(0.1).exterior.coords])
json.dump(out, open('pes_reais.json', 'w'))
# check the EVA-RT IFX position vs real feet
ifx = box(22.1 - 2.5, -12.45 - 3.5, 22.1 + 2.5, -12.45 + 3.5)
print('IFX EVA-RT (22.1,-12.45) colide com pe real?', both.intersects(ifx), round(both.intersection(ifx).area, 2))
