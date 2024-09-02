module tlfsm2
#(
    parameter T_WIDTH = 8,
    parameter NS_TIME = 8'd9 - 1'b1,
    parameter EW_TIME = 8'd6 - 1'b1,
    parameter Y_TIME = 8'd3 - 1'b1
) (
    output wire [2:0] o_state,
    input wire i_clk,
    input wire i_rst_n
);
    `define START   3'b111      // init state, all red
    `define NS      3'b011      // north/south green
    `define NY      3'b010      // north/south yellow
    `define EW      3'b000      // east/west green
    `define EY      3'b001      // east/west yellow

    wire evt_trigger;
    reg counter_rst_n;
    wire counter_desc;
    reg [T_WIDTH-1:0] counter_setup;

    cntclk2 #(.WIDTH(T_WIDTH)) inner_counter(
        .o_clk(),
        .o_match(evt_trigger),
        .o_value(),
        .i_clk(i_clk),
        .i_rst_n(counter_rst_n),
        .i_desc(counter_desc),
        .i_setup(counter_setup)
    );

    assign counter_desc = 1'b0;

    reg [2:0] state;
    reg [2:0] next_state;

    assign o_state = state;

    always @(posedge i_clk, negedge i_rst_n) begin
        if (!i_rst_n) begin
            state <= #1 `START;
            counter_rst_n <= #1 1'b0;
        end else begin
            counter_rst_n <= #1 1'b1;
            state <= #1 next_state;
        end
    end

    always @* begin
        if (!counter_rst_n) begin
            next_state = #1 `START;
            counter_setup = #1 Y_TIME;
        end else begin
            next_state = #1 state;
            case (state)
                `START: begin
                    if (evt_trigger) next_state = #1 `NS;
                    counter_setup = #1 Y_TIME;
                end
                `NS: begin
                    if (evt_trigger) next_state = #1 `NY;
                    counter_setup = #1 NS_TIME;
                end
                `NY: begin
                    if (evt_trigger) next_state = #1 `EW;
                    counter_setup = #1 Y_TIME;
                end
                `EW: begin
                    if (evt_trigger) next_state = #1 `EY;
                    counter_setup = #1 EW_TIME;
                end
                `EY: begin
                    if (evt_trigger) next_state = #1 `NS;
                    counter_setup = #1 Y_TIME;
                end
                default: begin
                    if (evt_trigger) next_state = #1 `START;
                    counter_setup = #1 Y_TIME;
                end
            endcase
        end
    end

endmodule
