"""Two-layer grid router for homemade double-sided fenolite (no plated holes).
Planes: 0 = TOP copper, 1 = VIA plane (layer change only where a via is allowed), 2 = BOTTOM copper.
A via is a wire through a drilled hole soldered on both faces (pad on both layers)."""
import math, time
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.graph import MCP_Geometric
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

RES = 0.12
CLR = 0.6
EDGE = 0.6
MARGIN = 0.16      # raster safety margin added to every distance rule
VIA_D = 1.8          # via pad diameter (drill 0.8)
VIA_COST = 35.0      # in mm of track; a via costs as much as 35 mm of detour
NEAR_PEN = 0.8
LAYERS = ('T', 'B')


class Grid:
    def __init__(self, bounds, pad=1.0):
        self.x0, self.y0 = bounds[0] - pad, bounds[1] - pad
        self.W = int(math.ceil((bounds[2] - bounds[0] + 2 * pad) / RES)) + 1
        self.H = int(math.ceil((bounds[3] - bounds[1] + 2 * pad) / RES)) + 1

    def px(self, x, y):
        return (x - self.x0) / RES, (y - self.y0) / RES

    def rc(self, x, y):
        c, r = self.px(x, y)
        return int(round(r)), int(round(c))

    def xy(self, r, c):
        return self.x0 + c * RES, self.y0 + r * RES

    def raster(self, geoms):
        img = Image.new('1', (self.W, self.H), 0)
        d = ImageDraw.Draw(img)
        def dp(p):
            d.polygon([self.px(x, y) for x, y in p.exterior.coords], fill=1)
            for h in p.interiors:
                d.polygon([self.px(x, y) for x, y in h.coords], fill=0)
        for g in geoms:
            if g is None or g.is_empty:
                continue
            for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
                if gg.geom_type == 'Polygon':
                    dp(gg)
        return np.array(img, dtype=bool)


