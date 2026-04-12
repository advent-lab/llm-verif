SCRIPT = brun_questa.sh

all: run

run:
	bash $(SCRIPT)

# Coverage viewer (replaces 'dve -cov')
cov:
	vsim -viewcov coverage/cov.ucdb &

# Waveform viewer (replaces 'verdi -ssf sim.fsdb')
wave:
	vsim -view vsim.wlf &

# HTML coverage report (no VCS equivalent — bonus)
report:
	vcover report -html -output coverage/html_report coverage/cov.ucdb

clean:
	rm -rf work transcript *.log *.wlf coverage modelsim.ini
