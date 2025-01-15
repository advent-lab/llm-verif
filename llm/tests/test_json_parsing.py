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
            "test bench": "module tb; endmodule"
        }
        `
        Here is some JSON
        """
        test_bench_code, error_code = LlamaChat.convert_json_response_to_dict(response)
        print(test_bench_code)
        print(test_bench_code[0].get("test bench"))
        self.assertEqual(error_code, 0)

if __name__=="__main__":
    unittest.main()
