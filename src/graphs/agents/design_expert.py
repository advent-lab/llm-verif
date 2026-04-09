"""Design Expert agent for CovAgent v2 (Orchestrator-Expert-Generator architecture).

NOTE: Used by the v2 graph (orc_exp_gen.py) only. In v2.1 (ag_crt.py), this
role is replaced by the Analyzer-Generator (analyzer_generator.py).

The Design Expert is a persistent agent that maintains conversation history
across all invocations within a run via a MemorySaver checkpointer. It reads
specifications, RTL source code, and coverage reports, providing analysis
and stimulus recipes to the Orchestrator.
"""

import uuid
import logging
from typing import Tuple

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from ...config import Config
from ...prompts.loader import load_expert_prompt
from ...tools.filesystem import read_file, list_directory
from ...tools.coverage import get_coverage_status
from ...utils.event_log import emit
from ...utils.tokens import count_message_tokens
from ...utils.conversation_logger import get_logger


def create_design_expert(config: Config) -> Tuple[CompiledStateGraph, str]:
    """Create the persistent Design Expert agent.

    Args:
        config: Application configuration.

    Returns:
        Tuple of (compiled_graph, thread_id) where thread_id is a fixed
        UUID used for all invocations within this run.
    """
    memory = MemorySaver()

    # Build system prompt
    system_prompt = load_expert_prompt(
        design_name=config.design_name,
        design_dir=config.design_dir,
        spec_path=config.spec_path,
        design_files=config.design_files,
        design_context_files=config.design_context_files,
    )

    # Build LLM kwargs
    llm_kwargs = dict(
        model=config.design_expert_model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        api_key=config.openai_api_key,
    )
    if config.reasoning_effort != "disabled":
        llm_kwargs["reasoning_effort"] = config.reasoning_effort

    expert_tools = [read_file, list_directory, get_coverage_status]

    expert_graph = create_agent(
        model=ChatOpenAI(**llm_kwargs),
        tools=expert_tools,
        checkpointer=memory,
        system_prompt=system_prompt,
        name="design_expert",
    )

    thread_id = str(uuid.uuid4())

    logging.info(f"Design Expert created (model={config.design_expert_model}, "
                 f"thread={thread_id[:8]}...)")

    emit("expert_created", {
        "model": config.design_expert_model,
        "thread_id": thread_id,
        "tools": [t.name for t in expert_tools],
    })

    return expert_graph, thread_id


def invoke_expert(
    expert_graph: CompiledStateGraph,
    thread_id: str,
    query: str,
    config: Config = None,
) -> str:
    """Invoke the Design Expert with a query.

    The expert maintains persistent conversation history via the checkpointer.
    Each invocation with the same thread_id continues the conversation.

    Args:
        expert_graph: The compiled expert agent graph.
        thread_id: Fixed thread ID for this run.
        query: Natural language query from the Orchestrator.
        config: Optional config for context limit checking.

    Returns:
        The expert's natural language response.
    """
    from langchain_core.messages import HumanMessage

    logging.info(f"Querying Design Expert: {query[:100]}...")

    emit("expert_query", {
        "thread_id": thread_id,
        "query_length": len(query),
        "query_preview": query[:200],
    })

    try:
        result = expert_graph.invoke(
            {"messages": [HumanMessage(content=query)]},
            config={
                "configurable": {"thread_id": thread_id},
                "callbacks": [get_logger("design_expert")],
            },
        )

        # Extract the last AI message content
        messages = result.get("messages", [])

        response = ""
        for msg in reversed(messages):
            if hasattr(msg, 'content') and type(msg).__name__ == 'AIMessage':
                response = msg.content
                break

        if not response:
            response = "Design Expert did not produce a response."
            logging.warning("Expert invocation returned no AI message")

        logging.info(f"Expert response: {len(response)} chars")

        emit("expert_response", {
            "thread_id": thread_id,
            "response_length": len(response),
            "response_preview": response[:200],
        })

        return response

    except Exception as e:
        error_msg = f"Design Expert error: {str(e)}"
        logging.error(error_msg)
        emit("expert_error", {
            "thread_id": thread_id,
            "error": str(e),
        })
        return error_msg
