# Copyright (c) Microsoft. All rights reserved.

"""Assemble the "Microsoft/Azure sandwich" coding agent.

    ┌────────────────────────────────────────────────────────────┐
    │  Agent Framework wrapper  (chat history -> Azure Cosmos DB) │  ← top
    ├────────────────────────────────────────────────────────────┤
    │  Coding engine tools      (Codex / Cursor stand-in)        │  ← middle
    ├────────────────────────────────────────────────────────────┤
    │  Foundry-hosted model     (AzureOpenAIChatClient)          │  ← bottom
    └────────────────────────────────────────────────────────────┘

Configure via ``.env`` (see ``.env.sample``):

    AZURE_OPENAI_ENDPOINT        Foundry / Azure OpenAI endpoint
    CODING_MODEL_DEPLOYMENT      deployment name, e.g. gpt-5-codex (falls back
                                 to MODEL_DEPLOYMENT_NAME, then "gpt-4o")
    AZURE_OPENAI_API_KEY         optional; if unset, Entra ID (az login) is used
    COSMOS_ENDPOINT              optional; if set, history persists to Cosmos,
                                 otherwise it stays in-memory for the session
"""

from __future__ import annotations

import os

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIResponsesClient
from dotenv import load_dotenv

from .coding_tools import CODING_TOOLS
from .cosmos_history import CosmosHistoryProvider

load_dotenv()

INSTRUCTIONS = """\
You are a senior software engineer working inside a sandboxed workspace.

You have a coding engine exposed as tools: list_files, read_file, write_file,
and run_python. Rules for using them reliably:

1. Always use the tools for file operations — never claim you created or changed
   a file without calling write_file.
2. After writing code, verify it: read_file to confirm contents, and run_python
   to check it executes when relevant.
3. Tool results that start with "ERROR:" mean the action failed. Read the
   message, fix the cause, and retry — do not pretend it succeeded.
4. Keep changes minimal and focused on what the user asked.

Explain what you did briefly, then stop.
"""


def _build_chat_client() -> AzureOpenAIResponsesClient:
    """Bottom slice: the model hosted in Foundry / Azure OpenAI.

    Uses the Responses API, which supports codex deployments (gpt-5.x-codex,
    codex-mini) as well as gpt-4o / gpt-5.x. Codex models do NOT support Chat
    Completions, so the Responses client is the reliable choice here.
    """
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "Set AZURE_OPENAI_ENDPOINT (or PROJECT_ENDPOINT) to your Foundry / "
            "Azure OpenAI endpoint in .env."
        )
    deployment = (
        os.getenv("CODING_MODEL_DEPLOYMENT")
        or os.getenv("MODEL_DEPLOYMENT_NAME")
        or "gpt-4o"
    )
    # Responses API requires 2025-03-01-preview or later (codex needs this).
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if api_key:
        return AzureOpenAIResponsesClient(
            endpoint=endpoint,
            deployment_name=deployment,
            api_version=api_version,
            api_key=api_key,
        )

    # Keyless: authenticate with Entra ID (requires `az login`).
    from azure.identity import AzureCliCredential

    return AzureOpenAIResponsesClient(
        endpoint=endpoint,
        deployment_name=deployment,
        api_version=api_version,
        credential=AzureCliCredential(),
    )


def _build_history_provider() -> CosmosHistoryProvider:
    """Top slice: own the conversation and persist it.

    Uses Cosmos when COSMOS_ENDPOINT is set; otherwise runs in memory-only mode
    (same reasoning-sanitization, no durable storage). Either way, reasoning
    traces are stripped so replaying history never trips the Responses API.
    """
    return CosmosHistoryProvider()


def build_agent() -> Agent:
    """Build the full sandwich agent."""
    return Agent(
        _build_chat_client(),
        instructions=INSTRUCTIONS,
        name="AzureSandwichCoder",
        description="A Foundry-hosted coding agent with Cosmos-backed chat history.",
        tools=CODING_TOOLS,
        context_providers=[_build_history_provider()],
    )


# Built at import time so DevUI (and `from entities.coding_sandwich import agent`)
# can discover it.
agent = build_agent()
