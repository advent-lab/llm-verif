"""Agent interaction logging utilities.

Provides structured logging for API requests and agent responses,
with detailed token usage breakdowns including reasoning and cached tokens.
"""

import logging
from .tokens import count_message_tokens


# ANSI color codes for terminal output
class Colors:
    CYAN = '\033[96m'      # API Requests
    GREEN = '\033[92m'     # Agent Responses
    YELLOW = '\033[93m'    # Tool Calls and Results
    MAGENTA = '\033[95m'
    RED = '\033[91m'       # Errors
    BLUE = '\033[94m'      # Info
    BOLD = '\033[1m'
    RESET = '\033[0m'


def log_agent_request(state: dict):
    """Log the latest message being sent to the LLM at INFO level.

    Displays iteration, API call count, coverage stats, and token estimates
    for the messages about to be sent to the API.

    Args:
        state: Agent state dict.
    """
    if not logging.root.isEnabledFor(logging.INFO):
        return

    messages = state.get("messages", [])

    # Skip logging if the latest message is an AIMessage (agent's own response)
    if messages:
        latest_msg = messages[-1]
        msg_type = type(latest_msg).__name__
        if msg_type == "AIMessage":
            return

    iteration = state.get("iteration", "?")
    api_calls = state.get("api_calls", "?")
    current_coverage = state.get("current_coverage", 0.0)
    cumulative_coverage = state.get("cumulative_coverage", 0.0)
    consecutive_failures = state.get("consecutive_failures", 0)
    no_progress = state.get("no_progress_count", 0)

    # Count tokens in the message list
    config = state.get("config")
    model = config.model if config else "gpt-4"
    token_count = count_message_tokens(messages, model)

    logging.info(f"{Colors.CYAN}{Colors.BOLD}{'='*120}{Colors.RESET}")
    logging.info(f"{Colors.CYAN}{Colors.BOLD}API REQUEST [Turn: {api_calls} | Iter: {iteration} | Cumulative: {cumulative_coverage:.2f}% | Last: {current_coverage:.2f}% | Failures: {consecutive_failures} | No Progress: {no_progress} | In: ~{token_count:,}]{Colors.RESET}")

    # Collect all trailing ToolMessages (results from the latest tool execution batch)
    # plus any non-ToolMessage that triggered them, logging each one
    if messages:
        # Gather consecutive ToolMessages from the end of the list
        tool_messages = []
        for msg in reversed(messages):
            if type(msg).__name__ == "ToolMessage":
                tool_messages.append(msg)
            else:
                break
        tool_messages.reverse()

        # If we found tool messages, log all of them; otherwise log the latest message
        msgs_to_log = tool_messages if tool_messages else [messages[-1]]

        for idx, msg in enumerate(msgs_to_log):
            msg_type = type(msg).__name__
            label = f" ({idx + 1}/{len(msgs_to_log)})" if len(msgs_to_log) > 1 else ""
            logging.info(f"{Colors.CYAN}[MESSAGE TYPE] {msg_type}{label}{Colors.RESET}")

            # If it's a tool message, show the tool name
            if hasattr(msg, 'name') and msg.name:
                logging.info(f"{Colors.YELLOW}[TOOL NAME] {msg.name}{Colors.RESET}")

            # Log message content
            if hasattr(msg, 'content') and msg.content:
                content = msg.content
                # Truncate if very long (e.g., tool results with lots of data)
                if config and config.log_truncate and isinstance(content, str) and len(content) > 1000:
                    preview = content[:1000] + f"\n... ({len(content)} chars total)"
                    color = Colors.YELLOW if msg_type == "ToolMessage" else Colors.CYAN
                    logging.info(f"{color}[CONTENT]\n{preview}\n{Colors.RESET}")
                else:
                    color = Colors.YELLOW if msg_type == "ToolMessage" else Colors.CYAN
                    logging.info(f"{color}[CONTENT]\n{content}\n{Colors.RESET}")

    logging.info(f"{Colors.CYAN}{'='*120}{Colors.RESET}\n")


def log_agent_response(response, state: dict, usage: dict = None):
    """Log detailed agent response at INFO level with token usage breakdown.

    Displays token usage including reasoning tokens and cached input tokens,
    reasoning text, and tool calls requested.

    Args:
        response: LangChain AIMessage response.
        state: Agent state dict.
        usage: Dict from extract_usage_from_response() with keys:
            input_tokens, output_tokens, total_tokens,
            reasoning_tokens, cached_input_tokens.
    """
    if not logging.root.isEnabledFor(logging.INFO):
        return

    iteration = state.get("iteration", "?")
    api_calls = state.get("api_calls", "?")
    current_coverage = state.get("current_coverage", 0.0)
    cumulative_coverage = state.get("cumulative_coverage", 0.0)
    config = state.get("config")

    # Build token breakdown from API-reported usage
    in_tok = cached_tok = out_tok = reason_tok = tot_tok = 0
    if usage:
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        tot_tok = usage.get("total_tokens", 0)
        reason_tok = usage.get("reasoning_tokens", 0)
        cached_tok = usage.get("cached_input_tokens", 0)

    logging.info(f"{Colors.GREEN}{Colors.BOLD}{'='*120}{Colors.RESET}")
    logging.info(
        f"{Colors.GREEN}{Colors.BOLD}AGENT RESPONSE [Turn: {api_calls} | Iter {iteration} | "
        f"Cumulative: {cumulative_coverage:.2f}% | Last: {current_coverage:.2f}% | "
        f"In: {in_tok:,} (Cached: {cached_tok:,}) | Out: {out_tok:,} (Reasoning: {reason_tok:,}) | "
        f"Total: {tot_tok:,}]{Colors.RESET}"
    )

    # Log reasoning text (if present)
    if hasattr(response, 'content'):
        if response.content:
            logging.info(f"{Colors.GREEN}[REASONING]\n{response.content}\n{Colors.RESET}")
        else:
            logging.info(f"{Colors.GREEN}[REASONING] (empty response){Colors.RESET}")

    # Log tool calls (if present)
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logging.info(f"{Colors.YELLOW}[TOOL CALLS] {len(response.tool_calls)} tool(s) requested:{Colors.RESET}")
        for i, tool_call in enumerate(response.tool_calls, 1):
            tool_name = tool_call.get('name', 'unknown')
            tool_args = tool_call.get('args', {})

            logging.info(f"{Colors.YELLOW}{i}. {tool_name}{Colors.RESET}")

            # Pretty-print arguments (handle long values)
            for arg_name, arg_value in tool_args.items():
                if config and config.log_truncate and isinstance(arg_value, str) and len(arg_value) > 200:
                    preview = arg_value[:200] + f"... ({len(arg_value)} chars total)"
                    logging.info(f"{Colors.YELLOW}{arg_name}: {preview}{Colors.RESET}")
                else:
                    logging.info(f"{Colors.YELLOW}{arg_name}: {arg_value}{Colors.RESET}")
    else:
        logging.info(f"{Colors.GREEN}[NO TOOL CALLS] Agent did not request any tools{Colors.RESET}")

    logging.info(f"{Colors.GREEN}{'='*120}{Colors.RESET}\n")
