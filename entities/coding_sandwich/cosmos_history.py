# Copyright (c) Microsoft. All rights reserved.

"""Cosmos DB-backed chat history for the Agent Framework wrapper.

This is the *top slice* of the customer's "Microsoft/Azure sandwich":

    Foundry model  ->  coding engine (tools)  ->  Agent Framework wrapper
                                                   └── owns the conversation
                                                       and persists it to Cosmos

The Agent Framework owns the conversation via a history provider. By subclassing
``BaseHistoryProvider`` we swap the built-in in-memory store for Azure Cosmos DB,
so every turn survives process restarts and can be shared across hosts (or read
back by an external coding engine such as Codex / Cursor).

One Cosmos item per session:

    {
        "id":        "<session_id>",
        "sessionId": "<session_id>",   # partition key
        "messages":  [ <Message.to_dict()>, ... ],
        "updatedAt": "2026-07-01T12:00:00+00:00"
    }
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, ClassVar, Sequence

from agent_framework import BaseHistoryProvider
from agent_framework._types import Message


def _sanitize_for_history(messages: Sequence[Message]) -> list[Message]:
    """Keep only the durable conversation; drop the ephemeral tool transcript.

    Reasoning-model + Responses-API outputs carry server-side item IDs on
    ``text_reasoning`` (``rs_...``) and ``function_call`` (``fc_...``) content.
    Replaying those as input trips the API with "Duplicate item found with id
    ...". They're also not really *chat history* — they're the model's internal
    scratchpad and live tool wiring, which is re-executed fresh each turn.

    So we persist only the conversation the user would recognize: user/assistant
    text. Tool calls still run live within a turn; across turns the model sees
    the assistant's text summaries. Message IDs are cleared so no ``msg_`` id can
    collide on replay either.
    """
    drop_types = {
        "text_reasoning",
        "function_call",
        "function_result",
        "function_approval_request",
        "function_approval_response",
    }
    cleaned: list[Message] = []
    for message in messages:
        kept = [c for c in message.contents if getattr(c, "type", None) not in drop_types]
        if not kept:
            continue
        cleaned.append(
            Message(
                message.role,
                contents=kept,
                author_name=message.author_name,
            )
        )
    return cleaned


class CosmosHistoryProvider(BaseHistoryProvider):
    """Persist Agent Framework chat history to Azure Cosmos DB.

    The base class drives the lifecycle: it calls :meth:`get_messages` before a
    run (to load prior context) and :meth:`save_messages` after a run (with the
    new input/output messages for that turn). We only implement those two hooks.

    When no ``endpoint`` (or ``COSMOS_ENDPOINT``) is configured the provider runs
    in ``memory_only`` mode: history lives in the in-process cache for the life
    of the session, with identical reasoning-sanitization behavior but no durable
    storage. Configure Cosmos to make history survive restarts.

    Auth uses Microsoft Entra ID (``DefaultAzureCredential``) by default — no
    keys required if the identity has the Cosmos DB Built-in Data Contributor
    role. Pass an explicit ``credential`` to override.
    """

    DEFAULT_SOURCE_ID: ClassVar[str] = "cosmos_history"

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        database: str | None = None,
        container: str | None = None,
        credential: Any | None = None,
        source_id: str | None = None,
        load_messages: bool = True,
        store_inputs: bool = True,
        store_outputs: bool = True,
    ) -> None:
        super().__init__(
            source_id=source_id or self.DEFAULT_SOURCE_ID,
            load_messages=load_messages,
            store_inputs=store_inputs,
            store_outputs=store_outputs,
        )
        self._endpoint = endpoint or os.getenv("COSMOS_ENDPOINT")
        self._memory_only = not self._endpoint
        self._database_name = database or os.getenv("COSMOS_CHAT_DATABASE", "agent-chat")
        self._container_name = container or os.getenv("COSMOS_CHAT_CONTAINER", "sessions")
        self._credential = credential
        self._client: Any = None
        self._container: Any = None
        # In-process mirror of each session's messages so we avoid a Cosmos
        # round-trip on every append; Cosmos remains the durable source of truth.
        self._cache: dict[str, list[Message]] = {}

    # ------------------------------------------------------------------ #
    # Cosmos plumbing
    # ------------------------------------------------------------------ #
    async def _ensure_container(self) -> Any:
        """Lazily create the client/database/container on first use."""
        if self._container is not None:
            return self._container

        # Imported lazily so simply importing this module never requires the
        # Cosmos SDK or credentials (keeps DevUI discovery cheap).
        from azure.cosmos import PartitionKey
        from azure.cosmos.aio import CosmosClient

        credential = self._credential
        if credential is None:
            from azure.identity.aio import DefaultAzureCredential

            credential = DefaultAzureCredential()

        try:
            self._client = CosmosClient(self._endpoint, credential=credential)
            database = await self._client.create_database_if_not_exists(self._database_name)
            self._container = await database.create_container_if_not_exists(
                id=self._container_name,
                partition_key=PartitionKey(path="/sessionId"),
            )
        except Exception as exc:  # noqa: BLE001 - collapse noisy SDK stack into guidance
            if self._client is not None:
                await self._client.close()
                self._client = None
            raise RuntimeError(
                f"Cannot reach Cosmos DB at {self._endpoint!r}: {exc}. "
                "Verify COSMOS_ENDPOINT points to a real account you have "
                "'Cosmos DB Built-in Data Contributor' access to, or unset "
                "COSMOS_ENDPOINT to run with in-memory history."
            ) from None
        return self._container

    # ------------------------------------------------------------------ #
    # BaseHistoryProvider hooks
    # ------------------------------------------------------------------ #
    async def get_messages(self, session_id: str | None, **kwargs: Any) -> list[Message]:
        """Load a session's full history (from cache, falling back to Cosmos)."""
        if not session_id:
            return []
        if session_id in self._cache:
            return list(self._cache[session_id])
        if self._memory_only:
            self._cache[session_id] = []
            return []

        container = await self._ensure_container()
        try:
            item = await container.read_item(item=session_id, partition_key=session_id)
        except Exception:
            # Unknown session (or not yet created) -> empty history.
            self._cache[session_id] = []
            return []

        messages = [Message.from_dict(m) for m in item.get("messages", [])]
        self._cache[session_id] = messages
        return list(messages)

    async def save_messages(
        self, session_id: str | None, messages: Sequence[Message], **kwargs: Any
    ) -> None:
        """Append this turn's new messages and upsert the session to Cosmos."""
        if not session_id or not messages:
            return

        new_messages = _sanitize_for_history(messages)
        if not new_messages:
            return

        # Make sure the cache is warm (handles a fresh process mid-session).
        if session_id not in self._cache:
            await self.get_messages(session_id)

        self._cache[session_id].extend(new_messages)

        if self._memory_only:
            return

        container = await self._ensure_container()
        await container.upsert_item(
            {
                "id": session_id,
                "sessionId": session_id,
                "messages": [m.to_dict() for m in self._cache[session_id]],
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def close(self) -> None:
        """Close the underlying Cosmos client (optional cleanup)."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._container = None
