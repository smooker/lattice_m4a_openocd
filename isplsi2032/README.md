# ispLSI2032 — Lattice ispLSI 2000 Family

Available on donor PCBs in the lab.

## VOLTAGE WARNING

The ispLSI 2032 family has **multiple voltage variants**:

| Variant        | VCC      | ISP         | JTAG                   | FT2232H direct?   | IDCODE     |
|----------------|----------|-------------|------------------------|--------------------|------------|
| ispLSI 2032    | **5V**   | Hidden JTAG | **Yes**                | YES (5V tolerant)  | None (0x00000005) |
| ispLSI 2032A   | **5V**   | Hidden JTAG | **Yes**                | YES (5V tolerant)  | TBD        |
| ispLSI 2032V   | **3.3V** | IEEE 1532   | **Yes** (IR=5)         | YES                | 0x00301043 |
| ispLSI 2032VL  | **3.3V** | IEEE 1532   | **Yes** (IR=5)         | YES                | TBD        |
| ispLSI 2032E   | **5V**   | IEEE 1532   | **Yes** (IR=5)         | YES (5V tolerant)  | 0x00A4E043 |
| ispLSI 2032VE  | **3.3V** | IEEE 1532   | **Yes** (IR=5) + BScan | YES                | 0x10301043 |

**FT2232H is +5V tolerant on all I/O** — direct connection to ALL variants, no level shifter!
- "Legacy ISP" is actually JTAG with different pin names (Lattice patent US5412260A)
- All variants have JTAG capability
- For 5V chips: FT2232H outputs 3.3V HIGH → accepted as HIGH (VIH >= 2.0V)
- Hold ispEN (pin 7) LOW to enable JTAG mode

## Device Summary

| Parameter | Value |
|-----------|-------|
| Family | ispLSI 2000 |
| Macrocells | 32 (8 GLB x 4) |
| I/O pins | 32 + 2 dedicated inputs |
| Clock pins | 3 dedicated (Y0, Y1, Y2) |
| OE pins | 1 dedicated (GOE 0) |
| IR length | 5 bits (JTAG variants only) |
| JTAG | V/VL/E variants only |
| ISP | Legacy serial (2032/A) or IEEE 1532 (V/VL/E) |
| Architecture | GLB (AND/OR/XOR array) |
| Density | ~1K PLD gates |
| fMAX | 180 MHz (-180 grade) |
| Interconnect | Global Routing Pool (GRP) |
| Erase cycles | 10,000 (ispLSI) |
| Data retention | 20 years |
| Technology | E²CMOS |

## Architecture

- 8 Generic Logic Blocks (GLBs): A0..A7, 4 macrocells each
- Each GLB: 18 inputs from GRP, programmable AND/OR/XOR array
- Macrocell: combinatorial or registered output
- Global Routing Pool (GRP): full interconnect between all GLBs
- Output Routing Pool (ORP): connects GLB outputs to I/O cells
- 3 dedicated clock pins (Y0, Y1/RESET, Y2/SCLK)
- 1 global output enable (GOE 0)

## Packages

| Package | Pins | Suffix |
|---------|------|--------|
| PLCC | 44 | -xLJ44 |
| TQFP | 44 | -xLT44, -xLTN44 |
| TQFP | 48 | -xLTN48 |

## ISC Instructions (JTAG variants: V/VL/E)

From BSDL (bsdl.info), IR length = 5 bits:

| Instruction | Opcode | Description |
|-------------|--------|-------------|
| ISC_ENABLE | 10101 | Enter ISC mode |
| ISC_DISABLE | 11110 | Exit ISC mode |
| ISC_ADDRESS_SHIFT | 00001 | Load row address |
| ISC_DATA_SHIFT | 00010 | Shift fuse data |
| ISC_READ | 01010 | Read fuse row |
| ISC_ERASE | 00011 | Erase device |
| ISC_NOOP | 11001 | No operation |
| ISC_DISCHARGE | 10100 | Discharge programming voltage |
| ISC_PROGRAM_SECURITY | 01001 | Set security fuse |
| IDCODE | 10110 | Read JTAG IDCODE |

## JTAG Scan Results (plain ispLSI 2032-135LT44)

First successful JTAG communication on 2026-03-11 via FT2232H + OpenOCD.

| Test                  | Result                                       |
|-----------------------|----------------------------------------------|
| Scan chain            | 1 TAP found                                  |
| BYPASS (IR=0xFF)      | OK — 1-bit register, returns 0               |
| IDCODE (IR=0x16)      | 0x00000005 — **no standard IDCODE**          |
| IR capture value      | 0x05 (irlen 8) or 0x05 (irlen 5)            |
| ISC_ENABLE (IR=0x15)  | Accepted (returned 0x05 = previous IR capture)|
| USB stability         | Marginal — loose wires cause disconnects     |

