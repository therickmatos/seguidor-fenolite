"""Writes MAPA_PINOS.txt (v3) from the design netlist: ESP32-C3 pin map + netlist."""
import sys
import design as D

FUNC = {
    '5V': 'NAO ligado',
    'GND': 'plano de GND',
    '3V3': 'saida do AMS1117 (U2) e pino 1 da barra (J2.1)',
    'IO4': 'C0 do mux 74HC4067 (ADC1), reto ate a barra',
    'IO3': 'S3 do mux, reto ate a barra',
    'IO2': 'S2 do mux, reto ate a barra (GPIO2 nao define o boot)',
    'IO1': 'S1 do mux, reto ate a barra',
    'IO0': 'S0 do mux, reto ate a barra',
    'IO5': 'BI_A -> U3.1 (motor ESQ). Hi-Z no reset; o pull-down interno do RZ7886 segura em 0',
    'IO6': 'FI_A -> U3.2 (motor ESQ) + R7 10k p/ GND (IO6/MTCK tem pull-up no reset)',
    'IO7': 'GATE_D -> R1 220R -> gate do Q1 (turbina); R2 4k7 gate->GND',
    'IO8': 'MK_L sensor de marca ESQ (digital). Firmware: INPUT_PULLUP. Strapping: alto ao gravar pelo BOOT',
    'IO9': 'BTN -> SW1 -> GND (e o proprio BOOT, pull-up interno)',
    'IO10': 'BI_B -> U4.1 (motor DIR)',
    'IO20': 'FI_B -> U4.2 (motor DIR) + R6 10k p/ GND (IO20/U0RXD tem pull-up no reset)',
    'IO21': 'MK_R sensor de marca DIR (digital). Firmware: INPUT_PULLUP',
}


def main(fn):
    C = D.build()
    nets = D.nets_from(C)
    L = ['MAPA DE PINOS v3 (placa roteada x2) - gerado de design.py', '',
         '=== ESP32-C3 SuperMini (U1): fileira da frente (barra) e depois a de tras ===']
    for p in sorted(C['U1'].pads, key=lambda p: (-round(p.y, 1), p.x)):
        L.append(f'  {p.name:5s} -> {p.net if not p.net.startswith("NC_") else "NC":7s} | {FUNC.get(p.name, "")}')
    L += ['', '=== Sensores de marca (QRE1113GR, embaixo, na ponta dos bracos) ===',
          '  pino 1 A <- R4/R5 470R <- VBAT  (LED ~12-15 mA com 2S)',
          '  pino 2 K -> GND, pino 3 E -> GND, pino 4 C -> MK_L / MK_R (baixo = viu branco)',
          '', '=== RZ7886 (U3 esquerdo, U4 direito) ===',
          '  1 BI, 2 FI, 3 GND, 4 VCC(VBAT), 5/6 FO -> MA1/MB1, 7/8 BO -> MA2/MB2',
          '', '=== NETLIST (rede -> pinos) ===']
    for n in sorted(nets):
        if not n.startswith('NC_'):
            L.append(f'  {n:7s}: {" ".join(f"{p.ref}.{p.pin}" for p in nets[n])}')
    open(fn, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/projects/sandbox/repo/MAPA_PINOS.txt')
