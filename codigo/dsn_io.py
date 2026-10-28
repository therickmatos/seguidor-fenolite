"""Specctra DSN export (for Freerouting) and SES import, for the v3 double-sided board."""
import math, re, os
from shapely.geometry import Point, box, Polygon
import design as D
import route_v3 as RV

UM = 1000.0          # mm -> um
VIA_NAME = 'via1800'
VIA_D, VIA_DRILL = 1.8, 0.8

CLASSES = {
    'power': (['VBAT', 'MA1', 'MA2', 'MB1', 'MB2', 'TURB_N'], 1.2),
    'p3v3': (['3V3', 'GND'], 0.9),
}
DEFAULT_W = 0.8
CLEAR = 0.6


def u(v):
    return int(round(v * UM))


def ring(coords):
    return ' '.join(f'{u(x)} {u(y)}' for x, y in coords)


def poly_items(g):
    if g is None or g.is_empty:
        return []
    return list(g.geoms) if hasattr(g, 'geoms') else [g]


def preroute(C):
    """Fixed copper in the nose.
    3V3: ESP 3V3 pin -> top jog -> header pin 1;  ESP 3V3 pin -> under the module (bottom) -> right end
         -> right lane down -> via (13.0, 22.0) where the regulator feed (routed on top along the right side) lands.
    GND: ESP GND pin <-> header pin 2 straight on the bottom."""
    u1, j2 = C['U1'], C['J2']
    p3 = [p for p in u1.pads if p.name == '3V3'][0]
    pg = [p for p in u1.pads if p.name == 'GND'][0]
    j21, j22 = j2.pad('1'), j2.pad('2')
    vy = (p3.y + 0.85 + j21.y - 0.85) / 2.0
    ym = u1.y + 2.0                     # lane between the two pin rows, under the module (bottom)
    rx = u1.x + 12.9
    wires = [('3V3', 'B', 0.9, [(p3.x, p3.y), (p3.x, vy)]),
             ('3V3', 'T', 0.9, [(p3.x, vy), (j21.x, vy), (j21.x, j21.y)]),
             ('3V3', 'B', 0.9, [(p3.x, p3.y), (p3.x, ym), (rx, ym), (rx, 22.0)]),
             ('GND', 'B', 0.9, [(pg.x, pg.y), (j22.x, j22.y)])]
    # GND rails along the upper edge of each sensor arm: QRE cathode -> arm root (keeps the arm pour attached)
    vias = [('3V3', p3.x, vy), ('3V3', rx, 22.0)]
    return wires, vias
PREROUTE = True


