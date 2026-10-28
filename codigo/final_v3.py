"""Final packaging of a routed v3 board (tag):
GND pour on both faces -> minimal stitching vias (Steiner heuristic over the pour components) ->
short hand-drawn GND tracks -> top wire jumpers for what is left -> vector DRC + connectivity ->
render + tables (placement / pads / netlist / vias / jumpers / tracks) for EasyEDA Pro."""
import pickle, sys, json, math, os
from collections import deque
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
import design as D
import route_v3 as RV
import router2 as R2
import drc_v3

OUT = '/projects/sandbox/repo'
RES = R2.RES
VNEED = R2.VIA_D / 2 + R2.CLR + R2.MARGIN       # via centre -> foreign copper (raster, with margin)
JPAD_R = 1.0                                     # top solder spot of a jumper end (Ø2,0 inside the GND plane)
HOLE_PEN = 1.0                                   # mm added to a jumper score per drilled end
WIRE_KO = ('pes da carcaca', 'janela helice', 'caixa reducao', 'presilha vareta')   # nothing may lie here on top

# short GND tracks drawn by hand: (layer, width, points)
MANUAL_GND = [
    ('B', 0.7, [(27.6, -4.45), (29.1, -4.45), (29.1, -2.4), (29.54, -1.16)]),   # R6.2 -> C6.1 / U4.3 (bottom)
]
# signal vias nudged by hand: net -> [(old xy, new xy)]; track vertices on the old spot follow the via.
# BI_A via 0.74 mm lower (still 1.4 mm clear of the real suction plate): opens a GND lane on top between
# the via and the ESP, so the nose GND closes with one stitching via instead of a wire jumper.
MOVE_VIAS = {'BI_A': [((-11.15, 21.29), (-11.15, 20.55))]}


def move_vias(R):
    for net, moves in MOVE_VIAS.items():
        for old, new in moves:
            hit = [i for i, v in enumerate(R['vias'].get(net, [])) if math.dist(v, old) < 0.05]
            assert hit, f'via {net} {old} nao encontrada'
            R['vias'][net][hit[0]] = new
            for k, (L, pts, w) in enumerate(R['tracks'][net]):
                R['tracks'][net][k] = (L, [new if math.dist(p, old) < 0.05 else p for p in pts], w)


# ---------------------------------------------------------------- board
def build_board(tag):
    C, nets, b, antenna = RV.setup()
    b.extra = {}
    R = pickle.load(open(f'route_{tag}.pkl', 'rb'))
    move_vias(R)
    b.tracks = {n: [(L, LineString(p), w) for L, p, w in v if len(p) >= 2] for n, v in R['tracks'].items()}
    b.vias = {n: list(v) for n, v in R['vias'].items()}
    for L, w, pts in MANUAL_GND:
        b.tracks.setdefault('GND', []).append((L, LineString(pts), w))
    for n in b.nets:
        b.refresh(n)
    b.prepare()
    b._antenna = antenna
    return C, nets, b, antenna


def pours_of(b):
    ko = {L: b.g.raster([b._antenna]) for L in R2.LAYERS}
    return R2.pour(b, 'GND', keep_out=ko)


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        p = self.p
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def components(b, pours, jumpers):
    """Pour components on both faces joined by GND vias, 2-face GND pads and jumper wires."""
    lab, off = {}, 0
    for L in R2.LAYERS:
        l, n = ndimage.label(pours[L], structure=np.ones((3, 3)))
        lab[L] = (l, off)
        off += n
    uf = UF(off + 1)

    def ids_at(x, y, layers):
        out = []
        for L in layers:
            l, o = lab[L]
            r, c = b.g.rc(x, y)
            if l[r, c]:
                out.append(o + int(l[r, c]))
        return out

    def join(ii):
        for i in ii[1:]:
            uf.union(ii[0], i)
    for x, y in b.vias.get('GND', []):
        join(ids_at(x, y, R2.LAYERS))
    for p in b.nets['GND']:
        join(ids_at(p.x, p.y, b.pad_layers[(p.ref, p.pin)]))
    for jm in jumpers:
        join(ids_at(*jm['a'], jm['la']) + ids_at(*jm['b'], jm['lb']))
    groups = {}
    for p in b.nets['GND']:
        ii = ids_at(p.x, p.y, b.pad_layers[(p.ref, p.pin)])
        key = uf.find(ii[0]) if ii else ('solto', p.ref, p.pin)
        groups.setdefault(key, []).append(f'{p.ref}.{p.pin}')
    root = np.array([uf.find(i) for i in range(off + 1)])
    rmap = {L: np.where(lab[L][0] > 0, root[lab[L][0] + lab[L][1]], -1) for L in R2.LAYERS}
    main = next(k for k, v in groups.items() if 'J1.2' in v)          # battery GND defines the main plane
    return rmap, groups, main


