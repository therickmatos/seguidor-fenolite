import design as D

ESP_ORDER = ['5V', 'GND', '3V3', 'IO4', 'IO3', 'IO2', 'IO1', 'IO0', 'IO5', 'IO6', 'IO7', 'IO8', 'IO9', 'IO10', 'IO20', 'IO21']
ESP_WHY = {
    'IO4': 'C0 do mux (ADC1) - reto ate a barra', 'IO3': 'S3 do mux - reto ate a barra',
    'IO2': 'S2 do mux - reto ate a barra (GPIO2 nao define o boot, so glitch)',
    'IO1': 'S1 do mux - reto ate a barra', 'IO0': 'S0 do mux - reto ate a barra',
    'IO5': 'FI motor ESQ', 'IO6': 'GATE turbina via 220R; 4k7 p/ GND (pull-up de reset -> 0,31 V)',
    'IO7': 'BI motor ESQ', 'IO8': 'sensor de marca ESQ (digital, pull-up 47k)',
    'IO9': 'botao (= BOOT do modulo, pull-up interno)', 'IO10': 'BI motor DIR',
    'IO20': 'FI motor DIR; 10k p/ GND (pull-up no reset)', 'IO21': 'sensor de marca DIR (digital, entrada)',
    '3V3': 'saida do AMS1117 / pino 1 da barra', 'GND': 'plano de terra', '5V': 'NAO conectado'}

def main():
    C = D.build()
    nets = D.nets_from(C)
    print('=== TABELA DE COMPONENTES (x,y,ang; origem=centro turbina, +y=frente) ===')
    print(f'{"ref":4} {"valor":12} {"lado":7} {"x":>7} {"y":>7} {"ang":>5}  pacote')
    pkg = {'esp': 'modulo THT', 'dip8': 'DIP-8 THT', 'sot223': 'SOT-223', 'sot23': 'SOT-23',
           'res': '1206', 'cap': '1206', 'ecap': 'radial THT', 'hdr': 'header THT', 'wire': 'ilhos fio',
           'btn': 'KFC-A06 3x6x4,3 SMD', 'xt30': 'XT30PW-M THT', 'qre': 'QRE SMD'}
    for ref in sorted(C, key=lambda r: (C[r].kind, r)):
        c = C[ref]
        print(f'{ref:4} {c.value:12} {c.side:7} {c.x:7.2f} {c.y:7.2f} {c.ang:5.0f}  {pkg.get(c.kind, c.kind)}')

    print('\n=== MAPA DE PINOS DO ESP32-C3 SuperMini ===')
    u1 = C['U1']
    byname = {p.name: p for p in u1.pads}
    for nm in ESP_ORDER:
        p = byname[nm]
        print(f'  {nm:4} -> {p.net:7}  | {ESP_WHY.get(nm, "")}')

    print('\n=== NETLIST (net -> pinos) ===')
    for n in sorted(nets):
        if n.startswith('NC_'):
            continue
        pins = ' '.join(f'{p.ref}.{p.pin}' for p in nets[n])
        print(f'  {n:8}: {pins}')
    ncs = [n for n in nets if n.startswith('NC_')]
    print('  (nao-conectados:', ', '.join(sorted(ncs)), ')')

if __name__ == '__main__':
    main()