class Board2:
    def __init__(self, outline, comps, nets, holes, widths, default_w,
                 ko_both=(), ko_top=(), ko_bot=(), via_forbid=(), top_trace_forbid=()):
        self.outline, self.comps, self.nets = outline, comps, nets
        self.widths, self.default_w = widths, default_w
        self.g = Grid(outline.bounds)
        g = self.g
        self.tracks = {}      # net -> list of (layer, LineString, width)
        self.vias = {}        # net -> list of (x, y)
        self.extra = {}       # net -> list of (layer, polygon) copper areas (e.g. heat spreaders)
        inside = g.raster([outline])
        self.d_out = ndimage.distance_transform_edt(inside) * RES
        holes_ko = [Point(x, y).buffer(rk, 24) for x, y, d, rk in holes]
        self.ko = {}
        for L, extra in (('T', list(ko_top) + list(top_trace_forbid)), ('B', list(ko_bot))):
            m = g.raster(holes_ko + list(ko_both) + extra)
            self.ko[L] = ndimage.distance_transform_edt(~m) * RES
        vf = g.raster(list(via_forbid) + holes_ko)
        self.via_ok = (~vf) & (ndimage.distance_transform_edt(~vf) * RES >= VIA_D / 2 + MARGIN) & (self.d_out >= VIA_D / 2 + EDGE + MARGIN)
        # pad geometry per layer; B-only THT pads still block the TOP layer (lead + solder ring)
        self.pad_geo = {}     # (ref,pin) -> geometry
        self.pad_layers = {}  # (ref,pin) -> tuple of layers where it can be connected
        for net, pads in nets.items():
            for p in pads:
                self.pad_geo[(p.ref, p.pin)] = p.geom()
                self.pad_layers[(p.ref, p.pin)] = getattr(p, 'layers', ('B',))
        self.blockers = {'T': [], 'B': []}    # (net, geom) present on a layer but NOT connectable there
        for net, pads in nets.items():
            for p in pads:
                lay = self.pad_layers[(p.ref, p.pin)]
                geo = self.pad_geo[(p.ref, p.pin)]
                if p.side == 'tht':
                    for L in LAYERS:
                        if L not in lay:
                            ring = Point(p.x, p.y).buffer(max(p.drill / 2 + 0.45, 0.8), 16)
                            self.blockers[L].append((net, ring))
        self._cu = {}
        for n in nets:
            self.refresh(n)

    # ---------- copper bookkeeping ----------
    def net_geoms(self, net, L):
        gs = []
        for p in self.nets.get(net, []):
            if L in self.pad_layers[(p.ref, p.pin)]:
                gs.append(self.pad_geo[(p.ref, p.pin)])
        gs += [ls.buffer(w / 2, 8) for lay, ls, w in self.tracks.get(net, []) if lay == L]
        gs += [Point(x, y).buffer(VIA_D / 2, 16) for x, y in self.vias.get(net, [])]
        gs += [poly for lay, poly in self.extra.get(net, []) if lay == L]
        return gs

    def refresh(self, net):
        self._cu[net] = {L: self.g.raster(self.net_geoms(net, L)) for L in LAYERS}

    def blocker_mask(self, L, exclude_net=None):
        return self.g.raster([geo for n, geo in self.blockers[L]])

    def other_mask(self, net, L):
        m = np.zeros((self.g.H, self.g.W), bool)
        for n, d in self._cu.items():
            if n != net:
                m |= d[L]
        m |= self._blk[L]
        return m

    def prepare(self):
        self._blk = {L: self.blocker_mask(L) for L in LAYERS}

    # ---------- routing ----------
    def plane_cost(self, net, w, L, d_other):
        need = CLR + w / 2 + MARGIN
        c = np.ones((self.g.H, self.g.W))
        c[(d_other < need + 0.5)] += NEAR_PEN
        hard = (d_other < need) | (self.d_out < EDGE + w / 2 + MARGIN) | (self.ko[L] < w / 2 + MARGIN)
        c[hard] = np.inf
        return c

    def route_net(self, net, verbose=False, max_w=None):
        pads = [p for p in self.nets[net]]
        if len(pads) < 2:
            return True
        widths = self.widths.get(net, self.default_w)
        connected = [pads[0]]
        remaining = pads[1:]
        ok = True
        while remaining:
            done = False
            for w in widths:
                res = self._route_once(net, connected, remaining, w)
                if res:
                    tgt, path = res
                    self._commit(net, path, w)
                    remaining.remove(tgt)
                    connected.append(tgt)
                    done = True
                    break
            if not done:
                if verbose:
                    print(f'   !! {net}: sem caminho ate {remaining[0].ref}.{remaining[0].pin}')
                self.failed.append((net, remaining[0].ref + '.' + remaining[0].pin))
                remaining.pop(0)
                ok = False
        return ok

    def _route_once(self, net, connected, targets, w):
        g = self.g
        H, W = g.H, g.W
        cost = np.empty((3, H, W))
        d_o = {}
        for i, L in ((0, 'T'), (2, 'B')):
            om = self.other_mask(net, L)
            d_o[L] = ndimage.distance_transform_edt(~om) * RES
            cost[i] = self.plane_cost(net, w, L, d_o[L])
        vneed = VIA_D / 2 + CLR + MARGIN
        vmask = self.via_ok & (d_o['T'] >= vneed) & (d_o['B'] >= vneed)
        cost[1] = np.where(vmask, VIA_COST / RES, np.inf)
        # sources: ONLY copper already connected to the tree (connected pads + this net's tracks/vias/areas)
        srcs = []
        for i, L in ((0, 'T'), (2, 'B')):
            gs = [self.pad_geo[(p.ref, p.pin)] for p in connected if L in self.pad_layers[(p.ref, p.pin)]]
            gs += [ls.buffer(ww / 2, 8) for lay, ls, ww in self.tracks.get(net, []) if lay == L]
            gs += [Point(x, y).buffer(VIA_D / 2, 16) for x, y in self.vias.get(net, [])]
            gs += [poly for lay, poly in self.extra.get(net, []) if lay == L]
            m = g.raster(gs)
            rs, cs = np.nonzero(m)
            if len(rs):
                step = max(1, len(rs) // 2500)
                srcs += [(i, r, c) for r, c in zip(rs[::step], cs[::step])]
            cost[i][m] = np.minimum(cost[i][m], 1.0)
        # own unconnected pads must not act as shortcuts: they are only targets
        own = self._cu[net]
        # targets on their connectable layers
        tg = {}
        for t in targets:
            r, c = g.rc(t.x, t.y)
            pm = g.raster([self.pad_geo[(t.ref, t.pin)]])
            for L in self.pad_layers[(t.ref, t.pin)]:
                i = 0 if L == 'T' else 2
                cost[i][pm] = np.minimum(np.where(np.isfinite(cost[i][pm]), cost[i][pm], 1.0), 1.0)
                tg[(i, r, c)] = t
        if not srcs:
            return None
        offs = [(0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (0, 1, 1), (0, 1, -1), (0, -1, 1), (0, -1, -1), (1, 0, 0), (-1, 0, 0)]
        mcp = MCP_Geometric(cost, offsets=np.array(offs))
        costs, _ = mcp.find_costs(srcs, list(tg.keys()), find_all_ends=False)
        best, bc = None, np.inf
        for k in tg:
            if costs[k] < bc:
                bc, best = costs[k], k
        if best is None or not np.isfinite(bc):
            return None
        path = mcp.traceback(best)
        return tg[best], path

    def _commit(self, net, path, w):
        g = self.g
        seg, cur = [], None
        segs = []
        vias = []
        for (i, r, c) in path:
            if i == 1:
                vias.append(g.xy(r, c))
                if seg:
                    segs.append((cur, seg)); seg = []
                cur = None
                continue
            L = 'T' if i == 0 else 'B'
            if cur is None:
                cur = L
            if L != cur:
                if seg:
                    segs.append((cur, seg))
                seg, cur = [], L
            seg.append(g.xy(r, c))
        if seg:
            segs.append((cur, seg))
        # one via per layer change (the via plane may contain consecutive cells)
        vv = []
        for p in vias:
            if not vv or math.hypot(p[0] - vv[-1][0], p[1] - vv[-1][1]) > 0.5:
                vv.append(p)
        for L, pts in segs:
            if len(pts) >= 2:
                ls = LineString(pts).simplify(0.08, preserve_topology=False)
                self.tracks.setdefault(net, []).append((L, ls, w))
            elif len(pts) == 1:
                self.tracks.setdefault(net, []).append((L, LineString([pts[0], (pts[0][0] + 0.01, pts[0][1])]), w))
        for p in vv:
            self.vias.setdefault(net, []).append(p)
        self.refresh(net)


def pour(board, net='GND', min_w=0.7, keep_out=None):
    """GND pour on both layers; returns per-layer masks."""
    g = board.g
    res = {}
    rad = int(round(min_w / 2 / RES))
    yy, xx = np.mgrid[-rad:rad + 1, -rad:rad + 1]
    st = (xx ** 2 + yy ** 2) <= rad ** 2
    for L in LAYERS:
        om = board.other_mask(net, L)
        d = ndimage.distance_transform_edt(~om) * RES
        m = (d >= CLR + MARGIN) & (board.d_out >= EDGE + MARGIN) & (board.ko[L] >= MARGIN)
        if keep_out is not None and L in keep_out:
            m &= ~keep_out[L]
        m = ndimage.binary_opening(m, structure=st)
        res[L] = m | board._cu[net][L]
    return res


def gnd_islands(board, pours, net='GND'):
    """Connected components of GND copper across both layers (joined by GND vias / two-layer pads)."""
    g = board.g
    lab = {}
    n_off = 0
    comp_of = {}
    for L in LAYERS:
        l, n = ndimage.label(pours[L], structure=np.ones((3, 3)))
        lab[L] = (l, n_off)
        n_off += n
    parent = list(range(n_off + 1))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    def gid(L, x, y):
        l, off = lab[L]
        r, c = g.rc(x, y)
        v = l[r, c]
        return off + v if v else None
    links = [(x, y) for x, y in board.vias.get(net, [])]
    for p in board.nets[net]:
        if len(board.pad_layers[(p.ref, p.pin)]) == 2:
            links.append((p.x, p.y))
    for x, y in links:
        a, b = gid('T', x, y), gid('B', x, y)
        if a and b:
            union(a, b)
    groups = {}
    for p in board.nets[net]:
        ids = [gid(L, p.x, p.y) for L in board.pad_layers[(p.ref, p.pin)]]
        ids = [i for i in ids if i]
        key = find(ids[0]) if ids else ('solto', p.ref, p.pin)
        groups.setdefault(key, []).append(f'{p.ref}.{p.pin}')
    return sorted(groups.values(), key=len, reverse=True), lab, find


def stitch(board, pours, net='GND', spacing=6.0):
    """Add GND vias where both layers have pour, on a coarse lattice, to tie the two planes together."""
    g = board.g
    vneed = VIA_D / 2 + CLR + MARGIN
    ok = board.via_ok.copy()
    for L in LAYERS:
        om = board.other_mask(net, L)
        d = ndimage.distance_transform_edt(~om) * RES
        inner = ndimage.distance_transform_edt(pours[L]) * RES
        ok &= (d >= vneed) & (inner >= VIA_D / 2 + 0.05)
    step = int(round(spacing / RES))
    added = []
    for r in range(step // 2, g.H, step):
        for c in range(step // 2, g.W, step):
            if ok[r, c]:
                x, y = g.xy(r, c)
                added.append((x, y))
    board.vias.setdefault(net, []).extend(added)
    board.refresh(net)
    return added


def repair_island(board, pours, lab, find, island_pads, w=0.8, net='GND'):
    """Route GND copper from one island (its pads) to the main GND region (both layers, vias allowed)."""
    g = board.g
    H, W = g.H, g.W
    # main region = largest union-find group by area
    comp_ids = {}
    for L in LAYERS:
        l, off = lab[L]
        ids, cnt = np.unique(l[l > 0], return_counts=True)
        for i, c in zip(ids, cnt):
            k = find(off + int(i))
            comp_ids[k] = comp_ids.get(k, 0) + int(c)
    main = max(comp_ids, key=comp_ids.get)
    cost = np.empty((3, H, W)); d_o = {}
    for i, L in ((0, 'T'), (2, 'B')):
        om = board.other_mask(net, L)
        d_o[L] = ndimage.distance_transform_edt(~om) * RES
        cost[i] = board.plane_cost(net, w, L, d_o[L])
    vneed = VIA_D / 2 + CLR + MARGIN
    cost[1] = np.where(board.via_ok & (d_o['T'] >= vneed) & (d_o['B'] >= vneed), VIA_COST / RES, np.inf)
    srcs = []
    for i, L in ((0, 'T'), (2, 'B')):
        l, off = lab[L]
        ids = [k for k in np.unique(l[l > 0]) if find(off + int(k)) == main]
        m = np.isin(l, ids) & pours[L]
        rs, cs = np.nonzero(m)
        if len(rs):
            st = max(1, len(rs) // 4000)
            srcs += [(i, r, c) for r, c in zip(rs[::st], cs[::st])]
        cost[i][m] = 1.0
    tg = {}
    for key in island_pads:
        ref, pin = key.split('.')
        p = [q for q in board.nets[net] if q.ref == ref and q.pin == pin][0]
        r, c = g.rc(p.x, p.y)
        pm = g.raster([board.pad_geo[(p.ref, p.pin)]])
        for L in board.pad_layers[(p.ref, p.pin)]:
            i = 0 if L == 'T' else 2
            cost[i][pm] = 1.0
            tg[(i, r, c)] = p
    if not srcs or not tg:
        return False
    offs = [(0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (0, 1, 1), (0, 1, -1), (0, -1, 1), (0, -1, -1), (1, 0, 0), (-1, 0, 0)]
    mcp = MCP_Geometric(cost, offsets=np.array(offs))
    costs, _ = mcp.find_costs(srcs, list(tg.keys()), find_all_ends=False)
    best = min(tg, key=lambda k: costs[k])
    if not np.isfinite(costs[best]):
        return False
    board._commit(net, mcp.traceback(best), w)
    return True
