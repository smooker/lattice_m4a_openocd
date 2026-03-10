# M4A3-64/32 — Datasheet Specs Extract

Extracted from `M4A5-64_32-6JC.pdf` (MACH 4 Family datasheet, Lattice/Vantis).

---

## Device Summary

| Parameter | Value |
|-----------|-------|
| Family | MACH 4A (ispMACH 4000) |
| Part | M4A3-64/32 |
| Macrocells | 64 (4 blocks x 16) |
| I/O pins | 32 |
| PAL blocks | 4 (A, B, C, D) |
| Product terms/macrocell | 5 (redistributable via Logic Allocator) |
| Clock/Input pins | 2 (CLK0/I0, CLK1/I1) |
| Technology | EEPROM (non-volatile, no config memory needed) |
| ISP | Yes, IEEE 1532 via JTAG |
| Boundary Scan | IEEE 1149.1 |
| JTAG ID | `0x17486157` |
| IR length | 10 bits |

---

## Absolute Maximum Ratings (M4LV / M4A3)

| Parameter | Value |
|-----------|-------|
| Storage temperature | -65 to +150 C |
| Ambient temperature (powered) | -55 to +100 C |
| Junction temperature | +130 C |
| Supply voltage (VCC to GND) | -0.5 to +4.5 V |
| DC input voltage | -0.5 to 6.0 V |
| Static discharge voltage | 2000 V |
| Latchup current (TA = -40 to +85 C) | 200 mA |

---

## Operating Ranges

| Grade | Temperature | VCC |
|-------|-------------|-----|
| Commercial (C) | 0 to +70 C | 3.0 to 3.6 V |
| Industrial (I) | -40 to +85 C | 3.0 to 3.6 V |

---

## 3.3V DC Characteristics

| Symbol | Parameter | Min | Typ | Max | Unit |
|--------|-----------|-----|-----|-----|------|
| VOH | Output HIGH voltage (IOH = -100 uA) | VCC - 0.2 | | | V |
| VOH | Output HIGH voltage (IOH = -3.2 mA) | 2.4 | | | V |
| VOL | Output LOW voltage (IOL = 100 uA) | | | 0.2 | V |
| VOL | Output LOW voltage (IOL = 24 mA) | | | 0.5 | V |
| VIH | Input HIGH voltage | 2.0 | | 5.5 | V |
| VIL | Input LOW voltage | -0.3 | | 0.8 | V |
| IIH | Input HIGH leakage | | | 5 | uA |
| IIL | Input LOW leakage | | | -5 | uA |
| ISC | Short-circuit current | -15 | | -160 | mA |

**Note:** Total IOL per PAL block must not exceed 64 mA.

---

## Capacitance

| Symbol | Parameter | Typ | Unit |
|--------|-----------|-----|------|
| CIN | Input capacitance | 6 | pF |
| CI/O | Output capacitance | 8 | pF |

---

## MACH 4A Timing (M4A3 speed grades)

### Combinatorial Delays

| Parameter | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|-----------|----|-----|----|-----|----|-----|-----|-----|------|
| tPDI (internal) | 3.5 | 4.0 | 4.0 | 4.5 | 5.0 | 7.0 | 9.0 | 11.0 | ns |
| tPD (pin-to-pin) | 5.0 | 5.5 | 6.0 | 6.5 | 7.5 | 10.0 | 12.0 | 14.0 | ns |

### Registered Delays

| Parameter | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|-----------|----|-----|----|-----|----|-----|-----|-----|------|
| tSS (sync setup, D-type) | 3.0 | 3.5 | 4.0 | 4.0 | 5.5 | 6.0 | 7.0 | 10.0 | ns |
| tHS (sync hold) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | ns |
| tCOS (sync clk-to-output) | 4.0 | 4.0 | 4.5 | 4.5 | 5.0 | 5.5 | 6.5 | 6.5 | ns |
| tCOA (async clk-to-output) | 6.5 | 6.5 | 7.0 | 7.0 | 8.5 | 11.0 | 13.0 | 15.0 | ns |

### Latched Delays

| Parameter | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|-----------|----|-----|----|-----|----|-----|-----|-----|------|
| tSSL (sync latch setup) | 4.0 | 4.0 | 4.5 | 4.5 | 6.0 | 7.0 | 8.0 | 10.0 | ns |
| tPDL (transparent latch-to-out) | 7.0 | 7.0 | 8.0 | 8.0 | 10.0 | 12.0 | 14.0 | 15.0 | ns |

