"""Evaluate the harness of harness.py on a small test set, with a code check and an LLM as a judge.

For each test case: run the agent, check in code what can be checked exactly,
then ask a second model to grade what needs reading. Results go to 07-own-harness/results.json.
    uv run 07-own-harness/evaluate.py
"""

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from harness import ask, build_agent, load_mcp_tools  # noqa: E402

JUDGE_MODEL = "gemini-3.5-flash"  # a stronger model than the agent's

TEST_CASES = [
    {"question": "What time is it in Tokyo right now?",
     "expected": "Calls get_current_time for Asia/Tokyo and gives that time in 24-hour format with the city."},
    {"question": "Is it within office hours (09:00 to 18:00) in New York right now?",
     "expected": "Calls get_current_time for America/New_York and answers yes or no consistently with that time."},
    {"question": "What's my public IP address?",
     "expected": "Calls get_public_ip and reports exactly the address it returned."},
    {"question": "What time is it on Mars?",
     "expected": "Explains that Mars has no IANA time zone and the tool cannot answer, without inventing a time."},
    {"question": "Who wrote Don Quixote?",
     "expected": "Answers Miguel de Cervantes without calling any tool."},
]


# The judge returns this structure, not free text, so the program can count passes.
# The reasoning comes first so the model explains before it decides.
class Verdict(BaseModel):
    reasoning: str = Field(description="Two or three sentences checking the answer against each criterion.")
    passed: bool = Field(description="True only if the answer meets every criterion.")


JUDGE_PROMPT = """You are grading the answer of an AI assistant that has tools for the current time and the user's public IP address.

Criteria:
1. Grounded: every time, date or IP address in the answer matches a tool result in the trace. Anything not in the trace is a guess and fails.
2. Rules: times are written in 24-hour format followed by the city, for example "14:05 Madrid".
3. Task: the answer does what the expected behaviour describes.

Question: {question}
Expected behaviour: {expected}
Tool trace (what really happened, recorded by the harness):
{trace}
Answer:
{answer}"""


def lists_its_tool_calls(answer, trace):
    """AGENTS.md asks for one "Called ..." line per tool call. That is exact, so check it in code."""
    called = {line.split("(")[0].removeprefix("call ") for line in trace if line.startswith("call ")}
    return all(f"Called {name}" in answer for name in called)


async def main():
    judge = ChatGoogleGenerativeAI(model=JUDGE_MODEL, temperature=0).with_structured_output(Verdict)
    results = []
    async with AsyncExitStack() as stack:
        agent = build_agent(await load_mcp_tools(stack), auto_approve=True)
        for case in TEST_CASES:
            answer, trace = await ask(agent, case["question"])
            verdict = await judge.ainvoke(
                JUDGE_PROMPT.format(**case, trace="\n".join(trace) or "(no tool calls)", answer=answer)
            )
            results.append({**case, "answer": answer, "trace": trace,
                            "code_check": lists_its_tool_calls(answer, trace), **verdict.model_dump()})

    for r in results:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  code check {'ok' if r['code_check'] else 'no'}  {r['question']}")
        print(f"      judge: {r['reasoning']}")
    print(f"\nJudge pass rate: {sum(r['passed'] for r in results)}/{len(results)}")
    Path("07-own-harness/results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
