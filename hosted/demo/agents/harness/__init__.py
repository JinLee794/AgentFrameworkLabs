# Copyright (c) Microsoft. All rights reserved.

"""The "Azure sandwich" harness coding agent.

A self-contained agent package:

    agent.py         build() — wires the harness (bottom -> top)
    instructions.py  the system prompt
    history.py       Cosmos-backed chat history for this agent
"""

from .agent import build

__all__ = ["build"]
