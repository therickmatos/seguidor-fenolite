# Notas de trabalho — base do seguidor em fenolite

## Plano (fase atual: ANTES de rotear)
1. Recriar o código de referência (geom/design/router/main) em `seguidor/`.
2. Clonar o EVA-RT, conferir o contorno e os furos e analisar os STL (pernas da carcaça, placa de sucção, caixa de redução).
3. Conferir os datasheets: XT30PW-M, RZ7886, AMS1117, AO3400A, QRE1113GR, botão de 2 pinos, SuperMini e strapping do C3.
4. Fazer o posicionamento v1 compacto, gerar o PNG e o mapa de pinos, e esperar a aprovação do Erick.

## Conclusões parciais
- **Zona da placa de sucção (embaixo):** nem PTH nem SMD, porque qualquer coisa ali levanta a placa. Só cobre plano. Isso inclui os furos de jumper.
- **Área útil para PTH (em cima):** fora de |x|<23,6 com y<21,5. Sobram as laterais (x 23,6–50, y −1,8–13, menos as presilhas) e a aba da frente. Isso dá uns 750 mm², e as peças PTH pedem ~1000 mm². Vai precisar crescer um pouco.
- **Corpo sobre a zona:** pode ficar em cima da zona, desde que os pinos fiquem fora (por exemplo, o ESP ou o eletrolítico entre as pernas da carcaça).
- **Fenolite de 1,6 mm:** a face de baixo fica ~0,6 mm mais perto do chão que no EVA-RT (~1,9 mm contra 2,5 mm). SOT-223 (1,8 mm) e QRE (1,7 mm) ficam no limite.
- **Jumper SMD:** um 0 Ω 1206 sobre uma trilha FUNCIONA na face simples, porque a trilha passa entre os pads, por baixo do corpo cerâmico. Vale como alternativa ao jumper de fio.
- **ADC1:** só GPIO0–4, todos na fileira direita do SuperMini.

## Medições reais (Gerber + STL do EVA-RT) — corrigem o contexto
- **Furos NPTH:** batem com o contexto. Os PTH do EVA-RT ficam assim:
  - 220 µF: terminais em (±22,0; 0,79/3,33), ou seja, DENTRO da placa de sucção. O EVA-RT tolera isso.
  - Motores: (±36,58; 0/2,54). Turbina: (29,72; 1,78/4,32). Bateria: (−37,62/−35,08; −30,25).
  - Furos de 0,8 mm em y = 22,74, de x = −7 a 7 (passo de 2,0 mm): conector de 8 vias.
- **Placa de sucção:** x ±23,08 e y −27,5…17,1, com frente em CHEVRON até (0; 20,9). Furo de Ø16,6 e 4 furos de parafuso. Não tem recortes.
- **Carcaça da turbina:** é um "X" (4 braços de ~4,4 mm em z 11–14,2) com 4 pés nas diagonais (r 19,8–26,5, ±6° mais ~10° de ressalto de um lado).
  - **A HÉLICE TEM Ø34** (impeller_fan.stl) e gira entre a placa e o X. Em cima, nada com r < 18.
  - Entre os pés fica a saída radial de ar, onde o EVA-RT pôs os 220 µF.
- **Caixa de redução:**
  - Base sólida de 2,5 mm. Furo do motor de Ø10 (o original é 1020) a 7,64 mm da placa.
  - **Eixo da roda Ø1,9 em y = −22,56**, a 7,0 mm da placa. O motor fica em y = −11,23.
  - Porca M2 presa na caixa, logo **a cabeça do parafuso fica EMBAIXO da placa**, em (±35,25; −3,73/−26,55).
- **Altura do chão:** com o EVA-RT a 2,5 mm (FR-4 de 1,0 mm), a roda tem Ø ≈ 21 mm.
  - Fenolite de 1,6 mm com a mesma roda: face de baixo a ~1,9 mm do chão.
  - Com roda de Ø22: ~2,4 mm.
- **Presilha das varetas (barilla_clamp):** tem uma fenda de 1,0 mm (para a placa de 1,0 mm). **Com fenolite de 1,6 mm, reimprimir com fenda de 1,6 mm.**
- **Asas do EVA-RT:** são placas de 14×5 mm no Gerber; nas fotos, a asa sai ~22 mm da borda.

## Datasheets conferidos
- **XT30PW-M** (horizontal, macho; footprint KiCad oficial a partir da spec Amass):
  - 2 pinos com furo de Ø1,9, pad de 3,5 e 5,0 mm entre si.
  - 2 pinos de fixação com furo de Ø1,0 em (+3; −10) e (−8; −10).
  - Corpo de 9,9 × 9,0 mm, de y −4,1 a −13,1. Courtyard de 14,3 × 15,9 mm. Peso 1,32 g.
