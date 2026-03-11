# BCD 0-9 Counter for ispLSI 2032

A BCD (0-9) counter targeting the Lattice ispLSI 2032 CPLD (44-TQFP, 3.3V).
This is a minimal test design to validate the open-source programming toolchain.

## Toolchain

```
bcd10.v (Verilog)
    |
    v
  Yosys (synthesis)  -->  bcd10.blif (BLIF netlist)
    |
    v
  m4afit (fitter)    -->  output.fuse (fuse map)    [TODO]
    |
    v
  program.py          -->  ispLSI 2032 chip (via FT2232H)
```

## Architecture

The ispLSI 2032 has:
- 8 GLBs (Generic Logic Blocks), each with 4 macrocells = 32 macrocells total
- 18 GRP (Global Routing Pool) inputs per GLB
- AND/OR/XOR array per macrocell
- 102 rows x 80 bits (40 high + 40 low order) = 8160 fuse cells
- Erased state = all 1s (0x3FFFFFFFFF per half-row)
- Programmed fuse = 0 (makes AND array connection)

## BLIF Equations (from Yosys synthesis)

The BCD counter synthesizes to 4 DFFs with async reset (`$_DFF_PN0_`):

```
cnt[0]_next = NOT cnt[0]

cnt[1]_next = (cnt[0]=0, cnt[1]=1)
           OR (cnt[0]=1, cnt[1]=0, cnt[2]=1, dont_care cnt[3])
           OR (cnt[0]=1, cnt[1]=0, cnt[2]=0, cnt[3]=0)

cnt[2]_next = (cnt[1]=0, cnt[2]=1)
           OR (cnt[0]=1, cnt[1]=1, cnt[2]=0)
           OR (cnt[0]=0, cnt[1]=1, cnt[2]=1)

cnt[3]_next = (cnt[0]=0, cnt[3]=1, dont_care cnt[1], dont_care cnt[2])
           OR (cnt[1]=0, cnt[2]=1, cnt[3]=1)
           OR (cnt[0]=1, cnt[1]=1, cnt[2]=0, cnt[3]=1)
           OR (cnt[0]=1, cnt[1]=1, cnt[2]=1, cnt[3]=0)
```

## Pin Assignments

ISP pins are AVOIDED (wires stay connected for in-circuit programming):

| Pin | Function    | ISP? |
|-----|-------------|------|
| 5   | Y0 = clk    | No   |
| 3   | I/O = rst_n | No   |
| 9   | I/O = q[0]  | No   |
| 10  | I/O = q[1]  | No   |
| 11  | I/O = q[2]  | No   |
| 12  | I/O = q[3]  | No   |
| 7   | ispEN       | ISP  |
| 8   | SDI         | ISP  |
| 18  | SDO         | ISP  |
| 27  | SCLK        | ISP  |
| 29  | RESET/Y1    | ISP  |
| 30  | MODE        | ISP  |

## Fuse Map

Binary format (`.fuse`): 102 rows x 10 bytes = 1020 bytes per file.
Each row = 5 bytes HIGH order (big-endian) + 5 bytes LOW order (big-endian).

Text format (`.txt`): one line per row with hex values. Programmed rows marked with `*`.

### Fuse Map RE Strategy

The fuse map structure is not publicly documented. Strategy:
1. Program known single-product-term equations
2. Read back and diff against erased state
3. Map which fuse bits control which GLB/macrocell/product terms
4. Build fitter lookup tables from accumulated knowledge

## How to Read/Program the Chip

All commands run on the **HOST** (not chroot) — needs pyftdi + libusb:

```bash
# Unload kernel FTDI driver (conflicts with pyftdi)
sudo rmmod ftdi_sio

# Read current fuse map
python3 read_fuses.py -o dump.fuse

# Program from fuse file (erase + program + verify)
python3 program.py input.fuse

# Program without erase (if chip is already erased)
python3 program.py --no-erase input.fuse

# Program without verification
python3 program.py --no-verify input.fuse
```

## ISP Protocol

The ispLSI 2032 uses Lattice's proprietary 3-state ISP protocol (NOT IEEE 1149.1 JTAG):

```
IDLE/ID  --HH-->  SHIFT  --HH-->  EXECUTE
   ^  HL/          LX/              LX/
   +----HL----------+        +--HL--+
```

- HH (MODE=H, SDI=H) on SCLK rising edge = advance state
- HL (MODE=H, SDI=L) = go to IDLE
- LX (MODE=L) = shift data / stay in current state

### ISP Commands (5-bit, LSB first)

| Cmd   | Binary | Description            |
|-------|--------|------------------------|
| NOP   | 00000  | No operation           |
| ADDSHFT | 00001 | Address shift          |
| DATASHFT | 00010 | Data shift            |
| UBE   | 00011  | User Bulk Erase        |
| PRGMH | 00111  | Program High Order     |
| PRGML | 01000  | Program Low Order      |
| VER/LDH | 01010 | Verify/Load High     |
| VER/LDL | 01011 | Verify/Load Low      |
| FLOWTHRU | 01110 | Bypass (SDI->SDO)   |
| ERALL | 10000  | Erase All (incl. UES)  |

### Hardware Connection

FT2232H channel A in MPSSE bitbang mode:
- ADBUS0 = SCLK (-> chip pin 27)
- ADBUS1 = SDI  (-> chip pin 8)
- ADBUS2 = SDO  (-> chip pin 18, input)
- ADBUS3 = MODE (-> chip pin 30)
- ADBUS4 = nSRST (-> chip pin 29)
- ADBUS5 = ispEN (-> chip pin 7, active low)