def export(fn, widths=None, skip_nets=(), use_preroute=True, seed_ses=None, seed_protect=False, gnd_top_center=None, shuffle_seed=None, layer_cost=None):
    widths = widths or {}
    C = D.build()
    nets = {n: ps for n, ps in D.nets_from(C).items() if not n.startswith('NC_') and n not in skip_nets}
    out = D.outline_poly()
    L = []
    L.append(f'(pcb "{os.path.basename(fn)}"')
    L.append('  (parser (string_quote ") (space_in_quoted_tokens on) (host_cad "seguidor") (host_version "v3"))')
    L.append('  (resolution um 10)')
    L.append('  (unit um)')
    L.append('  (structure')
    L.append('    (layer F.Cu (type signal) (property (index 0)))')
    L.append('    (layer B.Cu (type signal) (property (index 1)))')
    L.append(f'    (boundary (path pcb 0 {ring(list(out.exterior.coords))}))')
    # keepouts: holes (copper clearance radius) on both layers
    for x, y, d, rk in D.HOLES:
        L.append(f'    (keepout "furo" (circle signal {u(2 * rk)} {u(x)} {u(y)}))')
    for s in D.SLOTS:
        for p in poly_items(s.buffer(0.5)):
            L.append(f'    (keepout "rasgo" (polygon signal 0 {ring(list(p.exterior.coords))}))')
    # bottom: gearbox bolt heads
    for x, y in D.GEARBOX_SCREWS:
        L.append(f'    (keepout "cabeca" (circle B.Cu {u(5.2)} {u(x)} {u(y)}))')
    # top: no copper under the flush ESP module nor near its antenna
    esp = C['U1']
    for p in poly_items(esp.body.buffer(0.2)):
        L.append(f'    (keepout "esp" (polygon F.Cu 0 {ring(list(p.simplify(0.05).exterior.coords))}))')
    ex, ey = esp.x, esp.y
    ant = box(9.9, ey - 9.0, 14.5, ey + 9.2)
    L.append(f'    (keepout "antena" (polygon F.Cu 0 {ring(list(ant.exterior.coords))}))')
    # via keepouts: suction plate, housing feet, gearboxes, rod clamps, fan window, component bodies
    vk = [D.SUCTION_REAL.buffer(0.5)]
    for name, poly, mh in D.top_keepouts_h():
        if name in ('pes da carcaca', 'caixa reducao', 'presilha vareta', 'janela helice'):
            vk.append(poly)
    vk += [Point(x, y).buffer(2.6, 24) for x, y in D.GEARBOX_SCREWS]
    for c in C.values():
        if c.body is not None and c.kind != 'wire':
            vk.append(c.body.buffer(0.3))
    for g in vk:
        for p in poly_items(g):
            L.append(f'    (via_keepout "" (polygon signal 0 {ring(list(p.simplify(0.05).exterior.coords))}))')
    if gnd_top_center is not None:
        for p in poly_items(gnd_top_center):
            L.append(f'    (keepout "plano_gnd_cima" (polygon F.Cu 0 {ring(list(p.exterior.coords))}))')
    L.append(f'    (via "{VIA_NAME}")')
    L.append(f'    (rule (width {u(DEFAULT_W)}) (clearance {u(CLEAR)}))')
    L.append('  )')
    # placement: one image per component, pads already in the rotated frame, placed at rot 0 on front
    L.append('  (placement')
    for ref, c in sorted(C.items()):
        L.append(f'    (component "IMG_{ref}" (place "{ref}" {u(c.x)} {u(c.y)} front 0))')
    L.append('  )')
    L.append('  (library')
    stacks = {}
    for ref, c in sorted(C.items()):
        pins = []
        for p in c.pads:
            if getattr(p, 'opt', False):
                continue          # plastic mounting posts: not copper
            lay = getattr(p, 'layers', ('B',)) if p.side == 'tht' else (('T',) if p.side == 'top' else ('B',))
            rot = int(round(p.ang)) % 180
            w, h = (p.w, p.h) if rot == 0 else (p.h, p.w)
            key = (p.shape, round(w, 3), round(h, 3), lay)
            name = f'PS_{p.shape}_{int(w*1000)}x{int(h*1000)}_{"".join(lay)}'
            stacks[name] = key
            pins.append(f'      (pin "{name}" "{p.pin}" {u(p.x - c.x)} {u(p.y - c.y)})')
        L.append(f'    (image "IMG_{ref}"')
        L += pins
        L.append('    )')
    for name, (shape, w, h, lay) in stacks.items():
        L.append(f'    (padstack "{name}"')
        for la in lay:
            ln = 'F.Cu' if la == 'T' else 'B.Cu'
            if shape == 'circle':
                L.append(f'      (shape (circle {ln} {u(w)}))')
            else:
                L.append(f'      (shape (rect {ln} {u(-w/2)} {u(-h/2)} {u(w/2)} {u(h/2)}))')
        L.append('      (attach off)')
        L.append('    )')
    L.append(f'    (padstack "{VIA_NAME}"')
    L.append(f'      (shape (circle F.Cu {u(VIA_D)}))')
    L.append(f'      (shape (circle B.Cu {u(VIA_D)}))')
    L.append('      (attach off)')
    L.append('    )')
    L.append('  )')
    L.append('  (network')
    order = sorted(nets.items())
    if shuffle_seed is not None:
        import random
        random.Random(shuffle_seed).shuffle(order)
    for n, ps in order:
        if len(ps) < 2:
            continue
        L.append(f'    (net "{n}" (pins {" ".join(f"{p.ref}-{p.pin}" for p in ps)}))')
    used = set()
    for cname, (members, w) in CLASSES.items():
        ms = [m for m in members if m in nets and len(nets[m]) > 1]
        used |= set(ms)
        ww = widths.get(cname, w)
        L.append(f'    (class "{cname}" {" ".join(chr(34)+m+chr(34) for m in ms)}')
        L.append(f'      (circuit (use_via "{VIA_NAME}"))')
        L.append(f'      (rule (width {u(ww)}) (clearance {u(CLEAR)})))')
    rest = [n for n in sorted(nets) if n not in used and len(nets[n]) > 1]
    L.append(f'    (class "sinal" {" ".join(chr(34)+m+chr(34) for m in rest)}')
    L.append(f'      (circuit (use_via "{VIA_NAME}"))')
    L.append(f'      (rule (width {u(widths.get("sinal", DEFAULT_W))}) (clearance {u(CLEAR)})))')
    L.append('  )')
    if seed_ses:
        tr, vs = import_ses(seed_ses)
        L.append('  (wiring')
        for net, segs in tr.items():
            if net in skip_nets:
                continue
            for lay, pts, w in segs:
                if len(pts) >= 2:
                    ln = 'F.Cu' if lay == 'T' else 'B.Cu'
                    L.append(f'    (wire (path {ln} {u(w)} {ring(pts)}) (net "{net}")' + (' (type protect))' if seed_protect else ')'))
        for net, pts in vs.items():
            if net in skip_nets:
                continue
            for x, y in pts:
                L.append(f'    (via "{VIA_NAME}" {u(x)} {u(y)} (net "{net}")' + (' (type protect))' if seed_protect else ')'))
        L.append('  )')
    elif use_preroute:
        wires, pvias = preroute(C)
        L.append('  (wiring')
        for net, lay, w, pts in wires:
            ln = 'F.Cu' if lay == 'T' else 'B.Cu'
            L.append(f'    (wire (path {ln} {u(w)} {ring(pts)}) (net "{net}") (type protect))')
        for net, x, y in pvias:
            L.append(f'    (via "{VIA_NAME}" {u(x)} {u(y)} (net "{net}") (type protect))')
        L.append('  )')
    else:
        L.append('  (wiring)')
    L.append(')')
    open(fn, 'w').write('\n'.join(L) + '\n')
    if layer_cost:
        tc, bc, vc = layer_cost
        R = ['(rules PCB seguidor', '  (autoroute_settings', '    (fanout off)', '    (autoroute on)', '    (postroute on)', '    (vias on)',
             f'    (via_costs {vc})', '    (plane_via_costs 5)', '    (start_ripup_costs 100)', '    (start_pass_no 1)',
             f'    (layer_rule F.Cu (active on) (preferred_direction horizontal) (preferred_direction_trace_costs {tc}) (against_preferred_direction_trace_costs {tc * 1.4:.2f}))',
             f'    (layer_rule B.Cu (active on) (preferred_direction vertical) (preferred_direction_trace_costs {bc}) (against_preferred_direction_trace_costs {bc * 1.4:.2f}))',
             '  )', ')']
        open(fn.replace('.dsn', '.rules'), 'w').write('\n'.join(R) + '\n')
    return C, nets


