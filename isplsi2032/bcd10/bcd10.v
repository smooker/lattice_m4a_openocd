// BCD counter 0-9 for ispLSI 2032 (44-TQFP)
// 4 macrocells (registered), 1 GLB
// Clk: Y0 (pin 5)
// Reset: I/O pin 3 (Block A) — active low
// Output: q[3:0] on pins 9,10,11,12 (Block B)
//
// ISP pins AVOIDED (wires stay connected for programming):
//   pin 7 (ispEN), pin 8 (SDI), pin 18 (SDO),
//   pin 27 (SCLK), pin 29 (RESET/Y1), pin 30 (MODE)
module bcd10 (
    input  wire       clk,    // Y0 — pin 5
    input  wire       rst_n,  // I/O — pin 3 (active low)
    output wire [3:0] q       // I/O — pins 9,10,11,12
);
    reg [3:0] cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            cnt <= 4'd0;
        else if (cnt == 4'd9)
            cnt <= 4'd0;
        else
            cnt <= cnt + 4'd1;
    end

    assign q = cnt;
endmodule
