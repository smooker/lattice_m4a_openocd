# FT2232H JTAG Adapter — EYEWINK Board V2

AliExpress "FT2232HL Board" by popctrl@163.com (EYEWINK brand).

## Key Specs

- **Chip**: FTDI FT2232HL (dual-channel USB Hi-Speed)
- **VID/PID**: 0x0403:0x6010
- **I/O voltage**: +3.3V output, **+5V tolerant inputs**
- **Buffers**: 2x 74HC573 (8-bit transparent latch) on JTAG output
- **Connectors**: USB-B, 20-pin ARM JTAG (CN4), pin headers (ADBUS/ACBUS/BDBUS/BCBUS)
- **Power**: J1/J2 jumpers for 3.3V/5V target power select
- **Extras**: 4 LEDs, EEPROM (93C46), 12MHz crystal

## JTAG Connector (CN4, 20-pin ARM standard)

| Pin | Signal |
|-----|--------|
| 3 | TRST |
| 5 | TDI |
| 7 | TMS / SWIO |
| 9 | TCK / SWCK |
| 11 | RTCK |
| 13 | TDO |
| 15 | RESET |
| 17 | DBGRQ |

## Pin Headers (bottom edge)

```
GND RST  0 1 2 3 4 5 6 7  0 1 2 3 4 5 6 7
          ---- ADBUS ----  ---- ACBUS ----
```

Channel A (ADBUS/ACBUS) = MPSSE capable (JTAG/SPI/I2C)
Channel B (BDBUS/BCBUS) = UART or bitbang only

## 5V Tolerance

FT2232H datasheet states: "+1.8V (chip core) and +3.3V I/O interfacing (+5V Tolerant)"
- Output HIGH = 3.3V → accepted by 5V CMOS (VIH >= 2.0V)
- Input tolerates 5V → safe for 5V target TDO
- 74HC573 buffers add ESD protection but are NOT level shifters
- **Direct connection to both 3.3V and 5V targets — no level shifter needed**

## Source

- [AliExpress listing](https://www.aliexpress.com/item/32975940318.html)
- Photos: `ft2232h_board_{1,2,3}.jpg`

## OpenOCD Config

`ft2232h_smooker.cfg` — adapter driver config for this board.
