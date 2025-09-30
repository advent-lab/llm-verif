from __future__ import annotations

import os
import time
import logging
from typing import Any, Union
from dotenv import load_dotenv

from openai import OpenAI
import tiktoken

from llm_verif.modelchat import ModelChat
from llm_verif.environment import Environment
from llm_verif.simulator import Simulator
from llm_verif.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

class OpenAIBackend(ModelChat):

    def __init__(
      self,
      simulator: Simulator | None,
      environment: Environment,
      do_sample: bool,
      temperature_function: str = "constant",
      temperature: float = 0.3,
      top_p: float = 0.7,
      max_new_tokens: int = 4098,
      timeout_seconds: int = 1000,
      seed: int | None = None,
      skip_load: bool = False
    ):
        super().__init__(
            simulator,
            environment,
            do_sample,
            temperature_function,
            temperature,
            top_p,
            max_new_tokens,
            timeout_seconds,
            seed,
            skip_load
        )

        self.llm, self.tokenizer = self.load_model()

    def load_model(
            self, 
    ) -> tuple[Any, Any]:
        
        base_url = getattr(self.environment, 'base_url', None) or os.getenv("OPENAI_BASE_URL")
        api_key = getattr(self.environment, 'api_key', None) or os.getenv("OPENAI_API_KEY")
        model_id = getattr(self.environment, 'model_id', None) or os.getenv("OPENAI_MODEL_ID")

        if not api_key:
            raise ValueError("API_KEY not found.")
        if not model_id:
            raise ValueError("MODEL_ID not found.")
        
        client_kwargs = {"api_key": api_key}
        if base_url:
            if not base_url.rstrip("/").endswith("/v1"):
                base_url = base_url.rstrip("/") + "/v1"

            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs) # type: ignore

        try:
            tokenizer = tiktoken.encoding_for_model(model_id)
        except Exception:
            tokenizer = tiktoken.get_encoding("cl100k_base")

        return client, tokenizer

    def unload_model(self):
        self.llm = None
        self.tokenizer = None

    def generate_response(
            self,
            conversation_history: ConversationManager,
            num_return_sequences: int = 1
    ):
        if not conversation_history:
            raise ValueError("Conversation history is required.")

        self.temperature = self.temperature_function(conversation_history.length())

        conversation = conversation_history.get_messages()

        if not self.llm or not self.tokenizer:
            self.llm, self.tokenizer = self.load_model()

        req = dict(
            model = self.environment.model_id,
            messages = conversation,
            temperature = self.temperature if self.do_sample else 0.0,
            top_p = self.top_p if self.do_sample else 1.0,
            max_tokens = int(self.max_new_tokens),
            n = int(num_return_sequences),
        )

        start = time.time()
        try:
            resp = self.llm.chat.completions.create(**req) # type: ignore
            elapsed = time.time() - start

            choices = getattr(resp, 'choices', []) or []
            responses = []
            for ch in choices:
                msg = getattr(ch, 'message', None)
                txt = getattr(msg, 'content', '') if msg else ''
                responses.append(txt.strip())

            if getattr(resp, 'usage', None) and resp.usage.total_tokens is not None:
                total_tokens = resp.usage.total_tokens
            else:
                total_tokens = sum(len(self.tokenizer.encode(r)) for r in responses)

        except Exception as e:
            logging.error(f"Error during OpenAI generation: {e}")
            responses = [""] * num_return_sequences
            total_tokens = 0
            elapsed = self.timeout_seconds

        return responses, total_tokens, elapsed