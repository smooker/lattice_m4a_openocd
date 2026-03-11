#!/bin/bash
# Simple IR probe: start OpenOCD, send commands, capture output
CFG="../../ft2232h/ft2232h_smooker.cfg"

for IRLEN in 5 8; do
    echo "=== irlen=$IRLEN ==="

    openocd -f "$CFG" \
        -c "ftdi layout_signal nSRST -data 0x0010 -oe 0x0010" \
        -c "adapter speed 1000; transport select jtag" \
        -c "jtag newtap auto0 tap -irlen $IRLEN -expected-id 0 -ircapture 0x01 -irmask 0x01" \
        -c "init" \
        -l /tmp/ocd.log 2>/dev/null &
    OCD_PID=$!

    # Wait for port
    sleep 2

    # Build all commands into one file
    CMDS="/tmp/ocd_cmds.txt"
    > "$CMDS"

    MAX=$((1 << IRLEN))
    if [ $MAX -gt 256 ]; then MAX=256; fi

    for opcode in $(seq 0 $((MAX - 1))); do
        hex=$(printf "0x%02X" $opcode)
        echo "irscan auto0.tap $hex" >> "$CMDS"
        echo "drscan auto0.tap 16 0xCAFE" >> "$CMDS"
    done
    echo "shutdown" >> "$CMDS"

    # Send via bash TCP
    exec 3<>/dev/tcp/localhost/4444
    while IFS= read -r line; do
        echo "$line" >&3
        sleep 0.01
    done < "$CMDS"
    sleep 2
    cat <&3 > /tmp/ocd_out_${IRLEN}.txt
    exec 3>&-

    wait $OCD_PID 2>/dev/null

    # Extract just drscan results
    grep -oP '[0-9a-f]{4}$' /tmp/ocd_out_${IRLEN}.txt | sort | uniq -c | sort -rn
    echo ""
    sleep 1
done
