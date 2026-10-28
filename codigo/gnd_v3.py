"""GND plane on both layers over the Freerouting signal result, stitching, island repair, final DRC."""
import pickle, sys
import numpy as np
from scipy import ndimage
from shapely.geometry import LineString, Point
import route_v3 as RV
import router2 as R2
import drc_v3


def main(tag='v3j'):
    C, nets, b, antenna = RV.setup()
    b.extra = {}          # signal-only routing ignored the AMS heat spreader; GND/3V3 copper comes from the pour
    R = pickle.load(open(f'route_{tag}.pkl', 'rb'))
    b.tracks = {n: [(L, LineString(p), w) for L, p, w in v if len(p) >= 2] for n, v in R['tracks'].items()}
    b.vias = {n: list(v) for n, v in R['vias'].items()}
    for n in b.nets:
        b.refresh(n)
    b.prepare()
    ko = {'T': b.g.raster([antenna]), 'B': b.g.raster([antenna])}
    b.failed = []
    # direct bottom link ESP GND <-> header GND (aligned in x), then let the pour do the rest
    b.refresh('GND'); b.prepare()
    pours = R2.pour(b, 'GND', keep_out=ko)
    groups, lab, find = R2.gnd_islands(b, pours)
    print('GND (arvore + plano):', [len(g) for g in groups])
    st = R2.stitch(b, pours, 'GND', spacing=3.5)
    pours = R2.pour(b, 'GND', keep_out=ko)
    groups, lab, find = R2.gnd_islands(b, pours)
    print(f'costura: {len(st)} vias -> grupos {[len(g) for g in groups]}')
    tried = set()
    for it in range(20):
        cand = [g_ for g_ in groups[1:] if tuple(g_) not in tried]
        if not cand:
            break
        isl = cand[-1]
        tried.add(tuple(isl))
        ok = R2.repair_island(b, pours, lab, find, isl, w=0.8) or R2.repair_island(b, pours, lab, find, isl, w=0.7)
        pours = R2.pour(b, 'GND', keep_out=ko)
        groups, lab, find = R2.gnd_islands(b, pours)
        print(f'  reparo {isl} -> {"ok" if ok else "FALHOU"}; grupos {[len(g) for g in groups]}')
    # drop floating pour fragments (no GND pad/track/via inside)
    removed = 0
    for L in R2.LAYERS:
        l, n = ndimage.label(pours[L], structure=np.ones((3, 3)))
        keep = np.unique(l[b._cu['GND'][L] & (l > 0)])
        keep = keep[keep > 0]
        removed += n - len(keep)
        pours[L] = np.isin(l, keep) & pours[L]
    print('fragmentos soltos removidos:', removed)
    # stitching vias that ended up in no pour on a layer are useless: drop them
    Rf = dict(tracks={n: [(L, list(ls.coords), w) for L, ls, w in v] for n, v in b.tracks.items()},
              vias=b.vias, failed=[], extra={})
    pickle.dump(Rf, open(f'route_{tag}_gnd.pkl', 'wb'))
    pickle.dump(dict(pours=pours, grid=(b.g.x0, b.g.y0, b.g.W, b.g.H)), open(f'pours_{tag}.pkl', 'wb'))
    print('GND final:', [len(g) for g in groups], 'ilhas:', groups[1:] if len(groups) > 1 else 'nenhuma')
    R2_, C_, nets_ = drc_v3.load(f'{tag}_gnd')
    nets_.pop('GND', None)
    errs, disc, cu = drc_v3.drc(R2_, C_, nets_, verbose=True)
    vs = {n: len(v) for n, v in b.vias.items() if v}
    print('vias:', vs, 'total', sum(vs.values()))
    g = b.g
    drc_v3.render(R2_, C_, nets_, f'/projects/sandbox/ver_{tag}_gnd.png', f'{tag} + plano GND', pours=pours, grid=g)
    return groups, errs, disc


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'v3j')
