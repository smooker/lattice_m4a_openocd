#!/bin/bash
openocd --debug=2 \
    -f ./um232h_smooker_6010.cfg \
    -c "adapter speed 1000; transport select jtag; jtag newtap auto0 tap -irlen 5; "
