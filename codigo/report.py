import design as D

ESP_ORDER = ['IO5', 'IO6', 'IO7', 'IO8', 'IO9', 'IO10', 'IO20', 'IO21', 'IO0', 'IO1', 'IO2', 'IO3', 'IO4', '3V3', 'GND', '5V']
ESP_WHY = {
    'IO10': 'FI motor ESQ (seguro no boot)', 'IO7': 'BI motor ESQ (glitch 5ns inofensivo)',
    'IO6': 'FI motor DIR  -> 10k pull-down (MTCK tem pull-up no reset)',
    'IO5': 'BI motor DIR (strapping leve, so saida)',
    'IO8': 'S0 do mux (strapping; nada forca nivel no boot)',
    'IO9': 'S1 do mux (BOOT; pull-up do modulo mantem)',
    'IO20': 'S2 do mux (RX, pull-up no boot)', 'IO21': 'S3 do mux (TX, log no boot)',
    'IO4': 'C0 do mux (ADC1)', 'IO3': 'GATE turbina via 220R (+10k p/ GND)',
    'IO2': 'Botao (strapping; precisa 10k pull-up p/ 3V3 -> SPI boot)',
    'IO1': 'Sensor marca DIR (ADC1)', 'IO0': 'Sensor marca ESQ (ADC1)',
    '3V3': 'saida do AMS1117', 'GND': 'plano de terra', '5V': 'NAO conectado (sem 5V na placa)'}

def main():
    C = D.build()
    nets = D.nets_from(C)
    print('=== TABELA DE COMPONENTES (x,y,ang; origem=centro turbina, +y=frente) ===')
    print(f'{"ref":4} {"valor":12} {"lado":7} {"x":>7} {"y":>7} {"ang":>5}  pacote')
    pkg = {'esp': 'modulo THT', 'dip8': 'DIP-8 THT', 'sot223': 'SOT-223', 'sot23': 'SOT-23',
           'res': '0805', 'cap': '0805', 'ecap': 'radial THT', 'hdr': 'header THT', 'wire': 'ilhos fio',
           'btn': 'tactil 2p THT', 'xt30': 'XT30PW-M THT', 'qre': 'QRE SMD'}
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
