# ispLSI 2032 / pLSI 2032 — Specifications

Extracted from Lattice datasheet, July 1997 (15 pages).

## Variants

| Variant | VCC | ISP Method | JTAG | Notes |
|---------|-----|-----------|------|-------|
| pLSI 2032 | 5V | OTP / legacy serial | No | 100 erase cycles |
| ispLSI 2032 | 5V | Legacy serial (SDI/SDO/SCLK/MODE/ispEN) | No | 10,000 erase cycles |
| ispLSI 2032A | 5V | Enhanced ISP | Likely | Later revision |
| ispLSI 2032V | 3.3V | IEEE 1532 | Yes (IR=5) | Low voltage variant |
| ispLSI 2032VL | 3.3V | IEEE 1532 | Yes (IR=5) | VL = Very Low power? |
| ispLSI 2032E | 5V? | IEEE 1532 | Yes (IR=5) | Enhanced variant |

**FT2232H is +5V tolerant** — all variants connect directly, no level shifter needed.
- FT2232H outputs 3.3V HIGH → 5V CMOS accepts as HIGH (VIH >= 2.0V)
- FT2232H inputs tolerate 5V from chip TDO

## Architecture

- 8 Generic Logic Blocks (GLBs): A0..A7
- 4 macrocells per GLB = 32 total
- Each GLB: 18 inputs from GRP + dedicated inputs
- Programmable AND/OR/XOR array per GLB
- Macrocell: combinatorial or registered output
- Global Routing Pool (GRP): full interconnect between all GLBs
- Output Routing Pool (ORP): connects GLB outputs to I/O cells
- Input Bus: routes I/O pins to GRP
- One Megablock = 8 GLBs + 32 I/O cells + 2 ORPs

## Pin Summary

| Type | Count | Names |
|------|-------|-------|
| I/O | 32 | I/O 0..I/O 31 |
| Dedicated inputs | 2 | IN0 (SDI), IN1 (SDO) |
| Clock | 3 | Y0, Y1, Y2 (SCLK) |
| Reset | 1 | RESET/Y1 (shared with Y1 clock) |
| Global OE | 1 | GOE 0 |
| ISP control | 3 | ispEN, MODE, SCLK/Y2 |
| VCC | 2-4 | per package |
| GND | 2-4 | per package |

## Packages

### 44-Pin PLCC (suffix -xLJ)

```
               I/O27 I/O26 I/O25 I/O24 GOE0 GND I/O23 I/O22 I/O21 I/O20 I/O19
                 6     5     4     3     2    1    44    43    42    41    40
            ┌────────────────────────────────────────────────────────────────┐
  I/O 28  7 │                                                              │ 39  I/O 18
  I/O 29  8 │                                                              │ 38  I/O 17
  I/O 30  9 │                                                              │ 37  I/O 16
  I/O 31 10 │              ispLSI 2032                                     │ 36  MODE/NC
      Y0 11 │              pLSI 2032                                       │ 35  RESET/Y1
     VCC 12 │              Top View                                        │ 34  VCC
 ispEN   13 │                                                              │ 33  SCLK/Y2
 SDI/IN0 14 │                                                              │ 32  I/O 15
    I/O 0 15│                                                              │ 31  I/O 14
    I/O 1 16│                                                              │ 30  I/O 13
    I/O 2 17│                                                              │ 29  I/O 12
            └────────────────────────────────────────────────────────────────┘
                18    19    20    21    22    23    24    25    26    27    28
              I/O3  I/O4  I/O5  I/O6  I/O7  GND SDO/IN1 I/O8  I/O9 I/O10 I/O11
```

### 44-Pin TQFP (suffix -xLT44, -xLTN44)

```
              I/O27 I/O26 I/O25 I/O24 GOE0 GND I/O23 I/O22 I/O21 I/O20 I/O19
                44    43    42    41    40   39    38    37    36    35    34
            ┌────────────────────────────────────────────────────────────────┐
  I/O 28  1 │ *                                                            │ 33  I/O 18
  I/O 29  2 │                                                              │ 32  I/O 17
  I/O 30  3 │                                                              │ 31  I/O 16
  I/O 31  4 │              ispLSI 2032                                     │ 30  MODE/NC
      Y0  5 │              pLSI 2032                                       │ 29  RESET/Y1
     VCC  6 │              Top View                                        │ 28  VCC
 ispEN/NC 7 │                                                              │ 27  SCLK/Y2
 SDI/IN0  8 │                                                              │ 26  I/O 15
    I/O 0  9│                                                              │ 25  I/O 14
    I/O 1 10│                                                              │ 24  I/O 13
    I/O 2 11│                                                              │ 23  I/O 12
            └────────────────────────────────────────────────────────────────┘
                12    13    14    15    16    17    18    19    20    21    22
              I/O3  I/O4  I/O5  I/O6  I/O7  GND SDO/IN1 I/O8  I/O9 I/O10 I/O11
```

