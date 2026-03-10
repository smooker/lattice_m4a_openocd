# ispLSI2032 — Lattice ispLSI 2000 Family

Available on donor PCBs in the lab.

## VOLTAGE WARNING

The ispLSI 2032 family has **multiple voltage variants**:

| Variant | VCC | ISP | JTAG | UM232H compatible? |
|---------|-----|-----|------|--------------------|
| ispLSI 2032 | **5V** | Legacy serial | **No** | NO — needs 5V |
| ispLSI 2032A | **5V** | Legacy serial | **No** | NO — needs 5V |
| ispLSI 2032V | **3.3V** | IEEE 1532 | **Yes** (IR=5) | YES |
| ispLSI 2032VL | **3.3V** | IEEE 1532 | **Yes** (IR=5) | YES |
| ispLSI 2032E | **5V** | IEEE 1532 | **Yes** (IR=5) | NO — needs 5V |

**CHECK THE MARKING ON THE CHIP before connecting!**
- Only V/VL variants work at 3.3V with our UM232H FTDI adapter
- Original 2032/2032A have NO JTAG — only legacy serial ISP
- 2032E has JTAG but needs 5V level shifter

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

IDCODE: To be determined from device scan (not yet available).

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

## OpenOCD Quick Test (JTAG variants only)

```bash
openocd -f ../openocd/um232h_smooker_6010.cfg \
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

| | ispLSI2032 | M4A3-64/32 |
|--|-----------|------------|
| Macrocells | 32 (8x4) | 64 (4x16) |
| IR length | 5 bits | 10 bits |
| Blocks | 8 GLB x 4 MC | 4 PAL x 16 MC |
| GLB inputs | 18 | 33 |
| VCC | 5V or 3.3V (V/VL) | 3.3V |
| ISP | Legacy or IEEE 1532 | IEEE 1532 |
| Fuse access | TBD | Fully decoded |
| fmax | 180 MHz | 250 MHz |

## TODO

- [ ] **Identify exact variant** on donor PCBs (read chip marking!)
- [ ] Desolder from donor PCB
- [ ] JTAG scan to get IDCODE (if V/VL/E variant)
- [ ] Download BSDL from bsdl.info (needs CAPTCHA)
- [ ] Decode full ISC protocol (register sizes TBD)
- [ ] Determine fuse geometry
- [ ] If 5V variant: build 5V↔3.3V level shifter for FTDI
