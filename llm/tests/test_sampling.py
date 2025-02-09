import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from unittest.mock import MagicMock
from src.llama3_chat import LlamaChat

class TestLlamaSampling(unittest.TestCase):
    def setUp(self) -> None:
        self.llama = LlamaChat(None, False)

    def test_sampling(self):
        # Create a random conversation
        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Generate a test bench."},
        ]

        # Generate some responses
        responses = []
        for i in range(3):
            responses.append(self.llama.generate_response(conversation)[0])

        for response in responses[1:]:
            print(response)
            self.assertEqual(response, responses[0])

if __name__ == "__main__":
    unittest.main()