def _tokens(s):
    return re.findall(r'\(|\)|"[^"]*"|[^\s()]+', s)


def _parse(tok):
    stack = [[]]
    for t in tok:
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def import_ses(fn):
    tree = _parse(_tokens(open(fn).read()))
    res = 10.0  # resolution um 10 -> units of 0.1 um
    def find(node, key):
        if isinstance(node, list):
            if node and node[0] == key:
                yield node
            for ch in node:
                yield from find(ch, key)
    for r in find(tree, 'resolution'):
        if len(r) >= 3:
            res = float(r[2])
            break
    k = 1.0 / res / UM  # file units -> mm
    tracks, vias = {}, {}
    for no in find(tree, 'network_out'):
        for net in no[1:]:
            if not isinstance(net, list) or net[0] != 'net':
                continue
            name = net[1]
            for it in net[2:]:
                if not isinstance(it, list):
                    continue
                if it[0] == 'wire':
                    for path in it[1:]:
                        if isinstance(path, list) and path[0] == 'path':
                            lay = 'T' if path[1] == 'F.Cu' else 'B'
                            w = float(path[2]) * k
                            nums = [float(v) for v in path[3:] if not isinstance(v, list)]
                            pts = [(nums[i] * k, nums[i + 1] * k) for i in range(0, len(nums) - 1, 2)]
                            tracks.setdefault(name, []).append((lay, pts, round(w, 3)))
                elif it[0] == 'via':
                    x, y = float(it[2]) * k, float(it[3]) * k
                    vias.setdefault(name, []).append((x, y))
    return tracks, vias


if __name__ == '__main__':
    export('fr/seguidor_v3.dsn')
    print(open('fr/seguidor_v3.dsn').read()[:1500])
