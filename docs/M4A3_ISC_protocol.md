# M4A3-64/32 — IEEE 1532 ISC Protocol Analysis

Extracted from `M4A3_64_32_XXVC.bsdl` (Lattice, 2001).
This file documents the complete In-System Configuration protocol
for reading, writing, erasing, and verifying the M4A3-64/32 fuse map.

---

## ISC Registers

| Register | Width | Instruction | Opcode (10-bit) | Direction |
|----------|-------|-------------|-----------------|-----------|
| ISC_ADDRESS | 80 bits | ISC_ADDRESS_SHIFT | 0000000011 | write |
| ISC_DATA | 378 bits | ISC_DATA_SHIFT | 0000000100 | write |
| ISC_RDATA | 378 bits | ISC_READ | 0000000111 | read |
| ISC_CONFIG | 5 bits | ISC_ENABLE | 0000001111 | write |
| ISC_DEFAULT | 1 bit | ISC_PROGRAM | 0000000110 | - |
| ISC_DEFAULT | 1 bit | ISC_ERASE | 0000000101 | - |
| ISC_DEFAULT | 1 bit | ISC_DISABLE | 1111111111 | - |

---

## Fuse Map Geometry

```
Main AND array:   80 rows x 378 bits = 30,240 fuses
Config row:        1 row  x 378 bits =    378 fuses (macrocell config)
                                       --------
Total:                                  30,618 programmable bits
```

### Row Addressing

The address register is 80 bits wide with a **walking-1** pattern:

```
Row  0: 80000000000000000000  (MSB = bit 79)
Row  1: 40000000000000000000
Row  2: 20000000000000000000
...
Row 79: 00000000000000000001  (LSB = bit 0)
```

After all 80 rows, the config row is accessed by switching ISC_ENABLE
from mode 8 to mode 9 (`ISC_ENABLE 5:9`).

### Column Data (378 bits)

Each row contains 378 fuse bits = **384 - 6**:
- 384 = total logical AND array columns
- 6 = dedicated clock/input pins that bypass the AND array

---

## ISC Flows (from BSDL ISC_FLOW attribute)

### flow_enable — Enter ISC Mode

```
ISC_ENABLE 5:0x08    WAIT TCK 3
```

Config register value `0x08` = binary `01000` enables ISC mode.

### flow_erase — Bulk Erase

```
ISC_ERASE            WAIT TCK 3, 100ms
```

Single command, 100ms erase pulse. Sets all fuses to erased state.

### flow_program(array) — Write Fuse Map

```
addr = 0x80000000000000000000    (80 bits, walking-1 start)

repeat 80 times:
    ISC_DATA_SHIFT 378:<row_data>    WAIT TCK 1
    ISC_PROGRAM                      WAIT TCK 3, 50ms
    ISC_ADDRESS_SHIFT 80:addr>>1     WAIT TCK 1

-- Config row (macrocell configuration):
ISC_ADDRESS_SHIFT 80:0               WAIT TCK 1
ISC_ENABLE 5:0x09                    WAIT TCK 3
ISC_DATA_SHIFT 378:<config_data>     WAIT TCK 1
ISC_PROGRAM                          WAIT TCK 3, 50ms
ISC_ENABLE 5:0x08                    WAIT TCK 3
```

**Key: 80 data rows + 1 config row = 81 program cycles total.**
Programming time per row: 50ms. Total: ~4 seconds.

### flow_verify(array_tdo) — Read/Verify Fuse Map

```
addr   = 0x80000000000000000000
adsel  = 0x20000000...0000        (378 bits, address select mask)

repeat for each of ~80 rows:
    ISC_DATA_SHIFT 378:adsel     WAIT TCK 1
    ISC_READ                     WAIT TCK 3, 2ms  -> 378 bits out (with CRC)
    ISC_ADDRESS_SHIFT 80:addr>>1 WAIT TCK 1

-- Config row:
ISC_ADDRESS_SHIFT 80:0           WAIT TCK 1
ISC_ENABLE 5:0x09                WAIT TCK 3
ISC_DATA_SHIFT 378:adsel         WAIT TCK 1
ISC_READ                         WAIT TCK 3, 2ms  -> 378 bits out (with CRC)
ISC_ENABLE 5:0x08                WAIT TCK 3
```

Read time per row: 2ms. Total dump: ~200ms.

