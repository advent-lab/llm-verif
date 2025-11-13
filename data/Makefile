# Top-level Makefile for building all designs
# Usage:
#   make all          - Build all designs
#   make clean        - Clean all designs
#   make compile      - Compile only (no simulation)
#   make COVERAGE=sbceft all  - Override coverage type for all designs

SHELL := /bin/bash

# List of all designs with questa directories
DESIGNS := \
	activation \
	agalimberti_NoCRouter_circular_buffer \
	agalimberti_NoCRouter_crossbar \
	agalimberti_NoCRouter_input_buffer \
	agalimberti_NoCRouter_input_first_alloc \
	agalimberti_NoCRouter_input_port \
	agalimberti_NoCRouter_mesh \
	agalimberti_NoCRouter_rc_unit \
	agalimberti_NoCRouter_round_robin_arbiter \
	agalimberti_NoCRouter_router \
	agalimberti_NoCRouter_top_router \
	agalimberti_NoCRouter_two_routers \
	agalimberti_NoCRouter_vc_alloc \
	chacha_core \
	chacha_qr \
	chacha_top \
	cryptech_uart \
	cvdp_agentic_alu \
	cvdp_agentic_async_fifo_compute_ram_application \
	cvdp_agentic_byte_enable_ram \
	cvdp_agentic_caesar_cipher \
	cvdp_agentic_cic_decimator \
	cvdp_agentic_cont_adder \
	cvdp_agentic_door_lock \
	cvdp_agentic_dual_port_memory \
	cvdp_agentic_fixed_arbiter \
	cvdp_agentic_lfsr \
	cvdp_agentic_memory_scheduler \
	cvdp_agentic_multiplexer \
	cvdp_agentic_poly_interpolator \
	cvdp_agentic_rgb_color_space_conversion \
	cvdp_agentic_sorter \
	cvdp_agentic_spi_complex_mult \
	cvdp_agentic_ttc_lite \
	dpretet_axi-crossbar \
	ethmac_cop \
	ethmac_eth \
	ethmac_eth_with_cop \
	fifo \
	float_adder \
	float_multiplier \
	fsm-verilog0 \
	fsm-verilog1 \
	gsoc-museum-edsac_flipflop \
	gsoc-museum-edsac_memory \
	lab4-fitbit_tracker \
	microprocessor \
	mkmif_core \
	mkmif_spi \
	mkmif_top \
	oh \
	pooling \
	SD-card-controller_bistable_domain_cross \
	SD-card-controller_byte_en_reg \
	SD-card-controller_cmd_master \
	SD-card-controller_cmd_serial_host \
	SD-card-controller_data_master \
	SD-card-controller_data_serial_host \
	SD-card-controller_data_xfer_trig \
	SD-card-controller_edge_detect \
	SD-card-controller_monostable_domain_cross \
	SD-card-controller_top \
	SD-card-controller_wb \
	SD-card-controller_wb_sel_ctrl \
	sha1_core \
	sha1_top \
	sha1_w_mem \
	simple_mat_mul \
	stop-watch \
	TrafficLightController_Divider \
	TrafficLightController_FSM \
	TrafficLightController_Main \
	TrafficLightController_Synchronizer \
	TrafficLightController_TimeParameter \
	TrafficLightController_Timer \
	TrafficLightController_WalkRegister \
	trng_csprng \
	trng_mixer \
	trng_top \
	verilog-divider \
	vndecorrelator \
	Washing-machine-verilog

# Default target
.PHONY: all
all: compile

# Compile all designs
.PHONY: compile
compile:
	@echo "=========================================="
	@echo "Building all $(words $(DESIGNS)) designs..."
	@echo "=========================================="
	@pass=0; fail=0; \
	for design in $(DESIGNS); do \
		echo ""; \
		echo ">>> Building: $$design"; \
		if [ -d "$$design/questa" ]; then \
			if $(MAKE) -C "$$design/questa" compile 2>&1 | tee "$$design/questa/build.log" | grep -q "Errors: 0"; then \
				echo "✓ SUCCESS: $$design"; \
				pass=$$((pass + 1)); \
			else \
				echo "✗ FAILED: $$design (check $$design/questa/build.log)"; \
				fail=$$((fail + 1)); \
			fi; \
		else \
			echo "WARNING: $$design/questa not found"; \
		fi; \
	done; \
	echo ""; \
	echo "=========================================="; \
	echo "Build Summary: $$pass passed, $$fail failed out of $(words $(DESIGNS)) designs"; \
	echo "=========================================="

