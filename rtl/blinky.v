// blinky.v — First test design for M4A3-64/32 (44-pin TQFP)
//
// Uses CLK0/I0 (pin 5) as clock input.
// Directly tests combinatorial logic + registered counter.
//
// Pinout (active outputs — accent on Block A and B for easy probing):
//   CLK0/I0  pin 5   — clock input (external oscillator or manual toggle)
//   I/O5     pin 1   — blink output (counter MSB, slowest toggle)
//   I/O6     pin 2   — counter bit 1
//   I/O7     pin 3   — counter bit 0 (fastest toggle)
//   I/O8     pin 8   — AND of two inputs (combinatorial test)
//   I/O9     pin 9   — OR of two inputs
//   I/O10    pin 10  — XOR of two inputs
//   I/O11    pin 11  — NOT of input (inverter)
//   I/O23    pin 25  — input A
//   I/O22    pin 24  — input B
//
// With a slow clock (button/1Hz), you can see the counter on pins 1-3.
// Tie pins 24,25 high/low to test combinatorial gates on pins 8-11.

module blinky (
    input  wire clk,      // CLK0/I0 — pin 5
    input  wire in_a,     // I/O23   — pin 25
    input  wire in_b,     // I/O22   — pin 24

    output wire blink,    // I/O5    — pin 1  (counter[2])
    output wire cnt1,     // I/O6    — pin 2  (counter[1])
    output wire cnt0,     // I/O7    — pin 3  (counter[0])

    output wire and_out,  // I/O8    — pin 8
    output wire or_out,   // I/O9    — pin 9
    output wire xor_out,  // I/O10   — pin 10
    output wire not_out   // I/O11   — pin 11
);

    // --- Registered: 3-bit counter ---
    // M4A3 macrocells have async reset via product term.
    // Power-on reset: in_b doubles as active-low reset (active during test).
    // For normal operation, tie in_b high and it just counts.
    reg [2:0] counter;

    always @(posedge clk or negedge in_b) begin
        if (!in_b)
            counter <= 3'd0;
        else
            counter <= counter + 3'd1;
    end

    assign blink = counter[2];
    assign cnt1  = counter[1];
    assign cnt0  = counter[0];

    // --- Combinatorial: basic gates ---
    assign and_out = in_a & in_b;
    assign or_out  = in_a | in_b;
    assign xor_out = in_a ^ in_b;
    assign not_out = ~in_a;

endmodule
