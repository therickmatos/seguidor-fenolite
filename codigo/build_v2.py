"""v2 placement (double-sided fenolite 10x15 cm). Imported by design.py."""
from geom import *


def build_v2():
    C = {}
    add = lambda c: C.__setitem__(c.ref, c) or c
    # ---------- nose: only the ESP and the sensor-bar header (nothing under the ESP) ----------
    add(fp_header('J2', 0.0, 41.0, 0, 8, ['3V3', 'GND', 'NC', 'C0', 'S3', 'S2', 'S1', 'S0'], 'barra'))
    add(fp_esp32c3('U1', 0.0, 30.0, 90))                       # USB to the left edge

    # ---------- left front strip: left motor driver ----------
    add(fp_dip8('U3', -32.5, 6.8, 90, {'1': 'BI_A', '2': 'FI_A', '3': 'GND', '4': 'VBAT', '5': 'MA1', '6': 'MA1', '7': 'MA2', '8': 'MA2'}))
    add(fp_radial('C3', -24.4, 3.0, 90, 6.3, 2.5, '220uF'))    # in the housing air gap (like EVA-RT)
    add(fp_smd('C4', -29.96, 0.9, 180, '100nF', kind='cap', side='bottom'))   # under U3 pins 3-4
    add(fp_smd('R7', -40.0, 0.0, 90, '10k', side='bottom'))                    # BI_A (IO6) pull-down
    add(fp_wirepads('MA', -39.6, 10.9, 270, ['MA1', 'MA2'], 'MOT ESQ', pitch=5.08, d=1.8, drill=0.9))

    # ---------- right front strip: right motor driver + button ----------
    add(fp_dip8('U4', 32.5, 6.8, 90, {'1': 'BI_B', '2': 'FI_B', '3': 'GND', '4': 'VBAT', '5': 'MB1', '6': 'MB1', '7': 'MB2', '8': 'MB2'}))
    add(fp_radial('C5', 24.4, 3.0, 90, 6.3, 2.5, '220uF'))
    add(fp_smd('C6', 35.04, 0.9, 180, '100nF', kind='cap', side='bottom'))    # under U4 pins 3-4
    add(fp_smd('R6', 31.23, -1.6, 90, '10k', side='bottom'))                  # FI_B (IO20) pull-down
    add(fp_wirepads('MB', 39.6, 10.9, 270, ['MB2', 'MB1'], 'MOT DIR', pitch=3.0, d=1.8, drill=0.9))
    add(fp_btn_smd('SW1', 29.8, 13.0, 0))                                     # KFC-A06 3x6x4.3, top

    # ---------- under the LEFT motor (top side SMD, <=2.8 mm): turbine switch ----------
    add(fp_wirepads('TP', -27.0, -3.6, 0, ['VBAT', 'TURB_N'], 'TURBINA', pitch=3.0, d=1.8, drill=0.9))
    add(fp_sot23('Q1', -22.0, -9.0, 0, ('GATE', 'GND', 'TURB_N'), side='top'))
    add(fp_smd('R1', -26.2, -9.2, 90, '220R', side='top'))                    # IO6 -> gate
    add(fp_smd('R2', -22.3, -12.6, 0, '4k7', side='top'))                     # gate pull-down

    # ---------- under the RIGHT motor (top side SMD): 3V3 regulator ----------
    add(fp_sot223('U2', 24.5, -9.6, 0, ('GND', '3V3', 'VBAT', '3V3'), side='top'))
    add(fp_smd('C1', 28.9, -12.8, 90, '10uF', kind='cap', side='top'))        # AMS in
    add(fp_smd('C2', 28.9, -7.4, 90, '22uF', kind='cap', side='top'))         # AMS out

    # ---------- battery: XT30PW-M at the rear-left corner, mouth to the back ----------
    add(fp_xt30('J1', -34.5, -31.5, 180))

    # ---------- mark sensors on the lateral arms (bottom QRE) ----------
    add(fp_qre('SL', -68.0, 4.5, 0))
    add(fp_smd('R4', -58.0, 2.0, 0, '470R', side='bottom'))   # LED from VBAT
    add(fp_qre('SR', 68.0, 4.5, 0))
    add(fp_smd('R5', 58.0, 2.0, 0, '470R', side='bottom'))   # LED from VBAT
    return C


NETMAP_V2 = {
    # ESP front row -> header straight; rear row -> drivers/sensors
    'U1.5V': 'NC_5V', 'U1.GND': 'GND', 'U1.3V3': '3V3',
    'U1.IO4': 'C0', 'U1.IO3': 'S3', 'U1.IO2': 'S2', 'U1.IO1': 'S1', 'U1.IO0': 'S0',
    'U1.IO5': 'BI_A', 'U1.IO6': 'FI_A', 'U1.IO7': 'GATE_D', 'U1.IO8': 'MK_L',
    'U1.IO9': 'BTN', 'U1.IO10': 'BI_B', 'U1.IO20': 'FI_B', 'U1.IO21': 'MK_R',
    'J2.1': '3V3', 'J2.2': 'GND', 'J2.3': 'NC_J2', 'J2.4': 'C0', 'J2.5': 'S3', 'J2.6': 'S2', 'J2.7': 'S1', 'J2.8': 'S0',
    'U2.1': 'GND', 'U2.2': '3V3', 'U2.3': 'VBAT', 'U2.4': '3V3',
    'C1.1': 'VBAT', 'C1.2': 'GND', 'C2.1': '3V3', 'C2.2': 'GND',
    'J1.1': 'VBAT', 'J1.2': 'GND',
    'U3.1': 'BI_A', 'U3.2': 'FI_A', 'U3.3': 'GND', 'U3.4': 'VBAT', 'U3.5': 'MA1', 'U3.6': 'MA1', 'U3.7': 'MA2', 'U3.8': 'MA2',
    'U4.1': 'BI_B', 'U4.2': 'FI_B', 'U4.3': 'GND', 'U4.4': 'VBAT', 'U4.5': 'MB1', 'U4.6': 'MB1', 'U4.7': 'MB2', 'U4.8': 'MB2',
    'C3.1': 'VBAT', 'C3.2': 'GND', 'C4.1': 'GND', 'C4.2': 'VBAT', 'C5.1': 'VBAT', 'C5.2': 'GND', 'C6.1': 'GND', 'C6.2': 'VBAT',
    'R6.1': 'FI_B', 'R6.2': 'GND', 'R7.1': 'FI_A', 'R7.2': 'GND',
    'MA.1': 'MA1', 'MA.2': 'MA2', 'MB.1': 'MB2', 'MB.2': 'MB1', 'TP.1': 'VBAT', 'TP.2': 'TURB_N',
    'Q1.1': 'GATE', 'Q1.2': 'GND', 'Q1.3': 'TURB_N', 'R1.1': 'GATE_D', 'R1.2': 'GATE', 'R2.1': 'GATE', 'R2.2': 'GND',
    'SW1.1': 'BTN', 'SW1.2': 'GND',
    'SL.1': 'LEDA_L', 'SL.2': 'GND', 'SL.3': 'GND', 'SL.4': 'MK_L',
    'SR.1': 'LEDA_R', 'SR.2': 'GND', 'SR.3': 'GND', 'SR.4': 'MK_R',
    'R4.1': 'VBAT', 'R4.2': 'LEDA_L',
    'R5.1': 'VBAT', 'R5.2': 'LEDA_R',
}
