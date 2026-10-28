"""A minimal agent harness built with LangChain: Gemini, the lab's two MCP servers, AGENTS.md and two guardrails.

It does in about 100 lines what VS Code and Claude Code do for you in steps 1 to 6.
Set GEMINI_API_KEY first (see 07-own-harness/README.md), then:
    uv run 07-own-harness/harness.py "What time is it in Tokyo right now?"
"""

import asyncio
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, wrap_tool_call
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = "gemini-3.5-flash-lite"  # fast, cheap, generous free-tier quota
SERVERS = ["02-tools-and-mcp/servers/time_server.py", "02-tools-and-mcp/servers/ip_server.py"]
NEEDS_APPROVAL = {"get_public_ip"}  # tools that send a request to another service


# 1. Tools: connect to each MCP server and wrap its tools as LangChain tools.
#    This is what VS Code does with .vscode/mcp.json (step 2).
async def load_mcp_tools(stack):
    tools = []
    for script in SERVERS:
        params = StdioServerParameters(command="uv", args=["run", script])
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        for tool in (await session.list_tools()).tools:
            tools.append(as_langchain_tool(session, tool))
    return tools


def as_langchain_tool(session, tool):
    async def call(**arguments):
        result = await session.call_tool(tool.name, arguments)
        return result.content[0].text

    # The name, description and JSON schema are all the model will ever see of the tool.
    return StructuredTool.from_function(
        coroutine=call, name=tool.name, description=tool.description, args_schema=tool.input_schema
    )


# 2. A guardrail around the tools: ask the person at the keyboard before a call leaves the machine.
#    The model cannot skip it, because the harness runs it, not the model (step 6).
def approval_guardrail(auto_approve):
    @wrap_tool_call
    async def ask_before_network(request, handler):
        call = request.tool_call
        if call["name"] in NEEDS_APPROVAL and not auto_approve:
            answer = input(f"  Allow {call['name']}({call['args']})? [y/N] ")
            if answer.strip().lower() != "y":
                return ToolMessage(
                    content="The user refused this tool call. Do not try to get the information another way.",
                    tool_call_id=call["id"],
                    status="error",
                )
        return await handler(request)

    return ask_before_network


# 3. The agent: model + tools + standing rules + guardrails. create_agent runs the loop of step 1.
def build_agent(tools, auto_approve=False):
    return create_agent(
        model=ChatGoogleGenerativeAI(model=MODEL, temperature=0),
        tools=tools,
        system_prompt=Path("AGENTS.md").read_text(),  # the instruction file of step 3, sent on every call
        middleware=[
            approval_guardrail(auto_approve),
            ModelCallLimitMiddleware(run_limit=8),  # hard stop for runaway loops
        ],
    )


def tool_trace(messages):
    """Every tool call and its result, in order: what the harness saw happen."""
    lines = []
    for message in messages:
        if isinstance(message, AIMessage):
            lines += [f"call {c['name']}({c['args']})" for c in message.tool_calls]
        elif isinstance(message, ToolMessage):
            lines.append(f"result {message.content}")
    return lines


async def ask(agent, question):
    """Run one question through the agent. Returns the final answer and the tool trace."""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].text, tool_trace(result["messages"])


async def main(question):
    async with AsyncExitStack() as stack:
        agent = build_agent(await load_mcp_tools(stack))
        answer, trace = await ask(agent, question)
    print("\n".join(f"  {line}" for line in trace))
    print(answer)


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "What time is it in Tokyo right now?"))