- **XT30UPB-M** (vertical, macho): 2 pinos com furo de Ø1,8, pad de 3,0 e 5,0 mm entre si. Courtyard de 11,2 × 6,2 mm.
- **RZ7886 (RZ2018, mesma pinagem):**
  - 1 BI, 2 FI, 3 GND, 4 VCC, 5/6 FO, 7/8 BO.
  - Vcc 3–12 V (máx. 13). ViH ≥ 2,2 V.
  - Ii = 100–150 µA a 3 V, o que dá um pull-down interno de ~20–30 k.
  - Circuito de aplicação: 0,1 µF + 470 µF. Pede cobre nos pinos 5–8.
- **ESP32-C3** (guia de hardware da Espressif):
  - **SPI boot exige GPIO2 = 1, e o default é FLUTUANTE. Pôr 10 k de pull-up no IO2.**
  - GPIO6 (MTCK) tem pull-up no reset (eFuse padrão). Pôr 10 k de pull-down se for entrada do RZ.
  - GPIO9 tem pull-up (BOOT). GPIO20 tem pull-up. GPIO21 tem saída alta. GPIO8 flutua (LED do módulo).
  - GPIO7 e GPIO10 têm glitch de 5 ns no power-up (inofensivo).
- **Bateria GNB 2S 350 mAh:** 46×21×12 mm (60C) ou 49×16×12 mm (LiHV 70C).
- **Botão:** tátil de 6×3,5×4,3/5 mm com 2 pinos PTH (comum no Brasil, "chave táctil 2 terminais").

## Topologia: conclusões (não refazer)
- **Header da barra:** precisa das duas fileiras do ESP. S0–S3 ficam na fileira IO5..IO21 e C0/3V3 na fileira IO0..IO4/3V3.
  - Opção A: ESP de pé (eixo em y) com a ponta virada para o header. O USB fica para trás e inacessível.
  - Opção B: ESP deitado (eixo em x) com o USB numa borda lateral. Custa ~1–2 cruzamentos no nariz.
- **Plano de GND:** cada par de trilhas vizinhas forma uma faixa. A faixa precisa encostar num pad de GND numa das pontas, senão vira ilha.
- **Cobre:** só embaixo. A caixa de redução e o motor NÃO bloqueiam trilhas, só as cabeças dos parafusos (r ≈ 2,6).
- **Decisão:** parar de derivar à mão. Montar o posicionamento em código e testar a roteabilidade com o roteador (vários ordenamentos).

## Posicionamento v1 (para aprovação) — 28/10
- Arquivos: geom.py, design.py (contorno+placement+netlist+keepouts), place.py (render+checagem), report.py (tabela+mapa), router.py+main.py (teste de roteamento).
- Placa 144×76 mm. CORPO PRINCIPAL ~96×60 (≈ EVA-RT 100×61), NARIZ central de 24 mm de largura e +15 mm (para o ESP THT — o EVA-RT evita isso com MCU SMD sobre a placa de sucção). Braços dos sensores de marca até ±72 (QRE a ±68 ≈ EVA-RT).
- Checagem de colisão: SEM colisões (keepouts com altura: anel da carcaça só barra peças >11 mm; pés, janela da hélice, motores, caixas, bateria, presilhas = sólidos).
- ESP no nariz, eixo em x, USB para a esquerda (acessível). AMS1117 + caps no nariz (lado do cobre), na faixa livre entre as fileiras do ESP. Header da barra na ponta; botão na ponta (perto do IO2).
- Drivers RZ nas faixas laterais da frente (fora de baixo dos motores), saídas viradas para os ilhós dos motores. 220µF + 100nF por RZ. MOSFET da turbina (AO3400 SOT-23) + 220R + 10k no lado direito, perto dos ilhós da turbina. XT30PW-M pendurado na borda de trás.
- Roteador guloso (PESSIMISTA, conforme aviso do contexto): ~35 jumpers de sinal + ~14 costuras de GND. Não é o número final; serve só para confirmar que conecta. GND de face única é o gargalo.
- PENDENTE: aprovação do Erick antes de rotear de verdade.

## 28/10 — usuário não viu a imagem
- Imagens agora na RAIZ do workspace: PLACA_v1_posicionamento.png e PLACA_v1_nariz_zoom.png.
- Checagem nova (folga pad-pad entre redes + corpos sobrepostos) achou erros no v1: ilhós MA/MB em cima dos pinos dos RZ, C4/C6 sobre pads, 220µF sobre os RZ.
- Correção: RZ deitados (ang 90, saídas viradas para frente), ilhós dos motores na lateral externa, 220µF nos vãos de ar da carcaça (como no EVA-RT), turbina/MOSFET abaixo do RZ direito. Borda frontal das faixas laterais sobe para y=15 (+2 mm, pequeno).