### 48-Pin TQFP (suffix -xLTN48)

```
              NC  I/O27 I/O26 I/O25 I/O24 GOE0 GND I/O23 I/O22 I/O21 I/O20 I/O19
              48    47    46    45    44    43   42    41    40    39    38    37
            ┌────────────────────────────────────────────────────────────────────┐
  I/O 28  1 │ *                                                                │ 36  NC
  I/O 29  2 │                                                                  │ 35  I/O 18
  I/O 30  3 │                                                                  │ 34  I/O 17
  I/O 31  4 │              ispLSI 2032                                         │ 33  I/O 16
      Y0  5 │              Top View                                            │ 32  MODE
     VCC  6 │                                                                  │ 31  RESET/Y1
   ispEN  7 │                                                                  │ 30  VCC
 SDI/IN0  8 │                                                                  │ 29  SCLK/Y2
    I/O 0  9│                                                                  │ 28  I/O 15
    I/O 1 10│                                                                  │ 27  I/O 14
    I/O 2 11│                                                                  │ 26  I/O 13
       NC 12│                                                                  │ 25  I/O 12
            └────────────────────────────────────────────────────────────────────┘
                13    14    15    16    17    18    19    20    21    22    23    24
              I/O3  I/O4  I/O5  I/O6  I/O7  GND SDO/IN1 I/O8  I/O9 I/O10 I/O11  NC
```

## I/O to GLB Mapping

From pin table (44-TQFP):

| GLB | I/O Pins | TQFP Pins |
|-----|----------|-----------|
| A0 | I/O 0-3 | 9, 10, 11, 12 |
| A1 | I/O 4-7 | 13, 14, 15, 16 |
| A2 | I/O 8-11 | 19, 20, 21, 22 |
| A3 | I/O 12-15 | 23, 24, 25, 26 |
| A4 | I/O 16-19 | 31, 32, 33, 34 (approx) |
| A5 | I/O 20-23 | 35, 36, 37, 38 |
| A6 | I/O 24-27 | 41, 42, 43, 44 |
| A7 | I/O 28-31 | 1, 2, 3, 4 |

## DC Recommended Operating Conditions (5V variants)

| Parameter | Min | Max | Units |
|-----------|-----|-----|-------|
| VCC (Commercial, 0-70C) | 4.75 | 5.25 | V |
| VCC (Industrial, -40-85C) | 4.5 | 5.5 | V |
| VIL (Input Low) | 0 | 0.8 | V |
| VIH (Input High) | 2.0 | VCC+1 | V |

## DC Electrical Characteristics

| Parameter | Condition | Min | Max | Units |
|-----------|-----------|-----|-----|-------|
| VOL (Output Low) | IOL=8mA | - | 0.4 | V |
| VOH (Output High) | IOH=-4mA | 2.4 | - | V |
| IIL (Input Leakage Low) | | - | -10 | uA |
| IIH (Input Leakage High) | | - | 10 | uA |
| IOS (Short Circuit) | VCC=5V | - | -200 | mA |
| ICC (Supply Current) | Comm -180/-150 | -180..60 | - | mA |
| ICC (Supply Current) | Others | -..40 | - | mA |

## Capacitance (VCC=5V, 25C, 1MHz)

| Parameter | Typical | Units |
|-----------|---------|-------|
| Dedicated Input | 6 | pF |
| I/O | 7 | pF |
| Clock | 10 | pF |

## Data Retention

| Parameter | Value |
|-----------|-------|
| Data Retention | 20 years minimum |
| ispLSI Erase/Reprogram | 10,000 cycles |
| pLSI Erase/Reprogram | 100 cycles |

## Speed Grades

| Speed | fmax (MHz) | tpd1 (ns) | tpd2 (ns) |
|-------|-----------|-----------|-----------|
| -180 | 180 | 5.0 | 7.5 |
| -150 | 154 | 5.5 | 8.0 |
| -135 | 137 | 7.5 | 10.0 |
| -110 | 111 | 10.0 | 13.0 |
| -80 | 84 | 15.0 | 18.5 |

