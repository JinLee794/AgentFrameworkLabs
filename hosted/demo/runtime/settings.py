# Copyright (c) Microsoft. All rights reserved.

"""Runtime-level environment configuration (shared by all agents).

Read lazily (inside factories, not at import) so importing the package never
requires a fully populated environment.

Environment (.env):
    FOUNDRY_PROJECT_ENDPOINT   Foundry project all agents connect to (required).
    HOSTED_AGENT_NAME          Which registered agent to serve (default: harness).

Per-agent settings (model deployment, Cosmos endpoint, …) live with the agent
that owns them under ``hosted_agent/agents/<name>/``.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    try:
        return os.environ[name]
    except KeyError:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            "Set it in .env (see README) before starting the agent."
        ) from None


def foundry_project_endpoint() -> str:
    """Foundry project endpoint the chat client connects to."""
    return require_env("FOUNDRY_PROJECT_ENDPOINT")


def hosted_agent_name() -> str:
    """Name of the registered agent to serve (see :mod:`hosted_agent.agents`)."""
    return os.getenv("HOSTED_AGENT_NAME", "harness")
