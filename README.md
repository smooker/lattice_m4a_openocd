# Lattice ispMACH 4000 (M4A) — OpenOCD JTAG

Programming Lattice M4A3-64/32 CPLD via OpenOCD and FTDI FT2232H.

## Hardware

- **CPLD**: Lattice ispMACH M4A3-64/32, 44-pin TQFP, 3.3V
- **JTAG ID**: `0x17486157`, IR length: 10 bits
- **Programmer**: FTDI FT2232H, VID/PID `0403:6010`, **+5V tolerant I/O**

### JTAG Wiring (FT2232H → CPLD)

| FT2232H Signal | JTAG Function |
|----------------|---------------|
| ADBUS0 (AD0) | TCK |
| ADBUS1 (AD1) | TDI |
| ADBUS2 (AD2) | TDO |
| ADBUS3 (AD3) | TMS |
| ACBUS0 (AC0) | nTRST |
| ACBUS1 (AC1) | nSRST |

> FT2232H I/O is +5V tolerant — works with both 3.3V and 5V targets directly, no level shifter needed.

## Files

| File | Description |
|------|-------------|
| `openocd/go.sh` | JTAG scan — verifies connectivity and reads IDCODE |
| `ft2232h/ft2232h_smooker.cfg` | OpenOCD adapter config for FT2232H |
| `M4A3_64_32_XXVC.bsdl` | BSDL model (3.3V, IEEE 1532 ISC support) |
| `BSDLM4-643244PinTQFP.BSM` | Boundary Scan Model (5V, Vantis legacy) |
| `README.txt` | Original notes and links |

## Documentation

| File | Description |
|------|-------------|
| [`docs/M4A3_architecture.md`](docs/M4A3_architecture.md) | Architecture deep dive, fuse map analysis, reverse engineering strategy |
| [`docs/M4A3-64_32_specs.md`](docs/M4A3-64_32_specs.md) | DC/timing specs, pinout, max frequency tables |
| [`docs/M4A3_ISC_protocol.md`](docs/M4A3_ISC_protocol.md) | IEEE 1532 ISC protocol — read/write/erase fuse map via JTAG |
| [`docs/M4A5-64_32-6JC.pdf`](docs/M4A5-64_32-6JC.pdf) | MACH 4 Family datasheet (62 pages) |
| [`docs/session_2026_03_10.md`](docs/session_2026_03_10.md) | Session log — initial setup and fuse map discovery |

## Usage

### JTAG Scan (verify connection)

```bash
cd openocd && ./go.sh
```

Expected output should show JTAG tap with ID `0x17486157`.

### Program via SVF

```bash
openocd -f ./ft2232h/ft2232h_smooker.cfg \
    -c "adapter speed 2000; transport select jtag" \
    -c "jtag newtap auto0 tap -irlen 10 -expected-id 0x17486157" \
    -c "init" \
    -c "svf your_design.svf" \
    -c "shutdown"
```

Generate the SVF file from ispLEVER Classic (JEDEC → SVF export).

## Software

- **OpenOCD** — JTAG interface ([openocd.org](https://openocd.org))
- **ispLEVER Classic** — Lattice IDE for M4A synthesis + fitting ([archive.org mirror](https://archive.org/download/ispLEVER_Classic_Base_1_8))
- **BSDL source** — [bsdl.info](https://bsdl.info/details.htm?sid=dbb7399451e3e14088ca59b002289d77)

## Fuse Map Reverse Engineering

The long-term goal is to build an open-source fitter for M4A3, eliminating the
need for Windows/ispLEVER. Key discovery from BSDL analysis:

- `COLREG[378]` — AND array fuse register, **378 = 384 − 6 clock/input pins**
- `ROWREG[80]` — row address/control register
- Strategy: generate probe JEDEC files via ispLEVER, diff to map fuse positions

See [`docs/M4A3_architecture.md`](docs/M4A3_architecture.md) for full analysis.

## Notes

- The M4A3 is EEPROM-based — retains programming without external config memory.
- BSDL boundary scan works regardless of programmed pattern — no special ISC setup needed for pin testing.
- The FT2232H has two channels; this config uses channel A (ADBUS/ACBUS).
