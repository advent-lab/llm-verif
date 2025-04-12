from openai import OpenAI
import tiktoken
import os
from src.modelchat import ModelChat
import time
from src.simulator import Simulator
from src.environment import Environment
from src.conversation_manager import ConversationManager
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

class ChatGPTChat(ModelChat):

    def __init__(self, simulator: Simulator | None, environment: Environment, do_sample: bool, temperature_function: str = "constant", temperature: float = 0.3, top_p: float = 0.7, max_new_tokens: int = 4098, timeout_seconds: int = 1000, seed: int | None = None, skip_load: bool = False):

        super().__init__(simulator, environment, do_sample, temperature_function, temperature, top_p, max_new_tokens, timeout_seconds, seed, skip_load)

    def load_model(self, dotenv_path: str | None = None, seed: int | None = None) -> tuple[None, None]:
        
        # Set seed if given
        if seed is not None:
            # Seed generation
            pass

        if dotenv_path is not None:
            load_dotenv(dotenv_path)
        elif self.environment.dotenv_path is not None:
            load_dotenv(self.environment.dotenv_path)
        else:
            logging.error("You need to have a .env file with API credentails.\n")
            exit()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        
        client = OpenAI(api_key=api_key)

        # Load tiktoken tokenizer
        try:
            tokenizer = tiktoken.encoding_for_model(self.environment.model_id)
        except KeyError:
            tokenizer = tiktoken.get_encoding("cl100k_base")

        return client, tokenizer

    def generate_response(self, conversation_history: ConversationManager, num_return_sequences: int = 1):
        if not conversation_history:
            raise ValueError("Conversation history is required.")

        # Evaluate new temperature based on temperature function
        self.temperature = self.temperature_function(conversation_history.length())

        conversation = conversation_history.get_messages()

        try:
            start_time = time.time()

            response = self.llm.chat.completions.create(
                model=self.environment.model_id,
                messages=conversation,
                temperature=self.temperature if self.do_sample else 0.0,
                top_p=self.top_p if self.do_sample else 1.0,
                max_completion_tokens=self.max_new_tokens,
                n=num_return_sequences
            )

            elapsed_time = time.time() - start_time

            responses = [choice.message.content.strip() for choice in response.choices]
            total_tokens = response.usage.total_tokens if response.usage else sum(len(self.tokenizer.encode(r)) for r in responses)

        except Exception as e:
            logging.error(f"Error during OpenAI generation: {e}")
            responses = [""] * num_return_sequences
            total_tokens = 0
            elapsed_time = self.timeout_seconds

        return responses, total_tokens, elapsed_time