tpd1 = 4PT bypass, ORP bypass (fastest path)
tpd2 = Full data propagation delay

## External Timing (fastest: -180 grade)

| Parameter | Description | Max (ns) |
|-----------|-------------|----------|
| tpd1 | Data Prop, 4PT Bypass, ORP Bypass | 5.0 |
| tpd2 | Data Prop Delay | 7.5 |
| tco1 | GLB Reg Clk to Output, ORP Bypass | 4.0 |
| tsu1 | GLB Setup before Clk, 4PT Bypass | 3.0 |
| th1 | GLB Hold after Clk, 4PT Bypass | 0.0 |
| tsu2 | GLB Setup before Clk | 4.0 |
| tco2 | GLB Clk to Output | 4.5 |
| tr1 | Ext Reset to Output | 7.0 |
| trw1 | Ext Reset Pulse Duration | 4.0 |
| tptoeen | Input to Output Enable | 10.0 |
| tptoedis | Input to Output Disable | 10.0 |
| tgoeen | Global OE Enable | 5.0 |
| tgoedis | Global OE Disable | 5.0 |
| twh | Ext Sync Clk High | 2.5 min |
| twl | Ext Sync Clk Low | 2.5 min |

## Internal Timing (-180 grade, reference only)

| Parameter | Description | Max (ns) |
|-----------|-------------|----------|
| tio | Input Buffer Delay | 0.6 |
| tdin | Dedicated Input Delay | 1.1 |
| tgrp | GRP Delay | 0.7 |
| t4ptbpc | 4PT Bypass Combinatorial | 2.3 |
| t4ptbpr | 4PT Bypass Registered | 3.1 |
| t1ptxor | 1 PT XOR Path | 3.6 |
| t20ptxor | 20 PT XOR Path | 4.1 |
| torp | ORP Delay | 0.7 |
| torpbp | ORP Bypass Delay | 0.2 |
| tob | Output Buffer Delay | 1.2 |
| tgy0 | Y0 to GLB Clock Line | 1.9-2.1 |
| tgy1/2 | Y1/Y2 to GLB Clock Line | 1.9-2.1 |
| tgr | Global Reset to GLB | 4.1 |

## Power Consumption

ICC estimate formula (typical, VCC=5V, 25C):
- For -150/-180: ICC(mA) = 30 + (PTs x 0.46) + (nets x Max_freq x 0.012)
- For -80/-110/-135: ICC(mA) = 21 + (PTs x 0.30) + (nets x Max_freq x 0.012)

## ISP Pins (Legacy Serial, original ispLSI2032)

| Pin | Function |
|-----|----------|
| ispEN | ISP enable (active low) — when low, enters ISP mode |
| SDI/IN0 | Serial data in (ISP) / dedicated input (normal) |
| SDO/IN1 | Serial data out (ISP) / dedicated input (normal) |
| MODE/NC | ISP state machine control |
| SCLK/Y2 | Serial clock (ISP) / dedicated clock Y2 (normal) |

When ispEN is high (normal mode): SDI→IN0, SDO→IN1, SCLK→Y2, MODE→NC

## Part Number Decoding

```
(is)pLSI 2032 - XXX  X  XXX  X
                 │    │   │   └── Grade: blank=Commercial, I=Industrial
                 │    │   └────── Package: J=PLCC, T=TQFP, T44=TQFP44, T48=TQFP48
                 │    └────────── Power: L=Low
                 └─────────────── Speed: 180/150/135/110/80
```

## vs M4A3-64/32 Comparison

| Parameter | ispLSI 2032 | M4A3-64/32 |
|-----------|-------------|------------|
| Macrocells | 32 (8x4) | 64 (4x16) |
| Logic blocks | 8 GLBs | 4 PAL blocks |
| Block structure | 18-in AND/OR/XOR | 33-in AND/OR |
| I/O pins | 32 + 2 ded. | 32 |
| Clocks | 3 dedicated (Y0/Y1/Y2) | 2 (CLK0/CLK1) |
| VCC | 5V (original) / 3.3V (V/VL) | 3.3V |
| IR length | 5 bits | 10 bits |
| ISP | Legacy serial or IEEE 1532 | IEEE 1532 |
| Interconnect | GRP (global) | CSM+ISM+OSM |
| Technology | E2CMOS | E2CMOS |
| Erase cycles | 10,000 | 10,000 |
| fmax | up to 180 MHz | up to 250 MHz |
