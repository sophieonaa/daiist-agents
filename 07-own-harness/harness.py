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
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.mcp import MCPAdapter  # langchain.mcp is in beta and warns on import


MODEL = "gemini-3.5-flash-lite"  # fast, cheap, generous free-tier quota
SERVERS = ["02-tools-and-mcp/servers/time_server.py", "02-tools-and-mcp/servers/ip_server.py"]
NEEDS_APPROVAL = {"get_public_ip"}  # tools that send a request to another service


# 1. Tools: connect to each MCP server; MCPAdapter wraps its tools as LangChain tools.
#    This is what VS Code does with .vscode/mcp.json (step 2).
#    One adapter per server: a single multi-server adapter would rename tools to time_get_current_time.
async def load_mcp_tools(stack):
    tools = []
    for script in SERVERS:
        adapter = await stack.enter_async_context(MCPAdapter(Path(script)))
        tools += await adapter.list_tools()
    return tools


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
        model=ChatGoogleGenerativeAI(model=MODEL),
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
            lines.append(f"result {message.text}")  # MCP results arrive as content blocks
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
