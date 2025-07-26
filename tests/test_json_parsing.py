import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from src.llama3_chat import LlamaChat

class TestJsonParse(unittest.TestCase):

    def test_json_parse(self):
        response = """
        `json
        {
            "test bench": "module tb; endmodule",
            "comments": "ngwreignwoiebmwerg"
        }
        `
        Here is some JSON
        """
        test_bench_code, error_code = LlamaChat.convert_json_response_to_dict(response)
        print(test_bench_code)
        self.assertEqual(error_code, 0)

        response = "{\"test bench\": \"\n\t\tmodule tb_llm;\n\n\t\t\t// Clock logic\n\t\t\treg clk;\n\t\t\treg reset_n;\n\t\t\tinitial\n\t\t\tbegin\n\t\t\t\tclk = 0;\n\t\t\t\tforever #5 clk = ~clk;\n\t\t\tend\n\n\t\t\t// Configuration parameters\n\t\t\treg [15 : 0] bit_rate;\n\t\t\treg [3 : 0]  data_bits;\n\t\t\treg [1 : 0]  stop_bits;\n\n\t\t\t// External data interface\n\t\t\treg rxd;\n\t\t\twire txd;\n\n\t\t\t// Internal receive interface.\n\t\t\twire rxd_syn;\n\t\t\twire [7 : 0] rxd_data;\n\t\t\treg rxd_ack;\n\n\t\t\t// Internal transmit interface.\n\t\t\treg txd_syn;\n\t\t\treg [7 : 0] txd_data;\n\t\t\twire txd_ack;\n\n\t\t\t// Instantiate the DUT\n\t\t\tuart_core dut(\n\t\t\t\t.clk(clk),\n\t\t\t\t.reset_n(reset_n),\n\t\t\t\t.bit_rate(bit_rate),\n\t\t\t\t.data_bits(data_bits),\n\t\t\t\t.stop_bits(stop_bits),\n\t\t\t\t.rxd(rxd),\n\t\t\t\t.txd(txd),\n\t\t\t\t.rxd_syn(rxd_syn),\n\t\t\t\t.rxd_data(rxd_data),\n\t\t\t\t.rxd_ack(rxd_ack),\n\t\t\t\t.txd_syn(txd_syn),\n\t\t\t\t.txd_data(txd_data),\n\t\t\t\t.txd_ack(txd_ack)\n\t\t\t);\n\n\t\t\t// Test cases\n\t\t\tinitial\n\t\t\tbegin\n\t\t\t\t// Initialize the inputs\n\t\t\t\treset_n = 0;\n\t\t\t\tbit_rate = 16'd9600;\n\t\t\t\tdata_bits = 4\\\'d8;\n\t\t\t\tstop_bits = 2\\\'d1;\n\t\t\t\trxd = 1\\\'b1;\n\t\t\t\trxd_ack = 1\\\'b0;\n\t\t\t\ttxd_syn = 1\\\'b0;\n\t\t\t\ttxd_data = 8\\\'d0;\n\n\t\t\t\t// Reset the DUT\n\t\t\t\t#10 reset_n = 1;\n\n\t\t\t\t// Test case 1: Receive a byte\n\t\t\t\t#10 rxd = 1\\\'b0;\n\t\t\t\t#10 rxd = 1\\\'b1;\n\t\t\t\t#10 rxd_ack = 1\\\'b1;\n\t\t\t\t#10 rxd_ack = 1\\\'b0;\n\n\t\t\t\t// Test case 2: Transmit a byte\n\t\t\t\t#10 txd_syn = 1\\\'b1;\n\t\t\t\t#10 txd_data = 8\\\'d255;\n\t\t\t\t#10 txd_syn = 1\\\'b0;\n\n\t\t\t\t// Test case 3: Change configuration\n\t\t\t\t#10 bit_rate = 16\\\'d19200;\n\t\t\t\t#10 data_bits = 4\\\'d7;\n\t\t\t\t#10 stop_bits = 2\\\'d2;\n\n\t\t\t\t// Test case 4: Receive a byte with new configuration\n\t\t\t\t#10 rxd = 1\\\'b0;\n\t\t\t\t#10 rxd = 1\\\'b1;\n\t\t\t\t#10 rxd_ack = 1\\\'b1;\n\t\t\t\t#10 rxd_ack = 1\\\'b0;\n\n\t\t\t\t// Finish the simulation\n\t\t\t\t#100 $finish;\n\t\t\tend\n\t\tendmodule\n\t\",\n\t\"comments\": \"The test bench covers the basic functionality of the UART core, including receiving and transmitting bytes, and changing the configuration. The test cases are designed to cover the different states of the UART core and to ensure that the core is functioning correctly. The simulation is finished after 100 time units to allow the test cases to complete.\"\n}"
        test_bench_code, error_code = LlamaChat.convert_json_response_to_dict(response)
        print(test_bench_code)
        self.assertEqual(error_code, 0)


if __name__=="__main__":
    unittest.main()
