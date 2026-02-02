"""Token counting utilities for tracking context window usage."""

import tiktoken
from typing import List, Any
import logging

# Cache encoder instances per model
_encoders = {}

def get_encoder(model: str = "gpt-4"):
    """
    Get or create a tiktoken encoder for the specified model.
    
    Args:
        model: Model name (e.g., "gpt-4", "gpt-3.5-turbo", "gpt-5-nano")
    
    Returns:
        tiktoken.Encoding instance
    """
    if model not in _encoders:
        try:
            # Try to get encoding for the specific model
            _encoders[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base (used by GPT-4, GPT-3.5-turbo, and newer models)
            logging.debug(f"Model '{model}' not found in tiktoken, using cl100k_base encoding")
            _encoders[model] = tiktoken.get_encoding("cl100k_base")
    
    return _encoders[model]


def count_message_tokens(messages: List[Any], model: str = "gpt-4") -> int:
    """
    Count tokens in a list of LangChain messages.
    
    This approximates the token count that will be sent to the API.
    Based on OpenAI's token counting methodology.
    
    Args:
        messages: List of LangChain messages (SystemMessage, HumanMessage, AIMessage, ToolMessage)
        model: Model name for token encoding
    
    Returns:
        Approximate token count
    """
    encoder = get_encoder(model)
    
    # Base tokens per message (metadata overhead)
    # For chat models, each message has some overhead
    tokens_per_message = 3  # Approximate: role + name + content markers
    tokens_per_name = 1     # If name is present
    
    total_tokens = 0
    
    for message in messages:
        total_tokens += tokens_per_message
        
        # Count content tokens
        if hasattr(message, 'content') and message.content:
            content = message.content
            if isinstance(content, str):
                total_tokens += len(encoder.encode(content))
            elif isinstance(content, list):
                # For messages with structured content
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        total_tokens += len(encoder.encode(item['text']))
        
        # Count role/type tokens
        message_type = type(message).__name__
        total_tokens += len(encoder.encode(message_type))
        
        # Count name tokens if present
        if hasattr(message, 'name') and message.name:
            total_tokens += tokens_per_name
            total_tokens += len(encoder.encode(message.name))
        
        # Count tool call tokens if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                # Tool name
                if 'name' in tool_call:
                    total_tokens += len(encoder.encode(tool_call['name']))
                # Tool arguments (JSON stringified)
                if 'args' in tool_call:
                    import json
                    args_str = json.dumps(tool_call['args'])
                    total_tokens += len(encoder.encode(args_str))
    
    # Add base tokens for the API call itself
    total_tokens += 3  # Base overhead for the completion
    
    return total_tokens


def format_token_count(token_count: int, context_limit: int = 128000) -> str:
    """
    Format token count with percentage of context window.
    
    Args:
        token_count: Number of tokens
        context_limit: Context window size (default: 128k for GPT-4)
    
    Returns:
        Formatted string like "1234 (1%)" or "64000 (50%)"
    """
    percentage = (token_count / context_limit) * 100
    return f"{token_count:,} ({percentage:.1f}%)"
