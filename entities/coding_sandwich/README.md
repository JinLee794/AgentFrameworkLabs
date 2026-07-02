# Coding Sandwich — Foundry model + coding engine + Cosmos chat history

A self-contained recreation of the customer's **"Microsoft/Azure sandwich"**:
host the model in Foundry, drive it with a coding engine, and wrap the whole
thing with Microsoft Agent Framework so conversation history lives in Cosmos DB.

```
┌────────────────────────────────────────────────────────────┐
│  Agent Framework wrapper  (chat history -> Azure Cosmos DB) │  ← top slice
├────────────────────────────────────────────────────────────┤
│  Coding engine tools      (Codex / Cursor stand-in)         │  ← middle slice
├────────────────────────────────────────────────────────────┤
│  Foundry-hosted model     (AzureOpenAIChatClient)           │  ← bottom slice
└────────────────────────────────────────────────────────────┘
```

## Files

| File | Slice | Purpose |
| --- | --- | --- |
| `agent.py` | assembly | Builds the `Agent`: Foundry client + tools + history provider. Exports `agent` for DevUI. |
| `coding_tools.py` | middle | `list_files`, `read_file`, `write_file`, `run_python` — sandboxed, never raise, return structured text. |
| `cosmos_history.py` | top | `CosmosHistoryProvider(BaseHistoryProvider)` — persists each turn to Cosmos, one item per session. |

## Why this addresses the customer's pain

They saw Codex/Cursor tools "fail more often" once wrapped. Tool reliability
here comes from the **contract**, not the model:

- Every tool argument is typed and described, so the model gets a precise schema.
- Tools **never raise** — failures return `ERROR: ...` text the model can read
  and recover from, instead of aborting the turn.
- File access is confined to a sandbox workspace (path traversal is blocked).

Swap `coding_tools.py` for real Codex/Cursor calls later; the reliability
contract (typed args, structured errors, no raises) is the part worth keeping.

## Chat history in Cosmos

The Agent Framework owns the conversation through a history provider. Subclassing
`BaseHistoryProvider` swaps the built-in in-memory store for Cosmos DB — just
implement `get_messages` / `save_messages`. `Message.to_dict()` / `from_dict()`
handle JSON (de)serialization. Auth is keyless via `DefaultAzureCredential`.

Only the **conversation** (user + assistant text) is persisted. The model's
reasoning traces and the live tool-call transcript are stripped, because:

- They carry server-side item IDs (`rs_...`, `fc_...`) that the Responses API
  rejects as "Duplicate item found" when replayed on the next turn.
- They're the model's internal scratchpad / live wiring, not chat history —
  tool calls are re-executed fresh each turn.

When `COSMOS_ENDPOINT` is unset the provider runs in `memory_only` mode (same
sanitization, no durable storage), so the agent always runs.

## Model & API notes

- Uses `AzureOpenAIResponsesClient` (Responses API), which supports **codex**
  deployments (`gpt-5.x-codex`, `codex-mini`) plus `gpt-4o` / `gpt-5.x`. Codex
  models do **not** support Chat Completions.
- Requires `AZURE_OPENAI_API_VERSION` >= `2025-03-01-preview` (defaults to
  `2025-04-01-preview`).


## Run it

Configure `.env` (copy from `.env.sample`), then:

```bash
az login
# 1) Scripted demo — proves history survives a simulated restart:
python coding_sandwich_demo.py

# 2) Interactive — hosted in DevUI (discovers entities/coding_sandwich):
devui --port 8080 .
```

Without `COSMOS_ENDPOINT` set, history stays in-memory for the session and the
agent still runs — Cosmos is opt-in.