def clearance_map(b):
    dmin = None
    for L in R2.LAYERS:
        d = ndimage.distance_transform_edt(~b.other_mask('GND', L)) * RES
        dmin = d if dmin is None else np.minimum(dmin, d)
    return dmin


# ---------------------------------------------------------------- stitching vias
def smart_stitch(b, jumpers, max_rounds=12):
    """Add only the GND vias that join pad groups (shortest chains of pour components, BFS)."""
    added = []
    for _ in range(max_rounds):
        pours = pours_of(b)
        rmap, groups, main = components(b, pours, jumpers)
        terms = {k for k in groups if not isinstance(k, tuple)}
        if len(terms) <= 1:
            break
        dmin = clearance_map(b)
        ok = b.via_ok & (dmin >= VNEED) & pours['T'] & pours['B']
        # slack = how far the via could still move before breaking copper or board-edge clearance
        slack = np.minimum(dmin - VNEED, b.d_out - (R2.VIA_D / 2 + R2.EDGE + R2.MARGIN))
        rs, cs = np.nonzero(ok)
        best = {}
        for r, c in zip(rs, cs):
            u, v = int(rmap['T'][r, c]), int(rmap['B'][r, c])
            if u == v or u < 0 or v < 0:
                continue
            k = (min(u, v), max(u, v))
            if k not in best or slack[r, c] > best[k][0]:
                best[k] = (slack[r, c], r, c)
        adj = {}
        for (u, v), val in best.items():
            adj.setdefault(u, []).append((v, val))
            adj.setdefault(v, []).append((u, val))

        def bfs(src, goals):
            prev = {src: None}
            q = deque([src])
            while q:
                u = q.popleft()
                if u in goals and u != src:
                    return u, prev
                for v, val in adj.get(u, []):
                    if v not in prev:
                        prev[v] = (u, val)
                        q.append(v)
            return None, prev
        hit, prev = bfs(main, terms - {main})
        if hit is None:                                   # islands that can at least join each other
            for t in sorted(terms - {main}, key=str):
                hit, prev = bfs(t, terms - {t})
                if hit is not None:
                    break
        if hit is None:
            break
        v = hit
        while prev[v] is not None:
            u, val = prev[v]
            x, y = b.g.xy(val[1], val[2])
            b.vias.setdefault('GND', []).append((round(x, 2), round(y, 2)))
            added.append((round(x, 2), round(y, 2)))
            v = u
        b.refresh('GND')
    return added


# ---------------------------------------------------------------- jumpers
def wire_obstacles(C):
    obs = [p for n, p, mh in D.top_keepouts_h() if n in WIRE_KO]
    bodies = [c.body.buffer(0.2) for c in C.values() if c.body is not None and c.side == 'top' and c.kind != 'wire']
    return obs, bodies


def endpoint_cells(b, pours, rmap, root, dmin, ko_mask, body_mask):
    """(kind, layers, rows, cols) of the cells where a jumper end of this GND group fits."""
    out = []
    hole = b.via_ok & (dmin >= VNEED) & ((rmap['T'] == root) | (rmap['B'] == root))
    rs, cs = np.nonzero(hole)
    out.append(('furo', ('T', 'B'), rs, cs))
    reg = rmap['T'] == root
    inner = ndimage.distance_transform_edt(reg) * RES
    top = reg & (inner >= JPAD_R + 0.1) & ~ko_mask & ~body_mask
    rs, cs = np.nonzero(top)
    out.append(('ponto', ('T',), rs, cs))
    return out


