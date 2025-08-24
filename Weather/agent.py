import asyncio
from typing import Any, AsyncIterable, Dict, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

memory = MemorySaver()


def _fetch_mcp_tools_sync() -> list:
    """
    Helper function: runs the async MultiServerMCPClient code in a synchronous manner.
    Fetches the remote tools from your MCP server(s).
    """
    connection = {
        "url": "http://127.0.0.1:3001/sse",
        "transport": "sse",
    }
    async def _load():
        return await load_mcp_tools(None, connection=connection)

    return asyncio.run(_load())

class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal["input_required", "completed", "error"] = "completed"
    message: str

# "Your sole purpose is to use the 'get_exchange_rate' tool to answer questions about currency exchange rates. "

class WeatherAgent:
    SYSTEM_INSTRUCTION = (
    "You are a specialized assistant for weather queries."
    "If the user asks about anything other than weather conditions or forecasts,"
    "politely state that you cannot help with that topic and can only assist with weather-related queries."
    "Do not attempt to answer unrelated questions or use tools for other purposes."
    "Set response status to input_required if the user needs to provide more information (e.g., location or time)."
    "Set response status to error if there is an error while processing the request."
    "Set response status to completed if the request is complete."
    "You must store the final user-facing response in the structured_response field."
    )

    def __init__(self):
        # Instead of a local @tool, fetch remote tools from MCP
        self.tools = _fetch_mcp_tools_sync()

        self.model = ChatDeepSeek(model="deepseek-chat")
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat,
        )

    async def invoke(self, query, sessionId) -> str:
        config = {"configurable": {"thread_id": sessionId}}
        await self.graph.ainvoke({"messages": [("user", query)]}, config)
        print("Latest messages:", self.graph.get_state(config).values.get("messages"))
        return self.get_agent_response(config)

    async def stream(self, query, sessionId) -> AsyncIterable[Dict[str, Any]]:
        inputs = {"messages": [("user", query)]}
        config = {"configurable": {"thread_id": sessionId}}

        for item in self.graph.stream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            if (
                isinstance(message, AIMessage)
                and message.tool_calls
                and len(message.tool_calls) > 0
            ):
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Looking up the exchange rates...",
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Processing the exchange rates..",
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        if structured_response and isinstance(structured_response, ResponseFormat):
            if structured_response.status == "input_required":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message,
                }
            elif structured_response.status == "error":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message,
                }
            elif structured_response.status == "completed":
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": structured_response.message,
                }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]
