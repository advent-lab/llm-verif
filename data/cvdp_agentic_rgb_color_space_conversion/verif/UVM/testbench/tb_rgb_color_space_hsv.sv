`timescale 1ns/1ps

module tb_llm (
    input               clk,
    input               rst,

    // Memory ports to initialize (1/delta) values
    input               we,
    input       [7:0]   waddr,
    input      [24:0]   wdata,

    // Input data with valid.
    input               valid_in,
    input       [7:0]   r_component,
    input       [7:0]   g_component,
    input       [7:0]   b_component,

    input reg  [11:0]   h_component,  // Output in fx10.2 format, degree value = (h_component)/4
    input reg  [12:0]   s_component,  // Output in fx1.12 format. % value = (s_component/4096)*100
    input reg  [11:0]   v_component,  // % value = (v_componente/255) * 100
    input reg          valid_out
);
    
    
    // Derived signals for coverage
    logic [7:0] max_rgb;
    logic [7:0] min_rgb;
    logic [7:0] delta_rgb;
    
    
    // Helper function to calculate max
    function automatic [7:0] calc_max;
        input [7:0] r, g, b;
        begin
            calc_max = (r > g) ? ((r > b) ? r : b) : ((g > b) ? g : b);
        end
    endfunction
    
    // Helper function to calculate min
    function automatic [7:0] calc_min;
        input [7:0] r, g, b;
        begin
            calc_min = (r < g) ? ((r < b) ? r : b) : ((g < b) ? g : b);
        end
    endfunction
    
    // Update derived signals
    always_comb begin
        max_rgb = calc_max(r_component, g_component, b_component);
        min_rgb = calc_min(r_component, g_component, b_component);
        delta_rgb = max_rgb - min_rgb;
    end
    
    // ===========================================================================
    // FUNCTIONAL COVERAGE
    // ===========================================================================
    
    covergroup cg_rgb_hsv_advanced @(posedge clk iff valid_in);
        option.cross_auto_bin_max = 0;
        
        // Cover R component corner cases
        cp_r_component: coverpoint r_component {
            bins zero = {8'h00};
            bins one = {8'h01};
            bins max_val = {8'hFF};
            bins almost_max = {8'hFE};
            bins low_range = {[8'h02:8'h1F]};
            bins mid_low = {[8'h20:8'h7F]};
            bins mid_high = {[8'h80:8'hDF]};
            bins high_range = {[8'hE0:8'hFD]};
            bins power_of_2[] = {8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80};
        }
        
        // Cover G component corner cases
        cp_g_component: coverpoint g_component {
            bins zero = {8'h00};
            bins one = {8'h01};
            bins max_val = {8'hFF};
            bins almost_max = {8'hFE};
            bins low_range = {[8'h02:8'h1F]};
            bins mid_low = {[8'h20:8'h7F]};
            bins mid_high = {[8'h80:8'hDF]};
            bins high_range = {[8'hE0:8'hFD]};
            bins power_of_2[] = {8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80};
        }
        
        // Cover B component corner cases
        cp_b_component: coverpoint b_component {
            bins zero = {8'h00};
            bins one = {8'h01};
            bins max_val = {8'hFF};
            bins almost_max = {8'hFE};
            bins low_range = {[8'h02:8'h1F]};
            bins mid_low = {[8'h20:8'h7F]};
            bins mid_high = {[8'h80:8'hDF]};
            bins high_range = {[8'hE0:8'hFD]};
            bins power_of_2[] = {8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80};
        }
        
        // Cover which channel is maximum (determines hue sector)
        cp_max_channel: coverpoint {(r_component >= g_component && r_component >= b_component),
                                      (g_component >= r_component && g_component >= b_component),
                                      (b_component >= r_component && b_component >= g_component)} {
            bins r_is_max = {3'b100};
            bins g_is_max = {3'b010};
            bins b_is_max = {3'b001};
            bins r_g_tie = {3'b110};
            bins g_b_tie = {3'b011};
            bins r_b_tie = {3'b101};
            bins all_equal = {3'b111};
        }
        
        // Cover delta (max - min) values - critical for saturation and hue
        cp_delta: coverpoint delta_rgb {
            bins zero = {8'h00};           // Grayscale (no saturation)
            bins very_small_delta = {[8'h01:8'h0F]};
            bins small_delta = {[8'h10:8'h3F]};
            bins medium_delta = {[8'h40:8'hBF]};
            bins large_delta = {[8'hC0:8'hFE]};
            bins max_delta = {8'hFF};
        }
        
        // Cover grayscale vs color
        cp_color_type: coverpoint (r_component == g_component && g_component == b_component) {
            bins grayscale = {1'b1};
            bins color_val = {1'b0};
        }
        
        // Cover primary colors
        cp_primary_colors: coverpoint {r_component, g_component, b_component} {
            bins pure_red = {24'hFF0000};
            bins pure_green = {24'h00FF00};
            bins pure_blue = {24'h0000FF};
            bins pure_cyan = {24'h00FFFF};
            bins pure_magenta = {24'hFF00FF};
            bins pure_yellow = {24'hFFFF00};
            bins pure_white = {24'hFFFFFF};
            bins pure_black = {24'h000000};
        }
        
        // Cover equal channel combinations (corner cases for hue calculation)
        // Removed duplicate bins: r_eq_g_ne_b, g_eq_b_ne_r, r_eq_b_ne_g were
        // identical encodings to r_eq_g, g_eq_b, r_eq_b respectively and would
        // never be hit (first matching bin always wins in QuestaSim).
        cp_equal_channels: coverpoint {(r_component == g_component),
                                         (g_component == b_component),
                                         (r_component == b_component)} {
            bins all_different = {3'b000};
            bins r_eq_g = {3'b100};
            bins g_eq_b = {3'b010};
            bins r_eq_b = {3'b001};
            bins all_equal = {3'b111};
        }
        
        // Cross: R vs G to cover all comparison cases
        cross_r_vs_g: cross cp_r_component, cp_g_component {
            bins r_greater_g = binsof(cp_r_component.mid_high) && 
                                binsof(cp_g_component.low_range);
            bins g_greater_r = binsof(cp_g_component.mid_high) && 
                                binsof(cp_r_component.low_range);
            bins r_eq_g_zero = binsof(cp_r_component.zero) && 
                               binsof(cp_g_component.zero);
            bins r_eq_g_max = binsof(cp_r_component.max_val) && 
                              binsof(cp_g_component.max_val);
        }
        
        // Cross: All three channels to capture specific color patterns
        cross_rgb_pattern: cross cp_r_component, cp_g_component, cp_b_component {
            bins all_zero = binsof(cp_r_component.zero) && 
                            binsof(cp_g_component.zero) && 
                            binsof(cp_b_component.zero);
            bins all_max = binsof(cp_r_component.max_val) && 
                           binsof(cp_g_component.max_val) && 
                           binsof(cp_b_component.max_val);
            bins r_max_others_zero = binsof(cp_r_component.max_val) && 
                                      binsof(cp_g_component.zero) && 
                                      binsof(cp_b_component.zero);
            bins g_max_others_zero = binsof(cp_r_component.zero) && 
                                      binsof(cp_g_component.max_val) && 
                                      binsof(cp_b_component.zero);
            bins b_max_others_zero = binsof(cp_r_component.zero) && 
                                      binsof(cp_g_component.zero) && 
                                      binsof(cp_b_component.max_val);
        }
        
        // Cross: Max channel with delta to verify hue calculation
        cross_max_delta: cross cp_max_channel, cp_delta {
            bins all_equal_no_sat = binsof(cp_max_channel.all_equal) && 
                                     binsof(cp_delta.zero);
            bins r_max_full_sat = binsof(cp_max_channel.r_is_max) && 
                                   binsof(cp_delta.max_delta);
            bins g_max_full_sat = binsof(cp_max_channel.g_is_max) && 
                                   binsof(cp_delta.max_delta);
            bins b_max_full_sat = binsof(cp_max_channel.b_is_max) && 
                                   binsof(cp_delta.max_delta);
        }
        
        // Cross: Color type with delta
        cross_color_delta: cross cp_color_type, cp_delta {
            bins grayscale_zero_delta = binsof(cp_color_type.grayscale) && 
                                         binsof(cp_delta.zero);
            ignore_bins grayscale_nonzero = binsof(cp_color_type.grayscale) && 
                                             (!binsof(cp_delta.zero));
        }
        
    endgroup
    
    // Covergroup for output HSV values
    covergroup cg_hsv_output @(posedge clk iff valid_out);
        option.cross_auto_bin_max = 0;
        
        cp_hue: coverpoint h_component {
            bins red_sector = {[12'd0:12'd240]};
            bins yellow_sector = {[12'd241:12'd480]};
            bins green_sector = {[12'd481:12'd720]};
            bins cyan_sector = {[12'd721:12'd960]};
            bins blue_sector = {[12'd961:12'd1200]};
            bins magenta_sector = {[12'd1201:12'd1440]};
        }
        
        cp_saturation: coverpoint s_component {
            bins no_sat = {13'd0};
            bins very_low_sat = {[13'd1:13'd409]};
            bins low_sat = {[13'd410:13'd1228]};
            bins medium_sat = {[13'd1229:13'd2867]};
            bins high_sat = {[13'd2868:13'd3686]};
            bins very_high_sat = {[13'd3687:13'd4095]};
            bins full_sat = {13'd4096};
        }
        
        cp_value: coverpoint v_component {
            bins black_val = {12'd0};
            bins very_dark_val = {[12'd1:12'd25]};
            bins dark_val = {[12'd26:12'd76]};
            bins medium_val = {[12'd77:12'd178]};
            bins bright_val = {[12'd179:12'd229]};
            bins very_bright_val = {[12'd230:12'd254]};
            bins max_bright_val = {12'd255};
        }
        
        cross_hue_sat: cross cp_hue, cp_saturation {
            bins red_no_sat = binsof(cp_hue.red_sector) && binsof(cp_saturation.no_sat);
            bins red_full_sat = binsof(cp_hue.red_sector) && binsof(cp_saturation.full_sat);
            bins green_no_sat = binsof(cp_hue.green_sector) && binsof(cp_saturation.no_sat);
            bins green_full_sat = binsof(cp_hue.green_sector) && binsof(cp_saturation.full_sat);
            bins blue_no_sat = binsof(cp_hue.blue_sector) && binsof(cp_saturation.no_sat);
            bins blue_full_sat = binsof(cp_hue.blue_sector) && binsof(cp_saturation.full_sat);
        }
        
        cross_sat_val: cross cp_saturation, cp_value {
            bins no_sat_black = binsof(cp_saturation.no_sat) && binsof(cp_value.black_val);
            bins no_sat_white = binsof(cp_saturation.no_sat) && binsof(cp_value.max_bright_val);
            bins full_sat_bright = binsof(cp_saturation.full_sat) && binsof(cp_value.max_bright_val);
            
            ignore_bins impossible_full_sat_black = binsof(cp_saturation.full_sat) && 
                                                     binsof(cp_value.black_val);
        }
        
    endgroup
    
    // Covergroup for memory initialization
    covergroup cg_memory_init @(posedge clk iff we);
        option.cross_auto_bin_max = 0;
        
        cp_write_addr: coverpoint waddr {
            bins first = {8'h00};
            bins last = {8'hFF};
            bins low_range = {[8'h01:8'h7F]};
            bins high_range = {[8'h80:8'hFE]};
            bins power_of_2[] = {8'h01, 8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80};
        }
        
        cp_write_data: coverpoint wdata {
            bins zero = {25'h0000000};
            bins max_wdata = {25'h1FFFFFF};
            bins mid_range = {[25'h0000001:25'h1FFFFFE]};
        }
        
    endgroup
    
    // Covergroup for valid signal behavior
    covergroup cg_valid_behavior @(posedge clk);
        option.cross_auto_bin_max = 0;
        
        cp_valid_in_trans: coverpoint valid_in {
            bins rise = (1'b0 => 1'b1);
            bins fall = (1'b1 => 1'b0);
            bins stay_high = (1'b1 => 1'b1);
            bins stay_low = (1'b0 => 1'b0);
        }
        
    endgroup
    
    // Instantiate covergroups
    cg_rgb_hsv_advanced cg_rgb_inst;
    cg_hsv_output cg_hsv_inst;
    cg_memory_init cg_mem_inst;
    cg_valid_behavior cg_valid_inst;
    
    initial begin
        cg_rgb_inst = new();
        cg_hsv_inst = new();
        cg_mem_inst = new();
        cg_valid_inst = new();
    end
    
endmodule