def best_jumper(b, C, pours, rmap, isl, main, dmin, ko_mask, body_mask, obst):
    ea = endpoint_cells(b, pours, rmap, isl, dmin, ko_mask, body_mask)
    eb = endpoint_cells(b, pours, rmap, main, dmin, ko_mask, body_mask)
    cands = []
    for ka, la, ra, ca in ea:
        if not len(ra):
            continue
        sa = max(1, len(ra) // 4000)
        A = np.c_[ra[::sa], ca[::sa]]
        for kb, lb, rb, cb in eb:
            if not len(rb):
                continue
            sb = max(1, len(rb) // 40000)
            Bp = np.c_[rb[::sb], cb[::sb]]
            tree = cKDTree(Bp)
            d, k = tree.query(A, k=min(25, len(Bp)))
            d = np.atleast_2d(d) * RES
            k = np.atleast_2d(k)
            pen = HOLE_PEN * ((ka == 'furo') + (kb == 'furo'))
            for i in range(len(A)):
                for j in range(k.shape[1]):
                    if d[i, j] >= 3.0:
                        cands.append((d[i, j] + pen, d[i, j], ka, la, tuple(A[i]), kb, lb, tuple(Bp[k[i, j]])))
    cands.sort(key=lambda t: t[0])
    for score, L, ka, la, pa, kb, lb, pb in cands[:20000]:
        xa, ya = b.g.xy(*pa)
        xb, yb = b.g.xy(*pb)
        seg = LineString([(xa, ya), (xb, yb)])
        if obst.intersects(seg):
            continue
        return dict(a=(round(xa, 2), round(ya, 2)), la=la, ka=ka, b=(round(xb, 2), round(yb, 2)), lb=lb, kb=kb,
                    comprimento=round(L, 1))
    return None


def add_jumper_ends(b, jm):
    for key, kind in (('a', 'ka'), ('b', 'kb')):
        x, y = jm[key]
        if jm[kind] == 'furo':
            b.vias.setdefault('GND', []).append((x, y))
        else:
            b.extra.setdefault('GND', []).append(('T', Point(x, y).buffer(JPAD_R, 24)))
    b.refresh('GND')


def close_with_jumpers(b, C, jumpers, max_jumpers=6):
    obs, bodies = wire_obstacles(C)
    ko_mask = b.g.raster(obs)
    body_mask = b.g.raster(bodies)
    foreign_tht = [Point(p.x, p.y).buffer(max(p.w, p.h) / 2 + 0.3, 16) for c in C.values() for p in c.pads
                   if p.side == 'tht' and p.net != 'GND']
    obst = prep(unary_union(obs + bodies + foreign_tht))
    for _ in range(max_jumpers):
        pours = pours_of(b)
        rmap, groups, main = components(b, pours, jumpers)
        isl = [k for k in groups if k != main]
        if not isl:
            break
        dmin = clearance_map(b)
        done = False
        for k in sorted(isl, key=lambda k: -len(groups[k])):
            if isinstance(k, tuple):
                print('   pad sem cobre:', groups[k])
                continue
            jm = best_jumper(b, C, pours, rmap, k, main, dmin, ko_mask, body_mask, obst)
            if jm is None:
                print('   sem jumper possivel para', groups[k])
                continue
            jm['ilha'] = groups[k]
            add_jumper_ends(b, jm)
            jumpers.append(jm)
            print(f'   jumper J{len(jumpers)}: {groups[k]}  {jm["a"]}({jm["ka"]}) -> {jm["b"]}({jm["kb"]})  {jm["comprimento"]} mm')
            done = True
            break
        if not done:
            break
    return jumpers


def crossed_nets(b, jm):
    seg = LineString([jm['a'], jm['b']])
    s = set()
    for n, tr in b.tracks.items():
        if n == 'GND':
            continue
        for L, ls, w in tr:
            if L == 'T' and ls.buffer(w / 2).intersects(seg):
                s.add(n)
    for n, vs in b.vias.items():
        if n != 'GND' and any(Point(v).buffer(R2.VIA_D / 2).intersects(seg) for v in vs):
            s.add(n + ' (via)')
    return sorted(s)


# ---------------------------------------------------------------- outputs
def render_final(b, C, pours, jumpers, fn, title, zooms=()):
    g = b.g
    out = D.outline_poly()
    jholes = {jm[k] for jm in jumpers for k, kk in (('a', 'ka'), ('b', 'kb')) if jm[kk] == 'furo'}
    fig, axs = plt.subplots(1, 2, figsize=(24, 9.5), dpi=120)
    for ax, L, col in ((axs[0], 'T', '#c0392b'), (axs[1], 'B', '#1f6fb2')):
        ax.add_patch(MPoly(list(out.exterior.coords), closed=True, fc='#efe3c6', ec='#5a4630', lw=1.4, zorder=0))
        ext = [g.x0 - RES / 2, g.x0 + (g.W - 0.5) * RES, g.y0 - RES / 2, g.y0 + (g.H - 0.5) * RES]
        img = np.zeros(pours[L].shape + (4,))
        img[pours[L]] = [0.72, 0.52, 0.28, 0.55]
        ax.imshow(img, origin='lower', extent=ext, zorder=1, interpolation='nearest')
        for n, tr in b.tracks.items():
            for LL, ls, w in tr:
                if LL != L:
                    continue
                gg = ls.buffer(w / 2, 8)
                for p in (gg.geoms if hasattr(gg, 'geoms') else [gg]):
                    ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc=('#7a4f1d' if n == 'GND' else col),
                                       ec='none', alpha=0.95, zorder=3))
        for ref, c in C.items():
            for p in c.pads:
                lay = getattr(p, 'layers', ('B',))
                gp = p.geom()
                ax.add_patch(MPoly(list(gp.exterior.coords), closed=True, fc=col if L in lay else '#bbbbbb', ec='k', lw=0.3, zorder=4))
                if p.drill:
                    ax.add_patch(Circle((p.x, p.y), p.drill / 2, fc='white', ec='none', zorder=5))
            if c.body is not None and ((c.side == 'top') == (L == 'T')):
                ax.add_patch(MPoly(list(c.body.exterior.coords), closed=True, fc='none', ec='#222', lw=0.5, ls=':', zorder=6))
            ax.text(c.x, c.y, ref, fontsize=6.5, ha='center', va='center', zorder=7, color='#111', clip_on=True,
                    bbox=dict(fc='white', ec='none', alpha=0.55, pad=0.2))
        for n, vs in b.vias.items():
            for x, y in vs:
                isj = (x, y) in jholes
                ax.add_patch(Circle((x, y), R2.VIA_D / 2, fc='#ffd166' if isj else ('#2a9d8f' if n == 'GND' else '#f4a261'),
                                    ec='k', lw=0.5, zorder=8))
                ax.add_patch(Circle((x, y), 0.4, fc='white', ec='none', zorder=9))
        if L == 'T':
            for i, jm in enumerate(jumpers, 1):
                for key, kk in (('a', 'ka'), ('b', 'kb')):
                    if jm[kk] == 'ponto':
                        ax.add_patch(Circle(jm[key], JPAD_R, fc='#ffd166', ec='k', lw=0.6, zorder=10))
                ax.plot([jm['a'][0], jm['b'][0]], [jm['a'][1], jm['b'][1]], color='#e9a800', lw=2.6, zorder=11)
                mx, my = (jm['a'][0] + jm['b'][0]) / 2, (jm['a'][1] + jm['b'][1]) / 2
                ax.text(mx + 1.0, my + 1.0, f'JP{i}', fontsize=10, color='#7a5600', fontweight='bold', ha='left', zorder=12,
                        clip_on=True, bbox=dict(fc='white', ec='#e9a800', alpha=0.85, pad=0.3))
        for x, y, d, rk in D.HOLES:
            ax.add_patch(Circle((x, y), d / 2, fc='white', ec='k', lw=0.6, zorder=8))
        for s in D.SLOTS:
            ax.add_patch(MPoly(list(s.exterior.coords), closed=True, fc='white', ec='k', lw=0.6, zorder=8))
        ax.set_xlim(out.bounds[0] - 2, out.bounds[2] + 2)
        ax.set_ylim(out.bounds[1] - 2, out.bounds[3] + 2)
        ax.set_aspect('equal')
        ax.grid(lw=0.2, alpha=0.4)
        ax.set_title(('CIMA (lado dos componentes, vista de cima)' if L == 'T' else
                      'BAIXO (cobre de baixo, visto de CIMA / transparente)') + f' — {title}', fontsize=10)
    fig.tight_layout()
    fig.savefig(fn)
    for zfn, (x0, x1, y0, y1), ztitle in zooms:
        for ax, L in zip(axs, ('T', 'B')):
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_title(('CIMA' if L == 'T' else 'BAIXO (visto de cima)') + f' — {ztitle}', fontsize=11)
        fig.set_size_inches(24, 11.5 * (y1 - y0) / (x1 - x0) + 1.2)
        fig.tight_layout()
        fig.savefig(zfn)
    plt.close(fig)


