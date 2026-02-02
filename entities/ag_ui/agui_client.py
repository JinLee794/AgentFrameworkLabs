"""AG-UI client with tool event handling."""

import asyncio
import os

from agent_framework import ChatAgent, ToolCallContent, ToolResultContent
from agent_framework_ag_ui import AGUIChatClient

async def main():
    """Main client loop with tool event display."""
    server_url = os.environ.get("AGUI_SERVER_URL", "http://127.0.0.1:8888/")
    print(f"Connecting to AG-UI server at: {server_url}
")

    # Create AG-UI chat client
    chat_client = AGUIChatClient(server_url=server_url)

    # Create agent with the chat client
    agent = ChatAgent(
        name="ClientAgent",
        chat_client=chat_client,
        instructions="You are a helpful assistant.",
    )

    # Get a thread for conversation continuity
    thread = agent.get_new_thread()

    try:
        while True:
            message = input("
User (:q or quit to exit): ")
            if not message.strip():
                continue

            if message.lower() in (":q", "quit"):
                break

            print("
Assistant: ", end="", flush=True)
            async for update in agent.run_stream(message, thread=thread):
                # Display text content (cyan)
                if update.text:
                    print(f"[96m{update.text}[0m", end="", flush=True)

                # Display tool calls and results
                for content in update.contents:
                    if isinstance(content, ToolCallContent):
                        print(f"
[95m[Calling tool: {content.name}][0m")
                    elif isinstance(content, ToolResultContent):
                        result_text = content.result if isinstance(content.result, str) else str(content.result)
                        print(f"[94m[Tool result: {result_text[:100]}...][0m")

            print("
")

    except KeyboardInterrupt:
        print("

Exiting...")
    except Exception as e:
        print(f"
[91mError: {e}[0m")

if __name__ == "__main__":
    asyncio.run(main())