# Compile only design files (no testbenches)
.PHONY: compile-design
compile-design:
	@echo "=========================================="
	@echo "Compiling design files for all $(words $(DESIGNS)) designs..."
	@echo "=========================================="
	@pass=0; fail=0; \
	for design in $(DESIGNS); do \
		echo ""; \
		echo ">>> Compiling design: $$design"; \
		if [ -d "$$design/questa" ]; then \
			if $(MAKE) -C "$$design/questa" compile_design 2>&1 | tee "$$design/questa/compile_design.log" | grep -q "Errors: 0"; then \
				echo "✓ SUCCESS: $$design"; \
				pass=$$((pass + 1)); \
			else \
				echo "✗ FAILED: $$design (check $$design/questa/compile_design.log)"; \
				fail=$$((fail + 1)); \
			fi; \
		else \
			echo "WARNING: $$design/questa not found"; \
		fi; \
	done; \
	echo ""; \
	echo "=========================================="; \
	echo "Compile Summary: $$pass passed, $$fail failed out of $(words $(DESIGNS)) designs"; \
	echo "=========================================="

# Run simulations for all designs
.PHONY: sim
sim:
	@echo "=========================================="
	@echo "Running simulations for all $(words $(DESIGNS)) designs..."
	@echo "=========================================="
	@pass=0; fail=0; \
	for design in $(DESIGNS); do \
		echo ""; \
		echo ">>> Simulating: $$design"; \
		if [ -d "$$design/questa" ]; then \
			$(MAKE) -C "$$design/questa" all > "$$design/questa/sim.log" 2>&1; \
			if [ $$? -eq 0 ]; then \
				echo "✓ SUCCESS: $$design"; \
				pass=$$((pass + 1)); \
			else \
				echo "✗ FAILED: $$design (check $$design/questa/sim.log)"; \
				fail=$$((fail + 1)); \
			fi; \
		else \
			echo "WARNING: $$design/questa not found"; \
		fi; \
	done; \
	echo ""; \
	echo "=========================================="; \
	echo "Simulation Summary: $$pass passed, $$fail failed out of $(words $(DESIGNS)) designs"; \
	echo "=========================================="

# Clean all designs
.PHONY: clean
clean:
	@echo "=========================================="
	@echo "Cleaning all designs..."
	@echo "=========================================="
	@for design in $(DESIGNS); do \
		if [ -d "$$design/questa" ]; then \
			echo "Cleaning: $$design"; \
			$(MAKE) -C "$$design/questa" clean 2>/dev/null || true; \
		fi; \
	done
	@echo "All designs cleaned!"

# Test a single design
.PHONY: test-one
test-one:
	@if [ -z "$(DESIGN)" ]; then \
		echo "Usage: make test-one DESIGN=<design_name>"; \
		exit 1; \
	fi
	@echo "Testing: $(DESIGN)"
	@$(MAKE) -C "$(DESIGN)/questa" all

# List all designs
.PHONY: list
list:
	@echo "Available designs ($(words $(DESIGNS)) total):"
	@for design in $(DESIGNS); do echo "  - $$design"; done

# Help
.PHONY: help
help:
	@echo "Top-level Makefile for building all designs"
	@echo ""
	@echo "Targets:"
	@echo "  make all            - Compile all designs (default)"
	@echo "  make compile        - Compile all designs (same as all)"
	@echo "  make compile-design - Compile only design files (no testbenches)"
	@echo "  make sim            - Run simulations for all designs"
	@echo "  make clean          - Clean all designs"
	@echo "  make test-one DESIGN=<name> - Test a single design"
	@echo "  make list           - List all available designs"
	@echo "  make help           - Show this help message"
	@echo ""
	@echo "Options:"
	@echo "  COVERAGE=<type>     - Override coverage type (default: bcs)"
	@echo "                        Example: make COVERAGE=sbceft all"
	@echo ""
	@echo "Examples:"
	@echo "  make all                        # Build all designs"
	@echo "  make clean                      # Clean everything"
	@echo "  make test-one DESIGN=sha1_core  # Test single design"
	@echo "  make COVERAGE=sbceft compile    # Use different coverage"
