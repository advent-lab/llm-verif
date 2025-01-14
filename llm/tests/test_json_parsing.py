import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from src.llama3_chat import LlamaChat

class TestJsonParse(unittest.TestCase):
    def setUp(self):
        self.llama_chat = LlamaChat(None, True)

    def test_json_parse(self):
        response = """
        `json
        {
            "test bench": "module tb; endmodule"
        }
        `
        Here is some JSON
        """
        test_bench_code, error_code = self.llama_chat.parse_json_response(response)
        print(test_bench_code)
        self.assertEqual(error_code, 0)