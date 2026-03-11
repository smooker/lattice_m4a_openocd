// BCD counter 0-9 for ispLSI2032V (44-TQFP)
// 4 macrocells (registered), 1 GLB
// Clk: Y0 (pin 5), Reset: active low (pin 29)
// Output: I/O 0-3 (pins 9,10,11,12)
module bcd10 (
    input  wire       clk,    // Y0 — pin 5
    input  wire       rst_n,  // RESET — pin 29 (active low)
    output wire [3:0] q       // I/O 0-3 — pins 9,10,11,12
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
