import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from unittest.mock import MagicMock
from src.llama3_chat import LlamaChat
from src.environment import Environment

class MockEnvironment:

    def __init__(self):
        self.design_prompt = lambda _: "This is the design prompt."
        self.all_design_file_paths = []

# Mock Environment
mock_env = MockEnvironment()

# Mock Llama for tokenizer simulation
llama = LlamaChat(None, mock_env, False, skip_load=True)
llama.max_new_tokens = 100  # Example max tokens
llama.tokenizer = MagicMock()
llama.tokenizer.encode = lambda text: [0] * len(text)  # Simulate token count as length of text

class TestLimitConversation(unittest.TestCase):

    def setUp(self):
        """Set up a sample conversation for testing"""
        self.sample_conversation = [
            {"role": "system", "content": "You are a verification assistant."},
            {"role": "user", "content": "First user message"},
            {"role": "assistant", "content": "First assistant response"},
            {"role": "user", "content": "Second user message"},
            {"role": "assistant", "content": "Second assistant response"},
            {"role": "user", "content": "Third user message"},  # Stack pointer should be here
            {"role": "assistant", "content": "Third assistant response"},
        ]
        self.design_prompt = {"role": "user", "content": "This is the design prompt."}

    def test_limit_conversation_basic_trim(self):
        """Test if limit_conversation properly trims conversation"""
        trimmed_convo, sp, dp = llama.limit_conversation(self.sample_conversation, context_window=30, stack_pointer=5, design_prompt_idx=3)
        self.assertLess(len(trimmed_convo), len(self.sample_conversation))  # Should shrink
        self.assertEqual(trimmed_convo[-1]["role"], "assistant")  # Last message should be assistant's response

    def test_stack_pointer_retention(self):
        """Test if stack pointer is retained after trimming"""
        _, sp, _ = llama.limit_conversation(self.sample_conversation, context_window=50, stack_pointer=5, design_prompt_idx=3)
        self.assertIsNotNone(sp)
        self.assertEqual(self.sample_conversation[sp]["role"], "user")

    def test_design_prompt_retention(self):
        """Test if design prompt is retained after trimming"""
        self.sample_conversation.insert(5, self.design_prompt)  # Place design prompt before last user input
        _, _, dp = llama.limit_conversation(self.sample_conversation, context_window=50, stack_pointer=6, design_prompt_idx=5)
        self.assertIsNotNone(dp)
        self.assertEqual(self.sample_conversation[dp]["content"], self.design_prompt["content"])

    def test_recover_stack_pointer(self):
        """If stack pointer is lost, find the first user message"""
        self.sample_conversation.pop(5)  # Remove the stack pointer message
        trimmed_convo, sp, _ = llama.limit_conversation(self.sample_conversation, context_window=50, stack_pointer=None, design_prompt_idx=3)
        self.assertIsNotNone(sp)
        self.assertEqual(trimmed_convo[sp]["role"], "user")

    def test_recover_design_prompt(self):
        """If design prompt is lost, re-insert it"""
        self.sample_conversation.pop(3)  # Remove the design prompt
        trimmed_convo, _, dp = llama.limit_conversation(self.sample_conversation, context_window=50, stack_pointer=5, design_prompt_idx=None)
        self.assertIsNotNone(dp)
        self.assertEqual(trimmed_convo[dp]["content"], self.design_prompt["content"])

    def test_recover_both_stack_and_design_prompt(self):
        """If both stack pointer and design prompt are lost, recover both"""
        self.sample_conversation.pop(5)  # Remove stack pointer message
        self.sample_conversation.pop(3)  # Remove design prompt
        trimmed_convo, sp, dp = llama.limit_conversation(self.sample_conversation, context_window=50, stack_pointer=None, design_prompt_idx=None)

        self.assertIsNotNone(sp)
        self.assertEqual(trimmed_convo[sp]["role"], "user")
        self.assertIsNotNone(dp)
        self.assertEqual(trimmed_convo[dp]["content"], self.design_prompt["content"])

    def test_empty_conversation(self):
        """Edge case: Empty conversation"""
        trimmed_convo, sp, dp = llama.limit_conversation([], context_window=50, stack_pointer=None, design_prompt_idx=None)
        self.assertEqual(trimmed_convo, [])
        self.assertIsNone(sp)
        self.assertIsNone(dp)

    def test_minimal_conversation(self):
        """Edge case: Minimal conversation with one message"""
        minimal_convo = [{"role": "user", "content": "Only one message"}]
        trimmed_convo, sp, dp = llama.limit_conversation(minimal_convo, context_window=50, stack_pointer=0, design_prompt_idx=None)
        self.assertEqual(trimmed_convo, minimal_convo)
        self.assertEqual(sp, 0)
        self.assertIsNone(dp)

    def test_max_length_conversation(self):
        """Edge case: Very long conversation"""
        long_convo = [{"role": "user", "content": "Message " + str(i)} for i in range(200)]
        trimmed_convo, sp, dp = llama.limit_conversation(long_convo, context_window=100, stack_pointer=150, design_prompt_idx=140)
        self.assertLess(len(trimmed_convo), len(long_convo))  # Should trim conversation
        self.assertIsNotNone(sp)
        self.assertIsNotNone(dp)

if __name__ == '__main__':
    unittest.main()
