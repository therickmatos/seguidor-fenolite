"""Clear approval renders (top view) with the original EVA-RT outline overlaid."""
import json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle, Rectangle, Patch
from matplotlib.lines import Line2D
import design as D

NOMES = {
    'U1': 'ESP32-C3\nSuperMini', 'J2': 'barra p/ sensores (8 pinos)', 'SW1': 'botao\nSMD',
    'U3': 'RZ7886\nmotor ESQ', 'U4': 'RZ7886\nmotor DIR', 'C3': '220uF', 'C5': '220uF',
    'MA': 'fios\nmotor E', 'MB': 'fios\nmotor D', 'TP': 'fios\nturbina',
    'J1': 'XT30\nbateria', 'SL': 'QRE\nmarca E', 'SR': 'QRE\nmarca D',
    'U2': 'AMS1117\n(sob motor D)', 'Q1': 'AO3400\n(sob motor E)', 'R1': '', 'R2': '', 'R3': '', 'R4': '', 'R5': '', 'R6': '',
    'R8': '', 'R9': '', 'C1': '', 'C2': '', 'C4': '', 'C6': '', 'C7': ''}

def polys(g):
    if g is None or g.is_empty: return []
    return list(g.geoms) if hasattr(g, 'geoms') else [g]

def eva_outline():
    try:
        d = json.load(open('eva_geom.json'))
        return d['outline_polys'][0]
    except Exception:
        return None

def draw(ax, C, zoom=False):
    out = D.outline_poly()
    for p in polys(out):
        ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc='#f1e3c4', ec='#5a4630', lw=2.0, zorder=0))
    eva = eva_outline()
    if eva:
        ax.add_patch(MPoly(eva, closed=True, fc='none', ec='#d62828', lw=1.6, ls='--', zorder=9))
    # mechanical parts (top) - light
    for name, poly, mh in D.top_keepouts_h():
        col = {'pes da carcaca': '#6c757d', 'janela helice': '#adb5bd', 'anel carcaca': '#dee2e6',
               'caixa reducao': '#8ecae6', 'motor': '#8ecae6', 'bateria': '#ffd6a5',
               'presilha vareta': '#6c757d'}.get(name, '#ccc')
        for g in polys(poly):
            ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fc=col, ec='none', alpha=0.45, zorder=1))
    for p in polys(D.SUCTION):
        ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc='none', ec='#2a9d8f', lw=1.6, ls=':', zorder=2))
    for x, y, d, rk in D.HOLES:
        ax.add_patch(Circle((x, y), d / 2, fc='white', ec='k', lw=0.9, zorder=3))
    for s in D.SLOTS:
        ax.add_patch(MPoly(list(s.exterior.coords), closed=True, fc='white', ec='k', lw=0.8, zorder=3))
    for ref, c in C.items():
        top = c.side == 'top'
        smd = c.kind in ('sot223', 'sot23', 'res', 'cap', 'btn', 'qre')
        if top and smd:
            col, fcb, ls = '#2d6a4f', '#b7e4c7', '-'
        elif top:
            col, fcb, ls = '#1d3557', '#a8dadc', '-'
        else:
            col, fcb, ls = '#c1121f', '#ffccd5', '--'
        for p in polys(c.body):
            ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc=fcb,
                               ec=col, lw=1.2, ls=ls, alpha=0.9, zorder=4))
        if getattr(c, 'usb', None) is not None:
            for p in polys(c.usb):
                ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc='#444', ec='k', lw=0.5, zorder=5))
        for p in c.pads:
            fc = '#e85d04' if p.side == 'bottom' else ('#52b788' if p.side == 'top' else '#e9c46a')
            if p.shape == 'circle':
                ax.add_patch(Circle((p.x, p.y), p.w / 2, fc=fc, ec='k', lw=0.4, zorder=6))
                if p.drill:
                    ax.add_patch(Circle((p.x, p.y), p.drill / 2, fc='white', ec='none', zorder=6))
            else:
                ax.add_patch(Rectangle((p.x - p.w / 2, p.y - p.h / 2), p.w, p.h, fc=fc, ec='k', lw=0.4, zorder=6))
            if zoom and ref == 'U1':
                ax.text(p.x, p.y + (1.6 if p.y > c.y else -1.6), p.name.replace('IO', ''), fontsize=8,
                        ha='center', va='center', color='#000', zorder=8, fontweight='bold')
        lab = NOMES.get(ref, '')
        txt = ref if not lab else f'{ref}\n{lab}'
        if zoom or lab:
            ax.text(c.x, c.y, txt, fontsize=(9 if zoom else 7.5), ha='center', va='center', color=col,
                    zorder=10, fontweight='bold', bbox=dict(fc='white', ec=col, lw=0.5, alpha=0.85, pad=0.5))

