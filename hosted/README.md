# Hosted "Azure Sandwich" Coding Agent

A Foundry **hosted agent** recreation of the customer's "Microsoft/Azure
sandwich": host a codex model in Foundry, wrap it with a coding harness, and
persist chat history to Cosmos.

```
┌────────────────────────────────────────────────────────────┐
│  ResponsesHostServer     (hosted in Foundry, /responses)    │  ← hosting
├────────────────────────────────────────────────────────────┤
│  create_harness_agent    (the coding engine: file access,   │  ← "build your own
│                           shell, planning, web search)      │     claw" harness
│                           + Cosmos chat-history audit sink  │
├────────────────────────────────────────────────────────────┤
│  FoundryChatClient       (gpt-5.x-codex hosted in Foundry)  │  ← model
└────────────────────────────────────────────────────────────┘
```

## Why a harness (and not a "codex agent" class)

Codex is a **model**, not an Agent Framework agent class — there's no
`CodexAgent`. So we build our own agent around it with `create_harness_agent`
(the same factory as the Agent Framework "build your own claw" samples). It wires
up function invocation, file access, shell, planning, and web search; we plug in
the codex `FoundryChatClient` and our instructions.

## Project structure

A shared **runtime** (hosting layer) plus one **self-contained package per agent**.
The runtime hosts **one** agent per deployment (Foundry's `agent.yaml` declares a
single hosted agent, and `ResponsesHostServer` serves one agent); a small registry
selects which one, so agents are added without touching the entrypoint or server.

```
main.py                         Thin entrypoint: build_server().run()
hosted_agent/
├── __init__.py                 Architecture overview
├── runtime/                    Shared hosting layer
│   ├── settings.py             Shared env config (endpoint, HOSTED_AGENT_NAME)
│   ├── chat_client.py          Shared FoundryChatClient factory
│   └── server.py               build_server() -> ResponsesHostServer
└── agents/
    ├── __init__.py             Registry: AGENT_BUILDERS, build_agent(name)
    └── harness/                The "Azure sandwich" agent — self-contained
        ├── __init__.py         Exposes build()
        ├── agent.py            build() wiring + model choice
        ├── instructions.py     System prompt
        └── history.py          Cosmos-backed chat history for this agent
agent.yaml                      Foundry hosted-agent manifest (Responses protocol)
azure.yaml                      azd deployment (Container Apps + codex model)
```

### Add another agent

1. Create `hosted_agent/agents/<name>/` with an `__init__.py` exposing a zero-arg
   `build()` that returns any Agent Framework agent (a `ChatAgent`, a
   `create_harness_agent` harness, a workflow, …). Keep its instructions, history,
   and options alongside it in the same directory.
2. Register it in `AGENT_BUILDERS` in [hosted_agent/agents/__init__.py](hosted_agent/agents/__init__.py).
3. Select it at runtime with `HOSTED_AGENT_NAME=<name>` (default: `harness`).

> **Why is there a second `cosmos_history.py`-equivalent in `entities/coding_sandwich/`?**
> They are intentionally *not* shared. This agent's [history.py](hosted_agent/agents/harness/history.py)
> subclasses the GA `HistoryProvider` (the `create_harness_agent` hosted path);
> the `entities/coding_sandwich` copy subclasses `BaseHistoryProvider` (the
> `ChatAgent`/DevUI wrapper path) and has a different `get_messages` signature.
> This directory must also be a self-contained Docker build context, so it
> vendors its own copy rather than importing across the repo. Keep them separate.

## Chat history in a hosted agent

Important nuance: in the **hosted** model the server owns live conversation
replay. `ResponsesHostServer` rejects a history provider with
`load_messages=True` ("History is managed by the hosting infrastructure").

So Cosmos is attached as a **write-only audit sink** (`load_messages=False`):
every turn is durably captured to Cosmos while the host manages live context.
Only user/assistant text is stored — codex reasoning traces and the tool
transcript carry server-side IDs (`rs_...`/`fc_...`) that break on replay and
aren't really chat history.

> For full server-side conversation persistence in Cosmos (not just an audit
> copy), implement the `ResponseProviderProtocol` from
> `azure.ai.agentserver.responses.store` and pass it as
> `ResponsesHostServer(agent, store=...)`. The audit-sink approach here is the
> quick path that matches the "chat history in Cosmos" ask.

## Configure

`.env` (see values already populated):

```
FOUNDRY_PROJECT_ENDPOINT=https://<project>.services.ai.azure.com/api/projects/<project>
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.3-codex
HOSTED_AGENT_NAME=harness   # which registered agent to serve (default: harness)
# COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/   # optional, enables durable audit
COSMOS_CHAT_DATABASE=agent-chat
COSMOS_CHAT_CONTAINER=sessions
```

## Run

Python 3.13, GA `agent-framework`.

```bash
cd hosted-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
az login
python main.py           # serves the Responses endpoint locally
```

## Deploy to Foundry

```bash
az login
azd up          # provisions + deploys (Container Apps host, codex deployment)
# or, after provisioning:
azd deploy
```
