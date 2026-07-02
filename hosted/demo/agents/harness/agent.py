# Copyright (c) Microsoft. All rights reserved.

"""The harness coding agent: build() assembles it bottom -> top.

Codex is a *model*, not an Agent Framework agent class — there is no
``CodexAgent``. So we build our own agent around it with ``create_harness_agent``
(the "build your own claw" factory from the Agent Framework samples). It wires up
function invocation, file access, shell, planning, and web search; we plug in the
codex ``FoundryChatClient`` and a Cosmos-backed ``history_provider``.

This agent owns its model choice (``AZURE_AI_MODEL_DEPLOYMENT_NAME``), while the
Foundry project endpoint is shared runtime config.
"""

from agent_framework import create_harness_agent

from ...runtime.chat_client import build_chat_client
from ...runtime.settings import require_env
from .history import build_history_provider
from .instructions import INSTRUCTIONS


def _model() -> str:
    """Model deployment this agent runs on (e.g. ``gpt-5.3-codex``)."""
    return require_env("AZURE_AI_MODEL_DEPLOYMENT_NAME")


def build():
    """Assemble the hosted sandwich coding agent."""
    return create_harness_agent(
        build_chat_client(model=_model()),
        name="AzureSandwichCoder",
        description="A Foundry-hosted codex coding agent with Cosmos-backed chat history.",
        agent_instructions=INSTRUCTIONS,
        history_provider=build_history_provider(),
        # Client-owned history: don't also keep server-side Responses state, or
        # replayed items collide ("Duplicate item found with id ...").
        default_options={"store": False},
        # The Responses hosting path runs the agent without a per-request
        # AgentSession, but ToolApprovalMiddleware (on by default) requires one.
        # A hosted agent has no interactive approver, so auto-approve tool calls.
        disable_tool_auto_approval=True,
    )
