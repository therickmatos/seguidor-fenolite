"""Grid maze router for a single copper layer (bottom), soft crossings -> jumpers.
Geometry in mm, raster RES mm/px. Adapted from the reference session router."""
import math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.graph import MCP_Geometric
from shapely.geometry import LineString, Point

RES = 0.12
CLR = 0.6
EDGE = 0.6
JUMP_COST = 60.0

class Grid:
    def __init__(self, xmin, ymin, xmax, ymax):
        self.x0, self.y0 = xmin, ymin
        self.W = int(math.ceil((xmax - xmin) / RES)) + 1
        self.H = int(math.ceil((ymax - ymin) / RES)) + 1
    def to_px(self, x, y):
        return (x - self.x0) / RES, (y - self.y0) / RES
    def to_rc(self, x, y):
        c, r = self.to_px(x, y)
        return int(round(r)), int(round(c))
    def to_xy(self, r, c):
        return self.x0 + c * RES, self.y0 + r * RES
    def raster(self, geoms):
        img = Image.new('1', (self.W, self.H), 0)
        d = ImageDraw.Draw(img)
        def draw_poly(p):
            d.polygon([self.to_px(x, y) for x, y in p.exterior.coords], fill=1)
            for hole in p.interiors:
                d.polygon([self.to_px(x, y) for x, y in hole.coords], fill=0)
        for g in geoms:
            if g is None or g.is_empty:
                continue
            if g.geom_type == 'Polygon':
                draw_poly(g)
            elif hasattr(g, 'geoms'):
                for gg in g.geoms:
                    if gg.geom_type == 'Polygon':
                        draw_poly(gg)
        return np.array(img, dtype=bool)

