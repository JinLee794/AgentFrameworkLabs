# Copyright (c) Microsoft. All rights reserved.

"""Shared hosting runtime.

Everything that is *not* specific to a single agent lives here: environment
configuration, the Foundry chat-client factory, and the Responses server that
selects and serves one registered agent. Individual agents live in
:mod:`hosted_agent.agents` — each in its own directory with its own instructions,
history, and options.
"""
