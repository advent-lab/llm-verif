"""
Unified OpenAI-compatible async backend for LLM interactions.

Supports:
- OpenAI API (https://api.openai.com/v1)
- vLLM inference servers (local or remote)
- Any OpenAI-compatible inference server
"""

from typing import Any, Type
from openai import AsyncOpenAI
from pydantic import BaseModel
import tiktoken
import os
from llm_verif.modelchat import ModelChat
import time
from llm_verif.simulator import Simulator
from llm_verif.environment import Environment
from llm_verif.conversation_manager import ConversationManager
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)


class OpenAIBackend(ModelChat):
    """Unified async chat backend using OpenAI-compatible API protocol.

    This backend can communicate with:
    - OpenAI's API (base_url defaults to https://api.openai.com/v1)
    - vLLM servers (e.g., base_url='http://localhost:8000/v1')
    - Any other OpenAI-compatible inference server

    Configuration priority:
    1. Explicit parameters (base_url, api_key)
    2. Environment variables (OPENAI_BASE_URL, OPENAI_API_KEY)
    3. .env file loaded from environment.dotenv_path
    """

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
        skip_load: bool = False,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize OpenAI-compatible backend.

        Args:
            simulator: Simulator instance (can be None)
            environment: Environment configuration
            do_sample: Whether to use sampling (temperature > 0)
            temperature_function: Temperature scheduling function name
            temperature: Initial temperature value
            top_p: Top-p sampling parameter
            max_new_tokens: Maximum tokens to generate
            timeout_seconds: Request timeout
            seed: Random seed (currently unused for API calls)
            skip_load: Skip model loading (for testing)
            base_url: API base URL (None = OpenAI default)
            api_key: API key (None = load from env)
        """
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
            skip_load,
        )

        self.base_url = base_url
        self.api_key = api_key

        if not skip_load:
            self.llm, self.tokenizer = self.load_model(seed=seed)
        else:
            self.llm = None
            self.tokenizer = None

    def load_model(
        self, dotenv_path: str | None = None, seed: int | None = None
    ) -> tuple[Any, Any]:
        """Load AsyncOpenAI client and tokenizer.

        Args:
            dotenv_path: Path to .env file (overrides environment.dotenv_path)
            seed: Random seed (currently unused for API)

        Returns:
            Tuple of (AsyncOpenAI client, tokenizer)
        """
        # Load environment variables from .env if specified
        if dotenv_path is not None:
            load_dotenv(dotenv_path)
        elif self.environment.dotenv_path is not None:
            load_dotenv(self.environment.dotenv_path)

        # Get API key (priority: instance var > env var > error)
        api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logging.error(
                "API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

        # Get base URL (priority: instance var > env var > None for OpenAI default)
        base_url = self.base_url or os.getenv("OPENAI_BASE_URL")

        # Create async client
        client_kwargs = {"api_key": api_key, "timeout": float(self.timeout_seconds)}
        if base_url:
            client_kwargs["base_url"] = base_url
            logging.info(f"Using OpenAI-compatible API at: {base_url} {api_key}")
        else:
            logging.info("Using OpenAI API (https://api.openai.com/v1)")

        client = AsyncOpenAI(**client_kwargs)

        # Load tiktoken tokenizer for token counting
        # For non-OpenAI models, this will approximate token counts
        try:
            tokenizer = tiktoken.encoding_for_model(self.environment.model_id)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            logging.warning(
                f"Model '{self.environment.model_id}' not recognized by tiktoken. "
                "Using cl100k_base encoding for token estimation."
            )
            tokenizer = tiktoken.get_encoding("cl100k_base")

        return client, tokenizer

    async def generate_response_async(
        self, 
        conversation_history: ConversationManager, 
        num_return_sequences: int = 1,
        response_format: Type[BaseModel] | None = None
    ) -> tuple[list[str], int, float]:
        """Generate responses asynchronously using OpenAI-compatible API.

        Args:
            conversation_history: Conversation manager with message history
            num_return_sequences: Number of responses to generate (n parameter)
            response_format: Optional Pydantic model for structured output.
                           When provided, uses OpenAI's structured output feature
                           to ensure responses match the schema.

        Returns:
            Tuple of (responses list, total tokens used, elapsed time in seconds)
        """
        if not conversation_history:
            raise ValueError("Conversation history is required.")

        # Update temperature based on temperature function
        self.temperature = self.temperature_function(conversation_history.length())

        # Get messages in OpenAI format (list of dicts with role/content)
        conversation = conversation_history.get_messages()

        try:
            start_time = time.time()

            # Build API call parameters
            api_params = {
                "model": self.environment.model_id,
                "messages": conversation,
                "temperature": self.temperature if self.do_sample else 0.0,
                "top_p": self.top_p if self.do_sample else 1.0,
                "max_tokens": self.max_new_tokens,
                "n": num_return_sequences,
            }

            # Make async API call with or without structured output
            # Note: Structured output requires using parse() instead of create()
            if response_format is not None:
                logging.info(f"Using structured output with schema: {response_format.__name__}")
                
                # Warn if batch size > 1 (parse() doesn't support n parameter)
                if num_return_sequences > 1:
                    logging.warning(
                        f"Structured output with parse() doesn't support n > 1. "
                        f"Requested {num_return_sequences} responses, but will only generate 1. "
                        "Consider disabling structured output for batch generation."
                    )
                
                # Use parse() method for structured output
                # Note: parse() doesn't support n parameter, so we can only get 1 response
                response = await self.llm.beta.chat.completions.parse(
                    model=api_params["model"],
                    messages=api_params["messages"],
                    temperature=api_params["temperature"],
                    top_p=api_params["top_p"],
                    max_tokens=api_params["max_tokens"],
                    response_format=response_format,
                )
                
                elapsed_time = time.time() - start_time
                
                # Extract parsed response
                responses = []
                for choice in response.choices:
                    parsed = choice.message.parsed
                    if parsed:
                        # Convert Pydantic model to JSON string for compatibility
                        responses.append(parsed.model_dump_json(indent=2))
                    else:
                        # Fallback to raw content if parsing failed
                        responses.append(choice.message.content.strip() if choice.message.content else "")
            else:
                # Standard create() for non-structured output
                response = await self.llm.chat.completions.create(**api_params)
                elapsed_time = time.time() - start_time
                
                # Standard string responses
                responses = [choice.message.content.strip() for choice in response.choices]

            # Get token count from API response or estimate
            if response.usage:
                total_tokens = response.usage.total_tokens
            else:
                # Fallback: estimate tokens if usage not provided
                total_tokens = sum(len(self.tokenizer.encode(r)) for r in responses)

        except Exception as e:
            logging.error(f"Error during API generation: {e}")
            responses = [""] * num_return_sequences
            total_tokens = 0
            elapsed_time = self.timeout_seconds

        return responses, total_tokens, elapsed_time

    def generate_response(
        self, conversation_history: ConversationManager, num_return_sequences: int = 1
    ) -> tuple[list[str], int, float]:
        """Synchronous wrapper for backwards compatibility.

        This method will be removed in a future version. Use generate_response_async instead.

        Note: This creates a new event loop which is inefficient. Callers should
        migrate to async/await pattern.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.generate_response_async(conversation_history, num_return_sequences)
        )
