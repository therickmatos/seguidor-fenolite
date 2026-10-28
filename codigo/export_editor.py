"""Export the current design (design.py) into a self-contained HTML placement editor."""
import json, math, os
import design as D
from geom import rot

HERE = os.path.dirname(os.path.abspath(__file__))


def r3(v):
    return round(float(v), 3)


def to_local(c, x, y):
    lx, ly = rot(x - c.x, y - c.y, -c.ang)
    return [r3(lx), r3(ly)]


def poly_coords(g):
    if g is None or g.is_empty:
        return []
    gs = list(g.geoms) if hasattr(g, 'geoms') else [g]
    return [[[r3(x), r3(y)] for x, y in p.exterior.coords[:-1]] for p in gs]


def export(fn_out):
    C = D.build()
    nets = D.nets_from(C)
    comps = []
    for ref, c in sorted(C.items()):
        pads = []
        for p in c.pads:
            pads.append(dict(pin=p.pin, name=p.name, net=p.net, lx=to_local(c, p.x, p.y)[0], ly=to_local(c, p.x, p.y)[1],
                             shape=p.shape, w=r3(p.w), h=r3(p.h), drill=r3(p.drill or 0), side=p.side,
                             opt=bool(getattr(p, 'opt', False))))
        body = None
        if c.body is not None:
            body = [to_local(c, x, y) for x, y in c.body.exterior.coords[:-1]]
        extra = [[to_local(c, x, y) for x, y in g.exterior.coords[:-1]] for g in getattr(c, 'extra', [])]
        usb = [to_local(c, x, y) for x, y in c.usb.exterior.coords[:-1]] if getattr(c, 'usb', None) is not None else None
        comps.append(dict(ref=ref, value=c.value, kind=c.kind, side=c.side, height=r3(c.height),
                          x=r3(c.x), y=r3(c.y), ang=r3(c.ang), pads=pads, body=body, extra=extra, usb=usb))
    out = D.outline_poly()
    outline = poly_coords(out)[0]
    try:
        eva = json.load(open(os.path.join(HERE, 'eva_geom.json')))['outline_polys'][0]
        eva = [[r3(x), r3(y)] for x, y in eva[:-1]]
    except Exception:
        eva = []
    kt = []
    for name, poly, mh in D.top_keepouts_h():
        for pc in poly_coords(poly):
            kt.append(dict(name=name, poly=pc, min_h=mh))
    kb = []
    for name, polys in D.bottom_keepouts().items():
        for poly in polys:
            for pc in poly_coords(poly):
                kb.append(dict(name=name, poly=pc))
    data = dict(
        version='v2', units='mm',
        outline=outline, eva_outline=eva,
        holes=[dict(x=r3(x), y=r3(y), d=r3(d), rk=r3(rk)) for x, y, d, rk in D.HOLES],
        slots=[poly_coords(s)[0] for s in D.SLOTS],
        suction=poly_coords(D.SUCTION)[0],
        keepouts_top=kt, keepouts_bot=kb,
        comps=comps,
        nets={n: [f'{p.ref}.{p.pin}' for p in ps] for n, ps in nets.items() if not n.startswith('NC_')},
        rules=dict(clearance=0.6, edge=0.6, track=0.7, board_max=[150, 100]),
    )
    tpl = open(os.path.join(HERE, 'editor_template.html'), encoding='utf-8').read()
    html = tpl.replace('/*__DATA__*/null', json.dumps(data, separators=(',', ':')))
    open(fn_out, 'w', encoding='utf-8').write(html)
    print('ok', fn_out, len(html) // 1024, 'KB', len(comps), 'comps', len(data['nets']), 'nets')


if __name__ == '__main__':
    import sys
    export(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'editor_placa.html'))