def main():
    C = D.build()
    D.nets_from(C)
    # ---- full board ----
    fig, ax = plt.subplots(figsize=(18, 11), dpi=110)
    draw(ax, C)
    ax.set_xlim(-78, 78); ax.set_ylim(-36, 48); ax.set_aspect('equal')
    ax.grid(True, lw=0.3, alpha=0.4)
    ax.set_xlabel('x (mm)'); ax.set_ylabel('y (mm)  -> FRENTE do robo para cima')
    ax.set_title('Seguidor fenolite - POSICIONAMENTO v2 (DUPLA FACE) (vista de CIMA, frente para cima, origem = centro da turbina)',
                 fontsize=13, fontweight='bold')
    bb = D.outline_poly().bounds
    leg = [Patch(fc='#f1e3c4', ec='#5a4630', label=f'placa fenolite v2 dupla face ({bb[2]-bb[0]:.0f} x {bb[3]-bb[1]:.0f} mm)'),
           Line2D([0], [0], color='#d62828', ls='--', lw=1.6, label='contorno ORIGINAL do EVA-RT (100 x 61 mm)'),
           Line2D([0], [0], color='#2a9d8f', ls=':', lw=1.6, label='placa de succao embaixo (sem PTH/SMD)'),
           Patch(fc='#a8dadc', ec='#1d3557', label='componente PTH em cima'),
           Patch(fc='#b7e4c7', ec='#2d6a4f', label='SMD em cima (sob os motores)'),
           Patch(fc='#ffccd5', ec='#c1121f', ls='--', label='SMD no lado do cobre (embaixo)'),
           Patch(fc='#8ecae6', alpha=0.45, label='motores / caixas de reducao'),
           Patch(fc='#6c757d', alpha=0.45, label='pes da carcaca / presilhas'),
           Patch(fc='#ffd6a5', alpha=0.45, label='bateria (em cima, atras)')]
    ax.legend(handles=leg, loc='upper left', fontsize=9, framealpha=0.95)
    ax.annotate('', xy=(12, 44), xytext=(12, 18.5), arrowprops=dict(arrowstyle='<->', color='#d62828'))
    ax.text(13, 31, 'nariz\n+15 mm\n(p/ o ESP)', color='#d62828', fontsize=9, va='center')
    fig.tight_layout()
    fig.savefig('/projects/sandbox/PLACA_v2_posicionamento.png')
    plt.close(fig)
    # ---- zoom on the nose with ESP pin names ----
    fig, ax = plt.subplots(figsize=(11, 11), dpi=110)
    draw(ax, C, zoom=True)
    ax.set_xlim(-20, 20); ax.set_ylim(14, 47); ax.set_aspect('equal')
    ax.grid(True, lw=0.3, alpha=0.4)
    ax.set_title('Zoom no nariz: ESP32-C3 (numeros = GPIO) + barra (nada embaixo do ESP)', fontsize=12, fontweight='bold')
    fig.tight_layout()
    fig.savefig('/projects/sandbox/PLACA_v2_nariz_zoom.png')
    plt.close(fig)
    print('ok')

if __name__ == '__main__':
    main()
