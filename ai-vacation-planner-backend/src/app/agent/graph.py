"""
graph.py

LangGraph agent graph for the travel planning agent.

Defines a ReAct-style agent loop using StateGraph:
  1. The LLM receives the user message and decides which tools to call
  2. If tool calls are present the tools node executes them
  3. Results are fed back to the LLM
  4. The loop continues until the LLM produces a final response with no tool calls

Validation is handled by the existing LLMItineraryOutput Pydantic schema.
If the response fails validation the error is fed back into the conversation
and the agent is given another chance to correct it, up to max_validation_retries times.
"""

import json
import logging
import operator
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import ValidationError

from app.agent.tools import AGENT_TOOLS
from app.config import settings
from app.schemas.itinerary import LLMItineraryOutput

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    """Represents the full message history passed between graph nodes.

    Attributes:
        messages: The accumulated list of messages in the conversation,
                  including human input, assistant responses, and tool results.
                  Uses operator.add as the reducer so each node appends
                  rather than replaces the list.
    """
    messages: Annotated[list[AnyMessage], operator.add]

AGENT_SYSTEM_PROMPT = """You are an expert travel planning assistant with access to tools.

When planning a trip, you should:
1. Use get_trip_details to retrieve the trip information from the database
2. Use get_weather to check current weather conditions at the destination
3. Use search_travel_knowledge to retrieve local tips, hidden gems, and recommendations
4. Use get_place_info to find specific types of places the traveller might enjoy
5. Combine all gathered information to generate a detailed, personalized itinerary

Always use the available tools to gather real information before generating the itinerary.
Return the final itinerary as a JSON object in this exact format with no extra text:
{
  "days": [
    {
      "day": 1,
      "activities": ["Activity 1", "Activity 2", "Activity 3"]
    }
  ]
}

Each day must have between 3 and 5 activities. Activities must be specific real places
that exist at the destination. Day numbers must be sequential starting from 1 with no
gaps or duplicates. Consider the weather, budget, and travel style when suggesting activities.
"""


def _build_llm() -> ChatAnthropic:
    """Initialise the ChatAnthropic model with all agent tools bound.

    Returns:
        A ChatAnthropic instance ready for tool-calling in the agent loop.
    """
    llm = ChatAnthropic(
        model=settings.agent_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )
    return llm.bind_tools(AGENT_TOOLS)


async def call_llm(state: AgentState) -> dict:
    """Send the current message history to the LLM and return its response.

    Prepends the system prompt on every call to keep the agent on track.
    Logs how many tool calls the LLM requested, if any.

    Args:
        state: The current agent state containing the message history.

    Returns:
        A dict with a messages key containing the LLM response to append.
    """
    llm = _build_llm()
    messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state["messages"]
    response = await llm.ainvoke(messages)
    tool_call_count = len(response.tool_calls) if hasattr(response, "tool_calls") else 0
    logger.info("LLM responded with %d tool call(s)", tool_call_count)
    return {"messages": [response]}


tool_node = ToolNode(AGENT_TOOLS)


def should_continue(state: AgentState) -> str:
    """Decide whether the agent should call more tools or finish.

    Args:
        state: The current agent state.

    Returns:
        "tools" if the last message contains tool calls, "end" otherwise.
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


def _build_graph():
    """Assemble and compile the agent StateGraph.

    Graph structure:
        START -> call_llm -> (tools -> call_llm)* -> END

    Returns:
        A compiled LangGraph StateGraph ready to invoke.
    """
    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges(
        "llm",
        should_continue,
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "llm")
    return graph.compile()


async def run_agent(request: str, max_validation_retries: int = 3) -> dict:
    """Run the travel planning agent and return a validated itinerary.

    Invokes the compiled graph with the request as the initial human message.
    After each invocation the response is validated against LLMItineraryOutput,
    which enforces:
      - day >= 1
      - between 3 and 5 non-empty activities per day
      - sequential day numbering with no gaps or duplicates

    If validation fails the exact Pydantic error is fed back into the
    conversation as a new HumanMessage so the agent can correct its output.
    This retry loop runs up to max_validation_retries times before giving up.

    Args:
        request: A plain-text description of what to plan, including
                 trip ID, destination, days, budget, and travel style.
        max_validation_retries: Maximum number of correction attempts
                                before raising ValueError.

    Returns:
        A validated dict matching the LLMItineraryOutput schema,
        ready to be saved to the database.

    Raises:
        ValueError: If the agent fails to return a valid itinerary
                    after all retry attempts are exhausted, or if it
                    exceeds the configured tool-call cycle limit.
    """
    graph = _build_graph()
    messages = [HumanMessage(content=request)]

    # Each tool-call cycle is one llm step plus one tools step, plus one
    # final llm step to produce the answer with no further tool calls.
    recursion_limit = (settings.agent_max_iterations * 2) + 1

    for attempt in range(1, max_validation_retries + 1):
        try:
            result = await graph.ainvoke(
                {"messages": messages},
                config={"recursion_limit": recursion_limit},
            )
        except GraphRecursionError as e:
            raise ValueError(
                f"Agent exceeded the maximum of {settings.agent_max_iterations} "
                "tool-call cycles without producing a final answer"
            ) from e
        messages = result["messages"]
        raw = messages[-1].content

        # Strip accidental markdown fences before parsing
        if raw.startswith("```"):
            lines = raw.splitlines()
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            raw = "\n".join(inner).strip()

        try:
            parsed = json.loads(raw)
            validated = LLMItineraryOutput(**parsed)
            logger.info("Agent response validated on attempt %d", attempt)
            return validated.model_dump()

        except json.JSONDecodeError as e:
            error_feedback = (
                f"Your response was not valid JSON: {e}. "
                "Return only a JSON object with no extra text or markdown."
            )
        except ValidationError as e:
            error_feedback = (
                f"Your response failed validation: {e}. "
                "Fix the issues and return the corrected JSON object."
            )

        logger.warning(
            "Agent validation attempt %d/%d failed, feeding error back to agent",
            attempt,
            max_validation_retries,
        )
        messages.append(HumanMessage(content=error_feedback))

    raise ValueError(
        f"Agent failed to return a valid itinerary after {max_validation_retries} attempts"
    )
