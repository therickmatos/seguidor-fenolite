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

## 28/10 — MUDANÇA DE ESCOPO (Erick)
- **DUPLA FACE.** A placa crua é de 10 × 15 cm: o contorno precisa caber em 150 × 100 (hoje 144 × 75 cabe deitado).
- **Nada embaixo do ESP:** tirar o AMS1117 e os resistores dali.
- **Região embaixo dos motores pode levar SMD** (no EVA-RT os IFX ficam ali). Nesse lugar cabem SMD do lado de CIMA, porque o motor está a ~3,4 mm da placa.
  - Ponto a conferir: altura do SOT-223 (1,8 mm) e do SOT-23 (~1,1 mm). Cabem embaixo do motor 8520, que deixa ~3,4 mm.
- Abas laterais estão OK.
- **Botão SMD KFC-A06.** Opções: 4×4×1,5 mm com 4 terminais, ou 3×6×4,3 mm com 2 terminais. Escolher qual fica melhor com trilha ≥ 0,7.
- **XT30 sai do centro:** a bateria fica deitada atrás, como no EVA-RT. Pôr o XT30 à esquerda/direita, ou na parte da frente da placa.
- Liberdade para girar componentes e trocar pinos. Evitar aglomerar.

### Implicações da dupla face
- Fenolite dupla face caseira não tem furo metalizado. Toda via vira um fio soldado dos dois lados.
- PTH só solda bem no lado de baixo: o corpo do componente impede a solda em cima, exceto no DIP com uma folga.
- Regra: trilha em cima só pode chegar a pad PTH se der para soldar em cima, ou por via. Dar preferência a SMD em cima, onde ficam os componentes.
- **Plano:**
  - GND como plano em baixo (+ cima onde der).
  - SMD do lado de CIMA, embaixo dos motores (AMS1117, AO3400A, R, C): fica longe do chão e resolve a altura do SOT-223.
  - Embaixo continua valendo a placa de sucção (sem componente). Trilhas OK.

### Decisões v2 (dupla face)
- **Pés reais da carcaça** (voxel, ±45°, margem de 0,5): r 19,2–27,0, ±10° nas diagonais. A posição dos IFX do EVA-RT (±22,1; −12,45) NÃO colide.
- **Embaixo do motor 8520:** o fundo do motor fica a ~3,4 mm da placa, então peças de até ~2,8 mm cabem embaixo dele em cima. Cabem SOT-223 (1,8), SOT-23 (1,1), 0805 e 1206.
- **Botão:** KFC-A06 2 terminais 3×6×4,3 SMD (EM CIMA).
  - Pads grandes e afastados nas pontas: o mais fácil com trilha de 0,7 e folga de 0,6. Os 4 pads pequenos do 4×4 apertam a folga.
  - Tem 4,3 mm de altura, fácil de apertar.
  - Pads de 1,8×1,4 em ±3,6 mm. CONFERIR com o paquímetro (a página só tem as medidas na imagem).
- **XT30PW-M:** canto traseiro (esquerdo), atrás da caixa de redução, com a boca para trás e o corpo para fora da borda traseira. A bateria fica deitada atrás, como no EVA-RT.
- **SMD em cima:** AMS1117+caps embaixo do motor esquerdo; AO3400A+R embaixo do motor direito, perto da turbina.
- **Vias caseiras:** fio soldado dos dois lados.
  - EVITAR via dentro da placa de sucção (o calombo de solda embaixo).
  - Preferir as vias fora de |x|<23,6.

### GPIO2: confirmado
Pelo guia da Espressif, nota [1]: o GPIO2 NÃO define o modo de boot; o pull-up é recomendado só por causa de glitches. Por isso o GPIO2 serve como S2 do mux (entrada de alta impedância; um glitch no boot não causa nada).

### Mapa de pinos v2
- **Fileira da frente → barra, ligação reta:** 3V3, GND, IO4=C0, IO3=S3, IO2=S2, IO1=S1, IO0=S0.
- **Fileira de trás:**

| Pino | Função | Observação |
|---|---|---|
| IO5 | FI_A | |
| IO6 | GATE | 4,7 k p/ GND: o pull-up de reset (~45 k) dá 0,31 V, MOSFET desligado |
| IO7 | BI_A | |
| IO8 | MK_L | entrada; o pull-up do sensor mantém nível alto, sem efeito no boot |
| IO9 | BTN | é o próprio BOOT |
| IO10 | BI_B | |
| IO20 | FI_B | +10 k p/ GND |
| IO21 | MK_R | entrada |

- Sensores de marca digitais (pull-up de 47 k a 3V3).
- Turbina (Q1, R1, R2 + ilhós) embaixo do motor ESQUERDO. AMS1117 + C1/C2 embaixo do motor DIREITO. Botão na faixa direita.

## Editor interativo (28/10)
- Fonte: editor_template.html. O export_editor.py gera o editor_placa.html (arquivo único, 72 KB, sem dependências) com os dados do design.py: contorno, furos, keepouts com altura, componentes e netlist.
- Funções:
  - arrastar, girar (R / Shift+R), virar face (F, só SMD), setas e grade;
  - desfazer/refazer, editar o contorno (com simetria), ligações (MST por rede);
  - checagem ao vivo: placa de sucção, borda, furos, folga de 0,6 entre pads por camada, corpos × mecânica com altura, corpos sobrepostos, tamanho de 10×15;
  - exportar texto/JSON para colar no chat, importar, autosave no localStorage.
