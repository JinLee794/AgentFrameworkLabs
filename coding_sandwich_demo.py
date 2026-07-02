# Copyright (c) Microsoft. All rights reserved.

"""Demo: the "Microsoft/Azure sandwich" coding agent.

Runs two coding turns, then rebuilds the agent from scratch (a simulated process
restart) with the *same session id* to prove the conversation was persisted to
Azure Cosmos DB by the Agent Framework wrapper.

    az login
    python coding_sandwich_demo.py

If COSMOS_ENDPOINT is not set, history stays in-memory and the "restart" step
will show an empty history (expected) — set it to see durable persistence.
"""

import asyncio
import os

from dotenv import load_dotenv

from entities.coding_sandwich.agent import build_agent

load_dotenv()

SESSION_ID = "demo-session-001"


async def main() -> None:
    backend = "Cosmos DB" if os.getenv("COSMOS_ENDPOINT") else "in-memory (set COSMOS_ENDPOINT for durability)"
    print(f"History backend: {backend}\n")

    agent = build_agent()
    session = agent.create_session(session_id=SESSION_ID)

    print("── Turn 1 ─────────────────────────────────────────────")
    r1 = await agent.run(
        "Create calc.py with an add(a, b) function that returns their sum.",
        session=session,
    )
    print(r1.text, "\n")

    print("── Turn 2 ─────────────────────────────────────────────")
    r2 = await agent.run(
        "Add a subtract(a, b) function to calc.py, then run a quick test that prints add(2,3) and subtract(5,2).",
        session=session,
    )
    print(r2.text, "\n")

    # Simulated restart: brand-new agent + session object, same session id.
    print("── Simulated restart: recalling history ───────────────")
    fresh_agent = build_agent()
    fresh_session = fresh_agent.create_session(session_id=SESSION_ID)
    r3 = await fresh_agent.run(
        "Without re-reading the files, what functions did we add to calc.py in this conversation?",
        session=fresh_session,
    )
    print(r3.text)


if __name__ == "__main__":
    asyncio.run(main())
