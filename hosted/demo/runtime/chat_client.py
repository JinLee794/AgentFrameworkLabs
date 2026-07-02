# Copyright (c) Microsoft. All rights reserved.

"""Shared ``FoundryChatClient`` factory.

All agents talk to the same Foundry project, so they share this factory. The
model is chosen by the agent (each agent owns its model choice), so it must be
passed explicitly.

Auth uses ``DefaultAzureCredential``: ``az login`` locally, or the container's
managed identity when hosted in Foundry.
"""

from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from . import settings


def build_chat_client(*, model: str) -> FoundryChatClient:
    """Build a Foundry chat client for the given model deployment."""
    return FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint(),
        model=model,
        credential=DefaultAzureCredential(),
        allow_preview=True,  # codex deployments are preview models
    )