- Testado no Playwright: sem erros de JS, arrastar e girar funcionam, a checagem bate com a do Python e o export funciona.
- Publicado no repo, em editor/editor_placa.html (commit 8148a28).
- Formas de abrir:
  - raw.githack (mostra um aviso antes, clicar "Open the page");
  - baixar o arquivo e abrir localmente.
  - Pages dá 403.
- Para IMPORTAR o que o Erick colar: pegar a linha JSON (`{"v":"v2","comps":{ref:{x,y,ang,side,flip}},"outline":[...]}`) e aplicar no build_v2.

## 28/10 — layout do Erick vindo do editor (v3)
- O Erick mudou as posições no editor e colou o JSON (salvo em layout_erick.json).
- **Intenção dele:**
  - Cap, ponte H e MA/MB alinhados em colunas, buscando harmonia visual.
  - SMDs de cima (menos o SW1) levados para trás, embaixo da bateria (EVA-RT: bateria sobre suportes de 3 mm, com o ATmega embaixo).
  - Arrumar a estética.
  - **ROTEAR em dupla face** e devolver no GitHub.
  - Trilha mín. 0,7 mm, de preferência mais larga.
  - Se ficar difícil chegar aos sensores laterais, os resistores podem ir para antes das abas.
- **Minha arrumação:**
  - Colunas alinhadas: MB centrado sobre o U4; C5 alinhado com o SW1; C3 alinhado com o TP; U3 e U4 na mesma altura.
  - C4/C6 colados nos pinos 3-4 dos RZ; R6 perto do U4.
- **Bateria:**
  - SMD de até 2,5 mm cabe embaixo dela (suportes de 3 mm).
  - Keepout nos suportes junto aos rasgos.
  - **AVISAR:** o AMS1117 embaixo da ponta da bateria aquece a LiPo.
- **Roteador de 2 camadas:** grade MCP em 3 planos (cima / via em retícula de 1 mm / baixo), com custo de via.
  - **Via:** NÃO entra na placa de sucção.
  - **PTH conectado só embaixo:** ESP, barra, DIP, eletrolíticos.
  - **PTH conectado nos dois lados:** ilhós e XT30.
- Keepout de cobre na antena do ESP: lado oposto ao USB, x > 10 no nariz.
- GND: plano nas duas faces, com costura mínima de vias e sem ilhas.

## Roteamento v3: estado (28/10, ~08:30)
- **Roteador próprio, sequencial (router2):**
  - 40 ordens testadas: sempre sobram 3–12 redes abertas.
  - Gargalo: as 8 trilhas da fileira de trás do ESP (IO5..IO21) saem por baixo e precisam se abrir entre a borda da placa de sucção e o nariz.
- **PathFinder:** não convergiu (VBAT×GND em pads de 220 µF e 3V3×GND no nariz).
- **Decisão:** usar o FREEROUTING v2.5.0 (Java 25 disponível), que faz push-and-shove e rip-up de verdade.
  - Exportar DSN Specctra com 2 camadas, keepouts e regras (0,7 / 0,6). Importar o SES.
  - Depois rodar o MEU DRC vetorial e a checagem de conectividade, e fazer o plano de GND.
- **Freerouting no sandbox:** precisa de HOME gravável. Rodar com `HOME=fr/home -Duser.home=fr/home`.

## Roteamento v3: resultado (x2) — 28/10
- **Freerouting** só nos sinais (GND fora), custo de camada cima 1,3 / baixo 1,0 / via 20, larguras sinal 0,8 / potência 1,1 / 3V3 0,9. Resultado: 0 redes abertas, DRC vetorial 0, 7 vias de sinal (3V3 ×2, BI_A, BTN, GATE_D, MK_L ×2).
- **GND (final_v3.py):** plano nas duas faces → vias de costura só onde juntam grupos (busca em largura entre pedaços do plano) → jumper de fio para o que sobrar.
  - Trilha de GND de 0,7 mm embaixo, do R6.2 ao C6.1/U4.3 (o R6.2 ficava num bolsão entre FI_B, VBAT e BTN).
  - Via de BI_A baixada de y 21,29 para 20,55 (ainda a 1,42 mm do chevron da placa de sucção): abre a faixa de GND de cima entre a via e o ESP, e o GND do nariz fecha com 1 via em vez de jumper.
  - Resultado: **2 vias de GND** (braço esquerdo e lado do ESP) + **1 jumper (JP1, 4,4 mm)** sobre a trilha de 3V3, na ponta de dentro do motor direito. 0 ilhas.
  - Pedaços de plano sem GND (o triângulo embaixo da turbina, cercado pelas trilhas do ESP e sem via possível por causa da placa de sucção) foram retirados.
- Bug antigo do close_islands (pontas do jumper nunca unidas, jumper de 0 mm, duplicado) resolvido: o union-find agora une as pontas do jumper explicitamente.