### Gate-to-Output Delays

| Parameter | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|-----------|----|-----|----|-----|----|-----|-----|-----|------|
| tCOSI (sync gate-to-internal) | 3.0 | 3.0 | 3.0 | 3.0 | 3.5 | 4.5 | 7.0 | 8.0 | ns |
| tCOS (sync gate-to-output) | 4.5 | 4.5 | 5.0 | 5.0 | 6.0 | 7.5 | 10.0 | 11.0 | ns |
| tCOA (async gate-to-output) | 7.5 | 7.5 | 8.0 | 8.0 | 11.0 | 13.0 | 16.0 | 18.0 | ns |

### Output Delays

| Parameter | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|-----------|----|-----|----|-----|----|-----|-----|-----|------|
| tBUF (output buffer) | 1.5 | 1.5 | 2.0 | 2.0 | 2.5 | 3.0 | 3.0 | 3.0 | ns |
| tSLW (slow slew adder) | 2.5 | 2.5 | 2.5 | 2.5 | 2.5 | 2.5 | 2.5 | 2.5 | ns |
| tEA (output enable) | 7.5 | 7.5 | 8.5 | 8.5 | 9.5 | 10.0 | 12.0 | 15.0 | ns |
| tER (output disable) | 7.5 | 7.5 | 8.5 | 8.5 | 9.5 | 10.0 | 12.0 | 15.0 | ns |

### Reset/Preset Delays

| Parameter | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|-----------|----|-----|----|-----|----|-----|-----|-----|------|
| tSR (async rst/pst to output) | 9.0 | 9.2 | 10.0 | 10.0 | 12.0 | 14.0 | 16.0 | 19.0 | ns |
| tSRR (rst/pst recovery) | 7.0 | 7.0 | 7.5 | 7.5 | 8.0 | 8.0 | 10.0 | 15.0 | ns |
| tSRW (rst/pst width) | 7.0 | 7.0 | 8.0 | 8.0 | 10.0 | 10.0 | 12.0 | 15.0 | ns |

### Clock/LE Width

| Parameter | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|-----------|----|-----|----|-----|----|-----|-----|-----|------|
| tWLS (global clk low) | 2.0 | 2.0 | 2.5 | 2.5 | 3.0 | 5.0 | 6.0 | 6.0 | ns |
| tWHS (global clk high) | 2.0 | 2.0 | 2.5 | 2.5 | 3.0 | 5.0 | 6.0 | 6.0 | ns |
| tWLA (PT clk low) | 3.0 | 3.0 | 3.5 | 3.5 | 4.0 | 5.0 | 8.0 | 9.0 | ns |
| tWHA (PT clk high) | 3.0 | 3.0 | 3.5 | 3.5 | 4.0 | 5.0 | 8.0 | 9.0 | ns |

### Maximum Frequency (MACH 4A)

| Mode | -5 | -55 | -6 | -65 | -7 | -10 | -12 | -14 | Unit |
|------|----|-----|----|-----|----|-----|-----|-----|------|
| fMAXS ext. feedback D-type | 143 | 133 | 118 | 118 | 95.2 | 87.0 | 74.1 | 60.6 | MHz |
| fMAXS int. feedback D-type | 182 | 167 | 154 | 154 | 125 | 100 | 83.3 | 74.1 | MHz |
| fMAXS no feedback | 250 | 250 | 200 | 200 | 154 | 125 | 100 | 83.3 | MHz |
| fMAXA ext. feedback D-type | 111 | 111 | 100 | 100 | 83.3 | 66.7 | 55.6 | 43.5 | MHz |
| fMAXA int. feedback D-type | 133 | 133 | 125 | 125 | 105 | 83.3 | 66.7 | 50.0 | MHz |
| fMAXA no feedback | 167 | 167 | 143 | 143 | 125 | 100 | 62.5 | 55.6 | MHz |
| fMAXI (input register) | 167 | 167 | 143 | 143 | 125 | 100 | 83.3 | 83.3 | MHz |

---

## ICC vs Frequency (from curves, Figure 21)

For M4A3-32/32 (closest to 64/32 on the chart) at VCC = 3.3V, TA = 25 C:

