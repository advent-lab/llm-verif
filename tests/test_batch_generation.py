import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from unittest.mock import MagicMock
from src.llama3_chat import LlamaChat

class TestBatchGeneration(unittest.TestCase):
    def setUp(self):
        self.llama = LlamaChat(None, True)

    def test_batch_generation(self):
        # Set up some mock conversations
        conversations = [
            
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Generate a test bench."},
                {"role": "assistant", "content": "I am a helpful assistant."},
                {"role": "user", "content": "Generate a test bench."},
            
        ]

       
        responses, _, _ = self.llama.generate_response(conversation_history=conversations, num_return_sequences=5)

        self.assertEqual(len(responses), 5)

if __name__ == "__main__":
    unittest.main() 