PKG = {'esp': 'ESP32-C3 SuperMini (THT 2x8, fileiras a 15,24 mm)', 'dip8': 'DIP-8', 'sot223': 'SOT-223', 'sot23': 'SOT-23',
       'res': '1206', 'cap': '1206', 'ecap': 'Radial Ø6,3 passo 2,5', 'hdr': 'Barra 1x8 2,54 90°', 'wire': 'Ilhós p/ fio',
       'btn': 'KFC-A06 3x6x4,3 SMD 2T', 'xt30': 'XT30PW-M', 'qre': 'QRE1113GR'}


def tables(C, nets, b, jumpers, stitch, fn):
    L = ['# Seguidor fenolite v3 (dupla face) — dados para redesenhar no EasyEDA Pro', '',
         'Origem = centro do furo da turbina; +x = direita; +y = frente do robô; vista de CIMA; mm; rotação em graus, anti-horário.',
         'Face: "top" = lado dos componentes; "bottom" = SMD soldado embaixo da placa. Componentes PTH ficam sempre em cima.',
         'Pads SMD de "bottom" estão em coordenadas vistas de CIMA (no EasyEDA, coloque o componente na camada Bottom com a mesma posição).', '',
         '## Componentes', '', '| Ref | Valor | Encapsulamento | Face | X (mm) | Y (mm) | Rot (°) |', '|---|---|---|---|---|---|---|']
    for ref in sorted(C, key=lambda r: (C[r].kind, r)):
        c = C[ref]
        L.append(f'| {ref} | {c.value} | {PKG.get(c.kind, c.kind)} | {c.side} | {c.x:.2f} | {c.y:.2f} | {c.ang % 360:.0f} |')
    L += ['', '## Pads (posição absoluta, camadas onde pode soldar)', '', '| Pad | Rede | X | Y | Camadas |', '|---|---|---|---|---|']
    for ref in sorted(C):
        for p in C[ref].pads:
            net = p.net if p.net and not p.net.startswith('NC_') else 'NC'
            lay = '+'.join({'T': 'cima', 'B': 'baixo'}[x] for x in sorted(getattr(p, 'layers', ('B',)), reverse=True))
            L.append(f'| {ref}.{p.pin} | {net} | {p.x:.2f} | {p.y:.2f} | {lay} |')
    L += ['', '## Netlist', '', '| Rede | Pinos |', '|---|---|']
    for n in sorted(nets):
        L.append(f'| {n} | {" ".join(f"{p.ref}.{p.pin}" for p in nets[n])} |')
    out = D.outline_poly()
    L += ['', '## Contorno da placa (vértices em ordem; também em `placa_v3_contorno.dxf`)', '',
          ' '.join(f'({x:.2f},{y:.2f})' for x, y in list(out.exterior.coords)[:-1])]
    L += ['', '## Furos e rasgos mecânicos (sem cobre)', '', '| Função | X | Y | Furo |', '|---|---|---|---|']
    names = ['turbina'] + ['carcaça da turbina'] * 4 + ['caixa de redução'] * 4 + ['presilha da vareta'] * 4
    for nm, (x, y, d, rk) in zip(names, D.HOLES):
        L.append(f'| {nm} | {x:.2f} | {y:.2f} | Ø{d:g} mm |')
    for s in D.SLOTS:
        x0, y0, x1, y1 = s.bounds
        L.append(f'| rasgo da bateria | {(x0 + x1) / 2:.2f} | {(y0 + y1) / 2:.2f} | {x1 - x0:g} × {y1 - y0:g} mm |')
    jholes = {jm[k] for jm in jumpers for k, kk in (('a', 'ka'), ('b', 'kb')) if jm[kk] == 'furo'}
    L += ['', '## Vias (fio soldado nas duas faces; furo 0,8 mm, ilha Ø1,8 mm)', '', '| # | Rede | X | Y | Função |', '|---|---|---|---|---|']
    k = 0
    for n in sorted(b.vias):
        for x, y in b.vias[n]:
            if (x, y) in jholes:
                continue
            k += 1
            L.append(f'| V{k} | {n} | {x:.2f} | {y:.2f} | {"liga o GND de cima com o de baixo" if n == "GND" else "troca de face"} |')
    L += ['', '## Jumpers de fio (GND, por cima da placa)', '',
          '"furo" = furo de 0,8 mm com ilha nas duas faces; "ponto" = ponto de solda Ø2 no plano de GND de cima (sem furo).', '',
          '| # | Ponta A (X, Y) | Ponta B (X, Y) | Comprimento | Passa por cima de | Liga ao GND principal |', '|---|---|---|---|---|---|']
    for i, jm in enumerate(jumpers, 1):
        L.append(f'| JP{i} | {jm["a"][0]:.2f}, {jm["a"][1]:.2f} ({jm["ka"]}) | {jm["b"][0]:.2f}, {jm["b"][1]:.2f} ({jm["kb"]}) | '
                 f'{jm["comprimento"]} mm | {", ".join(jm.get("cruza", [])) or "-"} | {", ".join(jm["ilha"])} |')
    L += ['', '## Trilhas (rede, camada, largura, pontos)', '', '| Rede | Camada | Largura (mm) | Pontos (mm) |', '|---|---|---|---|']
    for n in sorted(b.tracks):
        for LL, ls, w in b.tracks[n]:
            pts = ' '.join(f'({x:.2f},{y:.2f})' for x, y in ls.coords)
            L.append(f'| {n} | {"cima" if LL == "T" else "baixo"} | {w} | {pts} |')
    open(fn, 'w').write('\n'.join(L) + '\n')


