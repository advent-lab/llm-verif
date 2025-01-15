import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from unittest.mock import MagicMock
from src.llama3_chat import LlamaChat

class TestLlamaChat(unittest.TestCase):
    def setUp(self):
        # Mock the LlamaChat class and its tokenizer
        self.llama_chat = LlamaChat(None, True, skip_load=True)  # Pass dummy arguments for simplicity
        self.llama_chat.tokenizer = MagicMock()

        # Mock the tokenizer.encode method to return token counts
        def mock_encode(content):
            return list(range(len(content)))  # Simulates tokens proportional to content length

        self.llama_chat.tokenizer.encode = MagicMock(side_effect=mock_encode)
        self.llama_chat.max_new_tokens = 1000  # Set max new tokens for tests

    def test_empty_conversation(self):
        with self.assertRaises(ValueError) as context:
            self.llama_chat.limit_conversation([])
        self.assertEqual(str(context.exception), "Conversation must be a non-empty list of messages.")

    def test_invalid_conversation_type(self):
        with self.assertRaises(ValueError) as context:
            self.llama_chat.limit_conversation("invalid_input")
        self.assertEqual(str(context.exception), "Conversation must be a non-empty list of messages.")

    def test_only_system_prompt(self):
        conversation = [{"role": "system", "content": "You are a helpful assistant."}]
        result = self.llama_chat.limit_conversation(conversation)
        self.assertEqual(result, conversation, "Should return the same conversation if it only contains the system prompt.")

    def test_no_truncation_needed(self):
        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Generate a test bench."},
        ]
        result = self.llama_chat.limit_conversation(conversation)
        self.assertEqual(result, conversation, "Should not modify conversation if within token limits.")

    def test_truncation(self):
        # Simulate a conversation exceeding token limits
        long_message = "x" * 5000  # Each message is 5000 tokens long
        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": long_message},
            {"role": "assistant", "content": long_message},
            {"role": "user", "content": long_message},
        ]
        truncated_conversation = self.llama_chat.limit_conversation(conversation)
        self.assertLessEqual(
            sum(len(self.llama_chat.tokenizer.encode(msg["content"])) for msg in truncated_conversation),
            128000 - self.llama_chat.max_new_tokens,
            "Conversation should be truncated to fit within token limits."
        )
        self.assertEqual(
            truncated_conversation[0]["role"], "system",
            "The system prompt should always be preserved."
        )

    def test_truncation_logs_warning(self):
        # Simulate a conversation that cannot be fully truncated to fit within limits
        long_message = "x" * 150000  # Single message exceeds the token limit
        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": long_message},
        ]
        with self.assertLogs(level="WARNING") as log:
            self.llama_chat.limit_conversation(conversation)
        self.assertTrue(any("could not be fully limited" in message for message in log.output), "Should log a warning when conversation cannot fit within token limits.")

if __name__ == "__main__":
    unittest.main()
