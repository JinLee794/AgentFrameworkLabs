# Copyright (c) Microsoft. All rights reserved.

"""Assemble the selected agent into a Foundry ``ResponsesHostServer``."""

from agent_framework_foundry_hosting import ResponsesHostServer

from ..agents import build_agent
from . import settings


def build_server() -> ResponsesHostServer:
    """Build the Responses host server for the agent named by ``HOSTED_AGENT_NAME``."""
    agent = build_agent(settings.hosted_agent_name())
    return ResponsesHostServer(agent)
