# Copyright (c) Microsoft. All rights reserved.

"""Foundry hosted "Azure sandwich" agent runtime.

    ┌────────────────────────────────────────────────────────────┐
    │  ResponsesHostServer     (hosted in Foundry, /responses)    │  ← runtime/server.py
    ├────────────────────────────────────────────────────────────┤
    │  agents/<name>/build()   (a coding harness, a workflow, …)  │  ← agents/<name>/
    │                           + Cosmos chat history             │
    ├────────────────────────────────────────────────────────────┤
    │  FoundryChatClient       (gpt-5.x model hosted in Foundry)  │  ← runtime/chat_client.py
    └────────────────────────────────────────────────────────────┘

The runtime hosts **one** agent per deployment (Foundry's ``agent.yaml`` declares
a single hosted agent, and ``ResponsesHostServer`` serves a single agent). To
support *several* agents in one codebase, each agent is a self-contained package
under :mod:`hosted_agent.agents` (its builder, instructions, history, and options
live together), registered in that package's registry. The agent actually served
is chosen by ``HOSTED_AGENT_NAME`` (default: ``harness``).

Layout:
    runtime/        Shared hosting layer (config, chat client, server).
      settings.py     Env config shared by all agents (endpoint, HOSTED_AGENT_NAME).
      chat_client.py  Shared FoundryChatClient factory.
      server.py       build_server() -> ResponsesHostServer.
    agents/         One package per agent, plus the registry.
      harness/        The "Azure sandwich" codex coding agent.
        agent.py        build() wiring.
        instructions.py System prompt.
        history.py      Cosmos-backed chat history for this agent.
"""
