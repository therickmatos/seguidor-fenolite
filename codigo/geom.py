"""Footprints for the fenolite EVA-RT-style base (FINAL parts).
Units mm. Origin = turbine centre. +y = front. View from TOP (component side).
SMD parts live on the BOTTOM (copper) side: their local x is mirrored so the
physical part is correct once the board is flipped."""
import math
from shapely.geometry import Point, Polygon, box, LineString
from shapely import affinity

P = 2.54

def rot(x, y, a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return x * c - y * s, x * s + y * c

class Pad:
    def __init__(self, ref, pin, x, y, shape, w, h=None, drill=0.9, ang=0, side='tht', name=''):
        self.ref, self.pin, self.x, self.y = ref, str(pin), x, y
        self.shape, self.w, self.h, self.drill, self.ang, self.side = shape, w, (h or w), drill, ang, side
        self.name = name or str(pin)
        self.net = None
    def geom(self):
        if self.shape == 'circle':
            g = Point(self.x, self.y).buffer(self.w / 2, 24)
        else:  # rect / oval approx as rect
            g = box(-self.w / 2, -self.h / 2, self.w / 2, self.h / 2)
            g = affinity.rotate(g, self.ang, origin=(0, 0))
            g = affinity.translate(g, self.x, self.y)
        return g
    def __repr__(self):
        return f'{self.ref}.{self.pin}({self.name})@({self.x:.2f},{self.y:.2f})[{self.net}]'

class Comp:
    def __init__(self, ref, kind, x, y, ang, value=''):
        self.ref, self.kind, self.x, self.y, self.ang, self.value = ref, kind, x, y, ang, value
        self.pads, self.body = [], None
        self.side = 'top'
        self.height = 0
    def place(self, local_pads, body_poly, height=3, side='top'):
        mir = -1 if side == 'bottom' else 1
        for pin, name, lx, ly, shape, w, h, drill, pside in local_pads:
            gx, gy = rot(mir * lx, ly, self.ang)
            self.pads.append(Pad(self.ref, pin, self.x + gx, self.y + gy, shape, w, h, drill, ang=self.ang, side=pside, name=name))
        if body_poly is not None:
            b = affinity.scale(body_poly, xfact=mir, origin=(0, 0))
            b = affinity.rotate(b, self.ang, origin=(0, 0))
            self.body = affinity.translate(b, self.x, self.y)
        self.height = height
        self.side = side
        return self
    def pad(self, pin):
        for p in self.pads:
            if p.pin == str(pin):
                return p
        raise KeyError(f'{self.ref}.{pin}')

# ---------------- footprints (local coords, angle 0) -----------------
def fp_esp32c3(ref, x, y, ang):
    """ESP32-C3 SuperMini. Angle 0 = USB to +y. Rows at x=+-7.62, 8 pins @2.54.
    Row A (x=-7.62) from USB end: IO5,6,7,8,9,10,20,21. Row B (x=+7.62): 5V,GND,3V3,IO4,IO3,IO2,IO1,IO0."""
    A = ['5', '6', '7', '8', '9', '10', '20', '21']
    B = ['5V', 'GND', '3V3', '4', '3', '2', '1', '0']
    pads = []
    for i in range(8):
        yy = 3.5 * P - i * P
        pads.append(('IO' + A[i], 'IO' + A[i], -7.62, yy, 'circle', 1.7, 1.7, 1.0, 'tht'))
        nm = B[i] if B[i] in ('5V', 'GND', '3V3') else 'IO' + B[i]
        pads.append((nm, nm, 7.62, yy, 'circle', 1.7, 1.7, 1.0, 'tht'))
    body = box(-9.0, -11.25, 9.0, 11.25)
    c = Comp(ref, 'esp', x, y, ang, 'ESP32-C3').place(pads, body, height=4)
    c.usb = affinity.translate(affinity.rotate(box(-4.4, 10.5, 4.4, 12.5), ang, origin=(0, 0)), x, y)
    return c

def fp_dip8(ref, x, y, ang, names=None):
    """RZ7886 DIP-8. Angle 0: pins 1-4 down left col (x=-3.81, y 3.81..-3.81), 5-8 up right col."""
    names = names or {}
    pads = []
    for i in range(4):
        pads.append((str(i + 1), names.get(str(i + 1), str(i + 1)), -3.81, 3.81 - i * P, 'rect' if i == 0 else 'oval', 1.7, 1.5, 0.8, 'tht'))
        pads.append((str(8 - i), names.get(str(8 - i), str(8 - i)), 3.81, 3.81 - i * P, 'oval', 1.7, 1.5, 0.8, 'tht'))
    body = box(-3.3, -5.0, 3.3, 5.0)
    return Comp(ref, 'dip8', x, y, ang, 'RZ7886').place(pads, body, height=4)

def fp_sot223(ref, x, y, ang, names=('GND', 'OUT', 'IN', 'OUT')):
    """AMS1117 SOT-223 on BOTTOM. 3 pins pitch 2.3 on one edge + big tab (pin2 net) on the other."""
    pads = [('1', names[0], -2.3, -3.1, 'rect', 1.2, 2.0, 0, 'bottom'),
            ('2', names[1], 0.0, -3.1, 'rect', 1.2, 2.0, 0, 'bottom'),
            ('3', names[2], 2.3, -3.1, 'rect', 1.2, 2.0, 0, 'bottom'),
            ('4', names[3], 0.0, 2.3, 'rect', 3.6, 2.2, 0, 'bottom')]
    body = box(-3.3, -1.8, 3.3, 1.8)
    return Comp(ref, 'sot223', x, y, ang, 'AMS1117-3.3').place(pads, body, height=1.8, side='bottom')

def fp_sot23(ref, x, y, ang, names=('G', 'S', 'D')):
    """AO3400A SOT-23 on BOTTOM. pin1 G (bl), pin2 S (br), pin3 D (top-centre)."""
    pads = [('1', names[0], -0.95, -1.1, 'rect', 1.0, 1.1, 0, 'bottom'),
            ('2', names[1], 0.95, -1.1, 'rect', 1.0, 1.1, 0, 'bottom'),
            ('3', names[2], 0.0, 1.1, 'rect', 1.0, 1.1, 0, 'bottom')]
    body = box(-1.45, -0.7, 1.45, 0.7)
    return Comp(ref, 'sot23', x, y, ang, 'AO3400A').place(pads, body, height=1.1, side='bottom')

def fp_smd(ref, x, y, ang, value, kind='res', size='0805'):
    """0805 resistor/cap on BOTTOM. Pads at +-1.0, trace can pass between them under the body."""
    g = {'0805': (1.0, 1.2, 1.4, 2.0, 1.3), '1206': (1.6, 1.4, 1.8, 3.2, 1.7)}[size]
    dx, pw, ph, bx, by = g
    pads = [('1', '1', -dx, 0, 'rect', pw, ph, 0, 'bottom'), ('2', '2', dx, 0, 'rect', pw, ph, 0, 'bottom')]
    body = box(-bx / 2, -by / 2, bx / 2, by / 2)
    return Comp(ref, kind, x, y, ang, value).place(pads, body, height=1.0, side='bottom')

def fp_radial(ref, x, y, ang, dia, pitch, value):
    pads = [('1', '+', -pitch / 2, 0, 'rect', 1.8, 1.8, 0.9, 'tht'),
            ('2', '-', pitch / 2, 0, 'circle', 1.8, 1.8, 0.9, 'tht')]
    return Comp(ref, 'ecap', x, y, ang, value).place(pads, Point(0, 0).buffer(dia / 2, 24), height=max(6, dia))

def fp_header(ref, x, y, ang, n, names, value):
    pads = [(str(i + 1), names[i], (i - (n - 1) / 2) * P, 0, 'rect' if i == 0 else 'circle', 1.7, 1.7, 1.0, 'tht') for i in range(n)]
    body = box(-n * P / 2, -1.27, n * P / 2, 1.27)
    return Comp(ref, 'hdr', x, y, ang, value).place(pads, body, height=3)

def fp_wirepads(ref, x, y, ang, names, value, pitch=2.54, d=2.2, drill=1.0):
    n = len(names)
    pads = [(str(i + 1), names[i], (i - (n - 1) / 2) * pitch, 0, 'rect' if i == 0 else 'circle', d, d, drill, 'tht') for i in range(n)]
    body = box(-n * pitch / 2, -1.5, n * pitch / 2, 1.5) if n > 1 else box(-1.5, -1.5, 1.5, 1.5)
    return Comp(ref, 'wire', x, y, ang, value).place(pads, body, height=0)

def fp_btn2(ref, x, y, ang, value='BTN'):
    """2-pin tactile 6x3.5mm, pins out the ends at ~4.5mm pitch, PTH."""
    pads = [('1', 'A', -2.4, 0, 'rect', 1.6, 1.1, 0.9, 'tht'), ('2', 'B', 2.4, 0, 'oval', 1.6, 1.1, 0.9, 'tht')]
    body = box(-3.0, -1.75, 3.0, 1.75)
    return Comp(ref, 'btn', x, y, ang, value).place(pads, body, height=4.3)

def fp_xt30(ref, x, y, ang, names=('VBAT', 'GND')):
    """XT30PW-M horizontal PCB male. Pins Ø1.9 at 5mm pitch; body extends to +y (place with
    ang=180 so it overhangs the back edge). Mounting posts omitted (can be glued)."""
    pads = [('1', names[0], -2.5, 0, 'rect', 3.4, 3.4, 1.9, 'tht'),
            ('2', names[1], 2.5, 0, 'circle', 3.4, 3.4, 1.9, 'tht')]
    body = box(-5.0, 1.0, 5.0, 10.1)
    return Comp(ref, 'xt30', x, y, ang, 'XT30PW-M').place(pads, body, height=6)

def fp_qre(ref, x, y, ang):
    """QRE1113GR on BOTTOM (copper) side. Top-view pins: 1 A(-2,-0.9) 2 K(2,-0.9) 3 E(2,0.9) 4 C(-2,0.9)."""
    loc = [('1', 'A', -2.0, -0.9), ('2', 'K', 2.0, -0.9), ('3', 'E', 2.0, 0.9), ('4', 'C', -2.0, 0.9)]
    pads = [(p, n, lx, ly, 'rect', 1.5, 0.9, 0, 'bottom') for p, n, lx, ly in loc]
    return Comp(ref, 'qre', x, y, ang, 'QRE1113GR').place(pads, box(-1.8, -1.45, 1.8, 1.45), height=1.7, side='bottom')