def write_dxf(fn):
    """Board outline (layer CONTORNO) + mechanical holes/slots (layer FUROS), mm, DXF R12 entities only."""
    ent = []

    def line(a, b, layer):
        ent.extend(['0', 'LINE', '8', layer, '10', f'{a[0]:.4f}', '20', f'{a[1]:.4f}', '30', '0.0',
                    '11', f'{b[0]:.4f}', '21', f'{b[1]:.4f}', '31', '0.0'])
    out = D.outline_poly()
    for ring in [out.exterior] + list(out.interiors):
        c = list(ring.coords)
        for a, b in zip(c[:-1], c[1:]):
            line(a, b, 'CONTORNO')
    for x, y, d, rk in D.HOLES:
        ent.extend(['0', 'CIRCLE', '8', 'FUROS', '10', f'{x:.4f}', '20', f'{y:.4f}', '30', '0.0', '40', f'{d / 2:.4f}'])
    for s in D.SLOTS:
        c = list(s.exterior.coords)
        for a, b in zip(c[:-1], c[1:]):
            line(a, b, 'FUROS')
    open(fn, 'w').write('\n'.join(['0', 'SECTION', '2', 'ENTITIES'] + ent + ['0', 'ENDSEC', '0', 'EOF']) + '\n')


def main(tag='x2'):
    C, nets, b, antenna = build_board(tag)
    jumpers = []
    pours = pours_of(b)
    rmap, groups, main_ = components(b, pours, jumpers)
    print('GND inicial:', [v for k, v in groups.items() if k != main_])
    stitch = smart_stitch(b, jumpers)
    pours = pours_of(b)
    rmap, groups, main_ = components(b, pours, jumpers)
    print(f'costura: {len(stitch)} vias {stitch}; ilhas: {[v for k, v in groups.items() if k != main_]}')
    close_with_jumpers(b, C, jumpers)
    for jm in jumpers:
        jm['cruza'] = crossed_nets(b, jm)
    pours = pours_of(b)
    rmap, groups, main_ = components(b, pours, jumpers)
    islands = [v for k, v in groups.items() if k != main_]
    # drop pour fragments that carry no GND copper (would be floating copper)
    for L in R2.LAYERS:
        l, n = ndimage.label(pours[L], structure=np.ones((3, 3)))
        keep = np.unique(l[b._cu['GND'][L] & (l > 0)])
        pours[L] = np.isin(l, keep[keep > 0]) & pours[L]
    print('GND final: ilhas', islands, '| jumpers', len(jumpers))
    Rf = dict(tracks={n: [(L, list(ls.coords), w) for L, ls, w in v] for n, v in b.tracks.items()}, vias=b.vias, failed=[],
              extra={n: [(L, list(p.exterior.coords)) for L, p in v] for n, v in b.extra.items()})
    pickle.dump(Rf, open(f'route_{tag}_final.pkl', 'wb'))
    pickle.dump(dict(pours=pours, grid=(b.g.x0, b.g.y0, b.g.W, b.g.H), jumpers=jumpers, stitch=stitch),
                open(f'pours_{tag}_final.pkl', 'wb'))
    R_, C_, nets_ = drc_v3.load(f'{tag}_final')
    nets_.pop('GND', None)
    errs, disc, cu = drc_v3.drc(R_, C_, nets_, verbose=True)
    nsig = sum(len(v) for n, v in b.vias.items() if n != 'GND')
    nhole = sum((jm['ka'] == 'furo') + (jm['kb'] == 'furo') for jm in jumpers)
    ngv = len(b.vias.get('GND', [])) - nhole
    title = (f'{len(disc)} redes abertas, DRC {len(errs)}, {nsig} vias de sinal, {ngv} vias de GND, '
             f'{len(jumpers)} jumpers de GND, {len(islands)} ilhas de GND')
    os.makedirs(f'{OUT}/imagens', exist_ok=True)
    render_final(b, C, pours, jumpers, f'{OUT}/imagens/placa_v3_roteamento.png', title,
                 zooms=[(f'{OUT}/imagens/placa_v3_zoom_nariz.png', (-30, 30, 10, 48), 'zoom no nariz (ESP + barra)'),
                        (f'{OUT}/imagens/placa_v3_zoom_jp1.png', (5, 45, -32, 16), 'zoom no lado direito (JP1, U2, U4)')])
    tables(C, nets, b, jumpers, stitch, f'{OUT}/TABELA_EASYEDA_v3.md')
    write_dxf(f'{OUT}/placa_v3_contorno.dxf')
    json.dump(dict(drc=len(errs), erros=errs, abertas=[n for n, _ in disc], vias_sinal=nsig,
                   vias_sinal_por_rede={n: len(v) for n, v in b.vias.items() if n != 'GND' and v},
                   vias_gnd=ngv, jumpers=jumpers, ilhas_gnd=islands, trilhas_gnd_manuais=MANUAL_GND),
              open(f'{OUT}/resumo_v3.json', 'w'), indent=1, ensure_ascii=False)
    print('RESUMO:', title)
    return jumpers, errs, disc, islands


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'x2')
