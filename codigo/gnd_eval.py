"""Evaluate GND islands (tree + pour) for a routed tag without modifying it."""
import pickle, numpy as np
from shapely.geometry import LineString
import route_v3 as RV, router2 as R2
def islands(tag):
    C, nets, b, antenna = RV.setup()
    b.extra = {}
    R = pickle.load(open(f'route_{tag}.pkl', 'rb'))
    b.tracks = {n: [(L, LineString(p), w) for L, p, w in v if len(p) >= 2] for n, v in R['tracks'].items()}
    b.vias = {n: list(v) for n, v in R['vias'].items()}
    for n in b.nets: b.refresh(n)
    b.prepare()
    ko = {'T': b.g.raster([antenna]), 'B': b.g.raster([antenna])}
    pours = R2.pour(b, 'GND', keep_out=ko)
    groups, lab, find = R2.gnd_islands(b, pours)
    return groups