### flow_erase_program — Erase + Program with Config Patterns

This flow combines erase with programming of special EEPROM conditioning
patterns. The patterns reveal internal structure:

```
Main erase pattern (66 rows):
  3FFDFFBFF7FEFFDFFBFF7FEFFF7FEFFDFFBFF7FEFFDFFBFF...

Post-erase conditioning patterns:
  epgm1 = 084108210420841082104202104208410821042084108000...
  epgm2 = 084108210420841082104202104208410821042084108202...

Config row pattern:
  200200400801002004008018008010020040080100200401001002...
```

These are NOT random — they have repeating structure that maps to the
AND array's physical layout of product terms and input columns.

### flow_disable — Exit ISC Mode

```
ISC_ENABLE 5:0x0C    WAIT TCK 3
ISC_DISABLE          WAIT TCK 3
```

---

## OpenOCD Implementation Notes

To read the fuse map via OpenOCD, use `irscan` and `drscan`:

```tcl
# Enter ISC mode
irscan auto0.tap 0x00F    ;# ISC_ENABLE
drscan auto0.tap 5 0x08
runtest 3

# Read row 0
irscan auto0.tap 0x003    ;# ISC_ADDRESS_SHIFT
drscan auto0.tap 80 0x80000000000000000000
runtest 1

irscan auto0.tap 0x004    ;# ISC_DATA_SHIFT
drscan auto0.tap 378 0x2000...0000
runtest 1

irscan auto0.tap 0x007    ;# ISC_READ
set row0 [drscan auto0.tap 378 0x0]
runtest 3
# wait 2ms
after 2

# row0 now contains 378 fuse bits!
echo "Row 0: $row0"

# Next row: shift address right
# ... repeat for all 80 rows ...

# Exit ISC
irscan auto0.tap 0x00F    ;# ISC_ENABLE
drscan auto0.tap 5 0x0C
runtest 3
irscan auto0.tap 0x3FF    ;# ISC_DISABLE
runtest 3
```

### Erase Pattern Analysis

The conditioning patterns have a repeating unit of ~9 hex chars:

```
epgm1: 0841082104208410821042 | 0210420841082104208410 | 800...
epgm2: 0841082104208410821042 | 0210420841082104208410 | 820...
                                                          ^^^
                                         difference is only here
```

In binary, `084108210420` = `000010000100000100001000001000010000010000100000`

This is a regular pattern with a 1-bit every ~6 positions — likely maps to
one fuse per macrocell or one fuse per product term in the physical layout.

---

## Reverse Engineering Workflow

### Phase 1: Read (needs only FTDI + CPLD + OpenOCD)

1. Read blank chip -> all fuses (should be all-1s for EEPROM)
2. Record as baseline

### Phase 2: Program + Read (needs ispLEVER for SVF generation)

3. Create minimal probe design in Verilog
4. Synthesize with ispLEVER -> JEDEC -> SVF
5. Program chip via OpenOCD SVF player
6. Read back fuse map
7. Diff against blank -> identify changed fuses

### Phase 3: Map (analysis, no hardware needed)

8. Correlate changed fuses with known design features
9. Repeat with variations (move output pin, change gate type, etc.)
10. Build fuse map database

### Phase 4: Open-Source Fitter

11. Write tool: Verilog netlist -> fuse map -> JEDEC/SVF
12. No more ispLEVER needed!

---

## Key Constants

| Constant | Value | Notes |
|----------|-------|-------|
| JTAG ID | 0x17486157 | ID code mask: 0x0FFFFFFF |
| IR length | 10 bits | |
| Address register | 80 bits | Walking-1, MSB first |
| Data register | 378 bits | = 384 - 6 |
| Config register | 5 bits | Mode 8=normal ISC, 9=config row |
| Boundary scan | 98 bits | 32 I/O x 3 + 2 CLK |
| Blank USERCODE | 0xFFFFFFFF | All ones |
| Main array rows | 80 | |
| Config rows | 1 | Accessed via ISC_ENABLE mode 9 |
| Program pulse | 50 ms | Per row |
| Erase pulse | 100 ms | Bulk |
| Read delay | 2 ms | Per row |

---

*Source: M4A3_64_32_XXVC.bsdl, IEEE 1532-2001 ISC extensions*
*Analysis date: 2026-03-10*