| Frequency | ICC High Power (approx) | ICC Low Power (approx) |
|-----------|------------------------|----------------------|
| 0 MHz | ~15 mA | ~10 mA |
| 50 MHz | ~30 mA | ~20 mA |
| 100 MHz | ~50 mA | ~30 mA |
| 200 MHz | ~75 mA | ~50 mA |

M4A3-64/32 will be somewhat higher (more macrocells active).

---

## 44-Pin TQFP Pinout (M4A3-64/32)

```
                    44 43 42 41 40 39 38 37 36 35 34
                   +--+--+--+--+--+--+--+--+--+--+--+
                   |A3 A4 A5 A6 A7 GND VCC D7 D6 D5 D4|
                   |I4 I3 I2 I1 I0 --- --- I31 I30 I29 I28|
              -----+                                      +-----
  pin 1  A2  I/O5  |                                      | I/O27  D3  pin 33
  pin 2  A1  I/O6  |                                      | I/O26  D2  pin 32
  pin 3  A0  I/O7  |                                      | I/O25  D1  pin 31
  pin 4       TDI  |          M4A3-64/32                  | I/O24  D0  pin 30
  pin 5   CLK0/I0  |          44-TQFP                     | TDO        pin 29
  pin 6       GND  |          (top view)                  | GND        pin 28
  pin 7       TCK  |                                      | CLK1/I1    pin 27
  pin 8  B0  I/O8  |                                      | TMS        pin 26
  pin 9  B1  I/O9  |                                      | I/O23  C0  pin 25
  pin 10 B2  I/O10 |                                      | I/O22  C1  pin 24
  pin 11 B3  I/O11 |                                      | I/O21  C2  pin 23
              -----+                                      +-----
                   |B4 B5 B6 B7 VCC GND C7 C6 C5 C4 C3|
                   |I12 I13 I14 I15 --- --- I16 I17 I18 I19 I20|
                   +--+--+--+--+--+--+--+--+--+--+--+
                    12 13 14 15 16 17 18 19 20 21 22
```

### Pin-to-Block Mapping

| Block | I/O Pins | Package Pins (44-TQFP) | Macrocells |
|-------|----------|----------------------|------------|
| A | I/O0 - I/O7 | 44,43,42,41,40, 1,2,3 | A0-A15 |
| B | I/O8 - I/O15 | 8,9,10,11, 12,13,14,15 | B0-B15 |
| C | I/O16 - I/O20, I/O21-I/O23 | 18,19,20,21,22, 23,24,25 | C0-C15 |
| D | I/O24 - I/O31 | 30,31,32,33, 34,35,36,37 | D0-D15 |

### Special Pins

| Pin | Function | Notes |
|-----|----------|-------|
| 4 | TDI | JTAG data in |
| 5 | CLK0/I0 | Clock 0 or general input |
| 6 | GND | Ground |
| 7 | TCK | JTAG clock |
| 16 | VCC | 3.3V supply |
| 17 | GND | Ground |
| 26 | TMS | JTAG mode select |
| 27 | CLK1/I1 | Clock 1 or general input |
| 28 | GND | Ground |
| 29 | TDO | JTAG data out |
| 38 | VCC | 3.3V supply |
| 39 | GND | Ground |

---

## Available Packages (M4A3-64/32)

| Code | Package | Pins | Available Speed Grades |
|------|---------|------|----------------------|
| JC | PLCC | 44 | -5, -55, -6, -65, -7, -10, -12 |
| VC | TQFP | 44 | -5, -55, -6, -65, -7, -10, -12 |
| VC48 | TQFP | 48 | -5, -55, -6, -65, -7, -10, -12 |

Full part number example: **M4A3-64/32-7VC** = 64 macrocells, 32 I/O, 7.5ns, 44-pin TQFP

---

## ISP Programming Registers (from BSDL)

| Register | Width | JTAG Instruction | Purpose |
|----------|-------|------------------|---------|
| ROWREG | 80 bits | PRIV003 | Row address / control |
| COLREG | 378 bits | PRIV004, PRIV007 | AND array fuse data (= 384 - 6 clk/inputs) |
| PRIVR00F | 5 bits | PRIV00F | Control register |
| BOUNDARY | 98 bits | EXTEST, SAMPLE | Boundary scan (32 I/O x 3 + 2 CLK) |
| IDCODE | 32 bits | IDCODE | `0x17486157` |

---

*Source: Lattice MACH 4 Family datasheet (1999), pages 39, 42-47, 49, 61*
