import re

def extract_verilog_module_header(design_path: str) -> str:
    # Read the file line by line to identify the header
    with open(design_path, 'r') as f:
        lines = f.readlines()

    start_line = None
    end_line = None
    inside_module = False
    capturing_ports = False

    # Loop through lines to find the module declaration and subsequent I/O declarations
    for i, line in enumerate(lines):
        # Look for the start of the module declaration
        if re.match(r"\s*module\s+\w+", line) and start_line is None:
            start_line = i
            inside_module = True

        # If we're inside the module header, check for the end of the main header
        if inside_module:
            # Detect the end of the main module header (closing parenthesis with semicolon)
            if re.search(r"\);\s*$", line):
                end_line = i
                inside_module = False
                capturing_ports = True  # Start capturing additional ports after the header ends
                continue

        # Capture subsequent input/output/inout declarations
        if capturing_ports:
            if re.match(r"\s*(input|output|inout)\s+", line):
                end_line = i  # Update end line for each I/O declaration line

    # Slice the lines to get only the module header and subsequent I/O declarations
    if start_line is not None and end_line is not None:
        module_header = "".join(lines[start_line:end_line + 1])
        return module_header.strip()
    else:
        return "No module header found."






print(extract_verilog_module_header('/home/slowe8/Research/llm_verif_dataset/data_points/fifo/design/sync_fifo.sv'))


