#!/bin/bash
openocd --debug=2 \
    -f ../../ft2232h/ft2232h_smooker.cfg \
    -c "adapter speed 100; transport select jtag; jtag newtap auto0 tap -irlen 5; "
