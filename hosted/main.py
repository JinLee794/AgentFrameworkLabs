# Copyright (c) Microsoft. All rights reserved.

"""Entrypoint for the Foundry-hosted agent runtime.

Serves the agent named by ``HOSTED_AGENT_NAME`` (default: ``coding``) over the
Responses protocol. The application lives in the :mod:`hosted_agent` package;
add new agents under ``hosted_agent/agents/`` — see that package's docstring.

Run locally:  ``python main.py``  (uses .env; ``az login`` for credentials)
Hosted:       Foundry invokes this module; the container's managed identity auths.
"""

from hosted_agent.runtime.server import build_server

server = build_server()


if __name__ == "__main__":
    server.run()
