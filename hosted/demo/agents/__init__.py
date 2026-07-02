# Copyright (c) Microsoft. All rights reserved.

"""Registry of hostable agents.

Each agent is a self-contained package under ``hosted_agent/agents/<name>/`` that
exposes a zero-argument ``build()`` returning something ``ResponsesHostServer``
can serve (any Agent Framework agent — a ``ChatAgent``, a ``create_harness_agent``
harness, a workflow, …).

To add another agent:

1. Create ``hosted_agent/agents/<name>/`` with an ``__init__.py`` that exposes
   ``build()`` (keep its instructions, history, and options alongside it).
2. Register it in :data:`AGENT_BUILDERS` below.
3. Select it at runtime with ``HOSTED_AGENT_NAME=<name>``.
"""

from collections.abc import Callable
from typing import Any

from . import harness

# name -> zero-arg builder returning a hostable agent.
AGENT_BUILDERS: dict[str, Callable[[], Any]] = {
    "harness": harness.build,
}

DEFAULT_AGENT = "harness"


def available_agents() -> list[str]:
    """Names of all registered agents."""
    return sorted(AGENT_BUILDERS)


def build_agent(name: str | None = None) -> Any:
    """Build the named agent (default: :data:`DEFAULT_AGENT`)."""
    key = name or DEFAULT_AGENT
    try:
        builder = AGENT_BUILDERS[key]
    except KeyError:
        raise ValueError(
            f"Unknown agent {key!r}. Registered agents: {available_agents()}."
        ) from None
    return builder()