class Board:
    def __init__(self, outline, holes, comps, nets, widths, default_w, keepout_copper=()):
        self.outline, self.holes, self.comps = outline, holes, comps
        self.nets, self.widths, self.default_w = nets, widths, default_w
        b = outline.bounds
        self.g = Grid(b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1)
        self.tracks, self.jumpers, self.jpads, self.pad_geom = {}, [], {}, {}
        for net, pads in nets.items():
            for p in pads:
                self.pad_geom[(p.ref, p.pin)] = p.geom()
        g = self.g
        inside = g.raster([outline])
        self.outside = ~inside
        ko = [Point(x, y).buffer(rk, 24) for x, y, d, rk in holes] + list(keepout_copper)
        self.static_ko = g.raster(ko)
        self.d_out = ndimage.distance_transform_edt(~self.outside) * RES
        self.d_ko = ndimage.distance_transform_edt(~self.static_ko) * RES
        self.copper = {n: g.raster(self.net_geoms(n)) for n in nets}

    def net_geoms(self, net):
        gs = [self.pad_geom[(p.ref, p.pin)] for p in self.nets.get(net, [])]
        gs += [ls.buffer(w / 2, 8) for ls, w in self.tracks.get(net, [])]
        gs += list(self.jpads.get(net, []))
        return gs

    def refresh(self, net):
        self.copper[net] = self.g.raster(self.net_geoms(net))

    def other_mask(self, net):
        m = np.zeros((self.g.H, self.g.W), bool)
        for n, c in self.copper.items():
            if n != net:
                m |= c
        return m

    def pad_mask_others(self, net):
        gs = []
        for n, pads in self.nets.items():
            if n == net:
                continue
            gs += [self.pad_geom[(p.ref, p.pin)] for p in pads]
            gs += list(self.jpads.get(n, []))
        return self.g.raster(gs)

    def free_cost(self, net, w, soft):
        other = self.other_mask(net)
        d_other = ndimage.distance_transform_edt(~other) * RES
        need = CLR + w / 2
        hard = (self.d_out < EDGE + w / 2) | (self.d_ko < w / 2 + 0.05)
        blocked = d_other < need
        cost = np.ones((self.g.H, self.g.W))
        near = (d_other < need + 0.4) & ~blocked
        cost[near] += 1.2
        if soft:
            padm = self.pad_mask_others(net)
            d_pad = ndimage.distance_transform_edt(~padm) * RES
            cost[blocked] = JUMP_COST
            cost[d_pad < need] = np.inf
        else:
            cost[blocked] = np.inf
        cost[hard] = np.inf
        return cost, blocked

    def route_net(self, net, soft_ok=True, verbose=False):
        pads = self.nets[net]
        if len(pads) < 2:
            return True
        widths = self.widths.get(net, self.default_w)
        connected = [pads[0]]
        remaining = list(pads[1:])
        ok = True
        while remaining:
            routed = False
            for w in widths:
                for soft in ([False, True] if soft_ok else [False]):
                    res = self._route_once(net, connected, remaining, w, soft)
                    if res:
                        tgt, path, jumps = res
                        self._commit(net, path, w, jumps)
                        remaining.remove(tgt)
                        connected.append(tgt)
                        routed = True
                        break
                if routed:
                    break
            if not routed:
                if verbose:
                    print(f'  !! {net}: nao alcancou {remaining[0]}')
                remaining.pop(0)
                ok = False
        return ok

    def _route_once(self, net, connected, targets, w, soft):
        cost, blocked = self.free_cost(net, w, soft)
        g = self.g
        src = g.raster([self.pad_geom[(p.ref, p.pin)] for p in connected] +
                       [ls.buffer(ww / 2, 8) for ls, ww in self.tracks.get(net, [])] + list(self.jpads.get(net, [])))
        tmask = g.raster([self.pad_geom[(t.ref, t.pin)] for t in targets])
        cost2 = cost.copy()
        cost2[tmask] = np.minimum(np.where(np.isfinite(cost2[tmask]), cost2[tmask], 1.0), 1.0)
        cost2[src] = 1.0
        rs, cs = np.nonzero(src)
        if len(rs) == 0:
            return None
        idx = np.arange(len(rs))[:: max(1, len(rs) // 3000)]
        pts = list(zip(rs[idx].tolist(), cs[idx].tolist()))
        tg = {}
        for t in targets:
            tg[g.to_rc(t.x, t.y)] = t
        mcp = MCP_Geometric(cost2, fully_connected=True)
        costs, _ = mcp.find_costs(pts, list(tg.keys()))
        best, bt = None, np.inf
        for rc in tg:
            if costs[rc[0], rc[1]] < bt:
                bt, best = costs[rc[0], rc[1]], rc
        if best is None or not np.isfinite(bt):
            return None
        path = mcp.traceback(best)
        jumps = self._runs(path, blocked) if soft else []
        return tg[best], path, jumps

    def _runs(self, path, blocked):
        runs, cur = [], None
        for i, (r, c) in enumerate(path):
            if blocked[r, c]:
                cur = [i, i] if cur is None else [cur[0], i]
            elif cur is not None:
                runs.append(tuple(cur)); cur = None
        if cur is not None:
            runs.append(tuple(cur))
        return runs

    def _commit(self, net, path, w, jumps):
        g = self.g
        pts = [g.to_xy(r, c) for r, c in path]
        if not jumps:
            segs = [pts]
        else:
            segs, start = [], 0
            for a, b in jumps:
                pa = self._jpad_spot(net, pts, max(a - 1, 0), -1)
                pb = self._jpad_spot(net, pts, min(b + 1, len(pts) - 1), +1)
                segs.append(pts[start:pa + 1])
                self.jumpers.append((net, pts[pa], pts[pb]))
                self.jpads.setdefault(net, []).extend([Point(*pts[pa]).buffer(0.9, 16), Point(*pts[pb]).buffer(0.9, 16)])
                start = pb
            segs.append(pts[start:])
        for s in segs:
            if len(s) >= 2:
                ls = LineString(s).simplify(0.1, preserve_topology=False)
                self.tracks.setdefault(net, []).append((ls, w))
        self.refresh(net)

    def _jpad_spot(self, net, pts, i, step):
        other = self.other_mask(net)
        d_other = ndimage.distance_transform_edt(~other) * RES
        j = i
        while 0 <= j < len(pts):
            r, c = self.g.to_rc(*pts[j])
            if d_other[r, c] >= 0.9 + CLR and self.d_out[r, c] >= 0.9 + EDGE and self.d_ko[r, c] >= 0.9:
                return j
            j += step
        return i
