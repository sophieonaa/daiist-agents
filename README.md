# Building blocks of AI agents

AI coding agents such as GitHub Copilot's agent mode or Claude Code are built from a few simple pieces: a model, a loop, tools, instruction files, skills and subagents, plus the guardrails that limit what they may do. This lab takes them one at a time. Each step adds one piece to the agent in your IDE and gives you something to try, using two small tools you write yourself: one that reads the clock and one that looks up your public IP address.

| Step | What you learn | What you add |
|---|---|---|
| [1. How an agent works](01-how-agents-work/README.md) | The model, the context, tools, the agent loop, and how the model "decides" | Nothing yet: see what the agent does without tools |
| [2. Tools and MCP](02-tools-and-mcp/README.md) | The Model Context Protocol, the standard way to give agents tools | Two MCP servers in Python: `time` and `public_ip` |
| [3. Instruction files](03-instruction-files/README.md) | Standing rules the agent reads in every session | [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) |
| [4. Skills](04-skills/README.md) | Know-how the agent loads only when a task needs it | The `meeting-time-planner` skill |
| [5. Subagents](05-subagents/README.md) | Delegating a sub-task to an agent with its own context | The `world-clock` subagent |
| [6. The harness and guardrails](06-guardrails/README.md) | What the harness controls, prompt injection, and checks that stop unwanted actions | A deny rule and a hook that blocks network commands |
| [7. Your own harness and LLM as a judge](07-own-harness/README.md) | Building the agent yourself with LangChain, and testing it with a second model as the grader | A Python agent with the same tools, rules and guardrails, and an evaluation script |

## How the pieces fit together

| | What it gives the agent | What it is | When it enters the context |
|---|---|---|---|
| Tool | An ability: do something outside the model | A function with a schema | Its definition: on every call. Its result: after each use |
| MCP server | A set of tools, packaged to work in any host | A program speaking the MCP protocol | Its tool definitions: on every call |
| Instruction file | Standing rules for a project | A Markdown file | At the start of every session |
| Skill | Know-how: the steps to do a task well | A folder with a `SKILL.md` | Name and description: always. The rest: when needed |
| Subagent | A helper for a sub-task | Another agent loop | Only its final answer |
| Guardrail | Limits: what may go in, run, or come out | A rule or a program in the harness | Never: the harness applies it outside the model |

A **plugin** is a bundle that installs several of these in one step, for example a set of skills together with the MCP servers they rely on.

## Setup

You need an AI agent in your editor: **GitHub Copilot** in VS Code (Copilot Free is enough; students get Copilot Pro free through [GitHub Education](https://education.github.com)) or **Claude Code**. Everything else runs on your machine or in a codespace. Steps 1 to 6 call no model API themselves; step 7 builds its own agent and needs a free Gemini API key (see [step 7](07-own-harness/README.md#setup)).

All the configuration the agents read is at the root of this repository (`.vscode/`, `.mcp.json`, `AGENTS.md`, `.claude/`). Agents only find it when the repository folder itself is open (File, Open Folder), not a folder above it.

### Option A: GitHub Codespaces (nothing to install)

A codespace is a Linux machine in the cloud with VS Code in your browser. This repository's configuration, in [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json), installs Python 3.12, uv, the project's dependencies, the Copilot Chat and Claude Code extensions, and the `claude` command for the terminal. Both agents ask you to sign in the first time: Copilot with your GitHub account, Claude Code with a Claude account (a paid plan or API credits).

1. Open <https://codespaces.new/ami232/daiist-agents> and click **Create codespace**. (Equivalently: on the repository's GitHub page, click **Code**, then the **Codespaces** tab, then **Create codespace on main**.)
2. Wait for the setup to finish (a terminal shows `uv sync` running). The first start takes a few minutes.
3. Open a terminal (**Terminal**, **New Terminal**) and run `uv run 02-tools-and-mcp/list_and_call.py` to check it works.

The tools run inside the codespace, so they report the codespace's clock and its public IP (a GitHub data centre), not yours. GitHub's free plan includes a monthly allowance of codespace hours; stop the codespace when you finish (**Codespaces** menu at the bottom left, **Stop Current Codespace**).

### Option B: your own computer

You need Python 3.12 or later, [uv](https://docs.astral.sh/uv/getting-started/installation/) and git. Run every command from the root of the repository.

```bash
git clone https://github.com/ami232/daiist-agents.git
cd daiist-agents
uv sync
uv run 02-tools-and-mcp/list_and_call.py
```

`uv sync` creates `.venv/` and installs the `mcp` SDK, `httpx` and, for step 7, LangChain. Every command in the lab starts with `uv run`, which uses that environment.
