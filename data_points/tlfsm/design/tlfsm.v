/*
 * Traffic Light FSM
 */
module tlfsm
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
    `define START   3'b111
    `define NS      3'b011
    `define NY      3'b010
    `define EW      3'b000
    `define EY      3'b001

    wire evt_trigger;
    wire [T_WIDTH-1:0] counter_value;
    reg [T_WIDTH-1:0] counter_loader;
    wire counter_rst_n;
    reg loade;
    reg init;

    cntclk #(.WIDTH(T_WIDTH)) inner_counter(
        .o_clk(),
        .o_zero(evt_trigger),
        .io_value(counter_value),
        .i_clk(i_clk),
        .i_rst_n(counter_rst_n),
        .i_load(loade)
    );

    assign counter_value = loade ? counter_loader : { T_WIDTH{1'bz} };
    assign counter_rst_n = 1'b1;

    reg [2:0] state;
    reg [2:0] next_state;

    assign o_state = state;

    always @(posedge i_clk, negedge i_rst_n) begin
        if (!i_rst_n) begin
            state <= #1 `START;
            init <= #1 1'b1;
        end else begin
            state <= #1 next_state;
            init <= #1 1'b0;
        end
    end

    always @* begin
        if (init) begin
            next_state = #1 `START;
            counter_loader = #1 Y_TIME;
            loade = #1 1'b1;
        end else begin
            if (evt_trigger) begin
                casez (state)
                    `START: begin
                        next_state = #1 `NS;
                        counter_loader = #1 NS_TIME;
                        loade = #1 1'b1;
                    end
                    `NS: begin
                        next_state = #1 `NY;
                        counter_loader = #1 Y_TIME;
                        loade = #1 1'b1;
                    end
                    `NY: begin
                        next_state = #1 `EW;
                        counter_loader = #1 EW_TIME;
                        loade = #1 1'b1;
                    end
                    `EW: begin
                        next_state = #1 `EY;
                        counter_loader = #1 Y_TIME;
                        loade = #1 1'b1;
                    end
                    `EY: begin
                        next_state = #1 `NS;
                        counter_loader = #1 NS_TIME;
                        loade = #1 1'b1;
                    end
                    default: begin
                        next_state = #1 `START;
                        counter_loader = #1 Y_TIME;
                        loade = #1 1'b1;
                    end
                endcase
            end else begin
                next_state = #1 state;
                counter_loader = #1 { T_WIDTH{1'b0} };
                loade = #1 1'b0;
            end
        end
    end

endmodule