**Conclusion**: Plain ispLSI 2032 has **hidden JTAG** that responds to scan chain
operations.  No standard IEEE 1149.1 IDCODE is present.  ISP instructions
from the V/VL/E BSDL may partially work — further probing needed.

**IR length**: Likely 5 bits (same as V/VL/E); irlen 8 works with OpenOCD
but the actual register appears to be 5 bits (IR capture = 0x05 = 0b00101,
where bits 0-1 = 01 is standard JTAG capture signature).

## JTAG Pins (V/VL/E variants)

Standard 4-wire JTAG: TCK, TDI, TDO, TMS

## Legacy ISP Pins (all variants)

| Pin | 44-TQFP | Function (ISP mode) | Function (normal) |
|-----|---------|--------------------|--------------------|
| ispEN | 7 | Enable ISP (active low) | NC |
| SDI/IN0 | 8 | Serial data in | Dedicated input |
| SDO/IN1 | 18 | Serial data out | Dedicated input |
| MODE | 30 | ISP state control | NC |
| SCLK/Y2 | 27 | Serial clock | Clock Y2 |

## TQFP44 → DIP Adapter Wiring

Generic Chinese TQFP adapter (~1 лв).  Dual-sided PCB:
- **Front (0.8mm pitch)**: TQFP 32–64 pin
- **Back (0.5mm pitch)**: TQFP up to 100 pin

**No pinout table is provided** — user must create their own mapping for each chip!
Pin 1 is **top-left** on TQFP44.

![TQFP44 adapter](media/tqfp44_adapter.jpg)

The adapter has 64 holes but only 44 are used.  Each side has a gap of 5 unused holes.
Sides 1–2: gap at end; sides 3–4: gap at start (chip centered, traces route outward).

| Chip pins | Adapter holes | Offset | Gap position     |
|-----------|---------------|--------|------------------|
|  1 – 11   |  1 – 11       | +0     | end (12–16)      |
| 12 – 22   | 17 – 27       | +5     | end (28–32)      |
| 23 – 33   | 38 – 48       | +15    | start (33–37)    |
| 34 – 44   | 54 – 64       | +20    | start (49–53)    |

### FT2232H → Adapter Wiring (8 wires)

| Chip pin | Adapter | Signal        | FT2232H          |
|----------|---------|---------------|------------------|
|  6, 28   |  6, 43  | VCC           | +5V              |
|  7       |  7      | ispEN         | GND              |
|  8       |  8      | SDI (TDI)     | ADBUS1           |
| 17, 39   | 22, 59  | GND           | GND              |
| 18       | 23      | SDO (TDO)     | ADBUS2           |
| 27       | 42      | SCLK (TCK)    | ADBUS0           |
| 29       | 44      | RESET/Y1      | ADBUS4 (nSRST)  |
| 30       | 45      | MODE (TMS)    | ADBUS3           |

## OpenOCD Quick Test (JTAG variants only)

```bash
openocd -f ../../ft2232h/ft2232h_smooker.cfg \
    -c "adapter speed 1000; transport select jtag" \
    -c "jtag newtap auto0 tap -irlen 5" \
    -c "init"
```

## Speed Grades

| Grade | fmax (MHz) | tpd (ns) |
|-------|-----------|----------|
| -180 | 180 | 5.0 |
| -150 | 154 | 5.5 |
| -135 | 137 | 7.5 |
| -110 | 111 | 10.0 |
| -80 | 84 | 15.0 |

## vs M4A3-64/32

|             | ispLSI2032          | M4A3-64/32     |
|-------------|---------------------|----------------|
| Macrocells  | 32 (8x4)           | 64 (4x16)      |
| IR length   | 5 bits              | 10 bits        |
| Blocks      | 8 GLB x 4 MC       | 4 PAL x 16 MC  |
| GLB inputs  | 18                  | 33             |
| VCC         | 5V or 3.3V (V/VL)  | 3.3V           |
| ISP         | Legacy or IEEE 1532 | IEEE 1532      |
| Fuse access | TBD                 | Fully decoded  |
| fmax        | 180 MHz             | 250 MHz        |

## TODO

- [x] **Identify exact variant**: ispLSI 2032-135LT44 (5V, 137MHz, plain 2032)
- [x] Desolder from donor PCB (Cognex TURBO ACR/M/ALRM 2.0)
- [x] Mount on TQFP44→DIP adapter
- [x] **JTAG scan** — chain works, BYPASS OK, **no standard IDCODE** (smooker wins the bet!)
- [ ] Determine actual IR length (5 or 8?)
- [ ] Probe all IR opcodes — find which ISP instructions work
- [ ] Read fuse map via ISC_READ (if security bit allows)
- [ ] Download BSDL from bsdl.info (needs CAPTCHA)
- [ ] Decode full ISC protocol (register sizes TBD)
- [ ] Determine fuse geometry
