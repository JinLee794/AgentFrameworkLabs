# Lab 1a: Azure Cosmos DB Vector Store Integration - Specification

**Status:** Draft  
**Duration:** 20-25 minutes  
**Depends On:** Lab 1 (Agent Basics)

---

## TL;DR - What This Lab Teaches

| Concept | What It Is | Why It Matters |
|---------|------------|----------------|
| **Vector Store** | Database that stores text as numbers (embeddings) | Enables "find similar content" instead of exact keyword match |
| **Embeddings** | AI-generated numerical representation of text | "Database performance issue" ≈ "DB slowdown" (semantically similar) |
| **RAG** | Retrieval Augmented Generation | Agent retrieves relevant docs before answering → better, grounded responses |

**The "Aha!" Moment:** Ask the agent "How do I fix a slow database?" → It searches 3 runbooks, finds the right one, and gives you step-by-step instructions from your org's actual documentation.

---

## Learning Objectives

By the end of this lab, participants will understand:

1. **What** vector search does (semantic similarity vs. keyword matching)
2. **How** to connect an Agent Framework agent to Cosmos DB
3. **Why** RAG improves agent responses (grounded in your data)

---

## Architecture (Simplified)

```
┌─────────────────────────────────────────────────────────┐
│                    Your Agent                           │
│  "How do I fix a slow database?"                        │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              search_knowledge_base() Tool               │
│  1. Convert question → embedding (numbers)              │
│  2. Find similar documents in Cosmos DB                 │
│  3. Return: "runbook-db-performance.md" (95% match)     │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 Azure Cosmos DB                         │
│  📄 runbook-db-performance.md  [0.23, 0.87, ...]       │
│  📄 playbook-sev1-response.md  [0.45, 0.12, ...]       │
│  📄 guide-query-optimization.md [0.31, 0.76, ...]      │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- ✅ Lab 1 completed
- ✅ Azure subscription
- ✅ Azure AI Foundry project with GPT-4o deployed

---

## Part 1: Setup Cosmos DB (5 min)

### One-Click Deployment

Run the setup script - it creates everything you need:

```bash
# From the lab folder
./scripts/setup-cosmosdb.sh
```

This creates:
- Serverless Cosmos DB account (~$1-5/month for demo use)
- Database with vector search enabled
- Container ready for your documents

### What's Happening Under the Hood

| Component | Purpose |
|-----------|---------|
| **Serverless mode** | Pay only when you query (pennies for demos) |
| **DiskANN vector index** | Fast similarity search over embeddings |
| **Partition key: /category** | Organize docs by type (runbook, playbook, guide) |

---

## Part 2: Load Sample Data (5 min)

### Three Documents, One Concept

We'll load just **3 documents** to demonstrate the concept clearly:

| Document | What It Contains | When Agent Should Find It |
|----------|------------------|---------------------------|
| `runbook-db-performance.md` | Database troubleshooting steps | "slow database", "high CPU on db" |
| `playbook-sev1-response.md` | Incident response protocol | "production down", "SEV1 process" |
| `guide-query-optimization.md` | Query tuning tips | "slow queries", "optimize SQL" |

### Simple Document Schema

```python
{
    "id": "runbook-db-performance",
    "category": "runbook",           # Partition key
    "title": "Database Performance Runbook",
    "content": "Step 1: Check CPU usage...",  # The actual text
    "contentVector": [0.23, 0.87, ...],       # 1536 numbers representing the content
}
```

**That's it.** The `contentVector` is what makes semantic search work.

### Load Data with One Command

```bash
# Load all 3 documents (generates embeddings automatically)
python scripts/load_knowledge_base.py
```

Output:
```
Loading demo-data/knowledge/runbook-db-performance.md...
  → Generated embedding (1536 dimensions)
  → Uploaded to Cosmos DB ✓
Loading demo-data/knowledge/playbook-sev1-response.md...
  → Generated embedding (1536 dimensions)
  → Uploaded to Cosmos DB ✓
Loading demo-data/knowledge/guide-query-optimization.md...
  → Generated embedding (1536 dimensions)
  → Uploaded to Cosmos DB ✓
Done! 3 documents loaded.
```

---

## Part 3: The RAG Tool (5 min)

### One Function = Vector Search

```python
def search_knowledge_base(
    query: Annotated[str, Field(description="What to search for")]
) -> list[dict]:
    """Search the knowledge base for relevant runbooks and guides."""
    
    # Step 1: Convert question to numbers (embedding)
    query_embedding = generate_embedding(query)
    
    # Step 2: Find similar documents in Cosmos DB
    results = container.query_items(
        query="""
            SELECT TOP 3 c.title, c.content, c.category
            FROM c
            ORDER BY VectorDistance(c.contentVector, @embedding)
        """,
        parameters=[{"name": "@embedding", "value": query_embedding}]
    )
    
    return list(results)
```

### Add to Your Agent

```python
agent = ChatAgent(
    chat_client=chat_client,
    name="SRE-Assistant",
    instructions="You are an SRE assistant. Use search_knowledge_base to find relevant runbooks before answering.",
    tools=[get_system_metrics, search_knowledge_base],  # ← Added!
)
```

---

## Part 4: See It Work (5 min)

### Demo Script

```python
# Without RAG - agent makes up generic advice
response = await agent.run("How do I fix a slow database?")
# → Generic response about "check indexes, optimize queries..."

# With RAG - agent uses YOUR runbook
response = await agent_with_rag.run("How do I fix a slow database?")
# → "According to the Database Performance Runbook, you should:
#    1. Check Azure Monitor metrics dashboard
#    2. Identify long-running queries using sp_who2
#    3. Kill blocking queries with KILL <spid>
#    ..."
```

### The "Aha!" Moment

| Query | Keyword Search Would Find | Vector Search Finds |
|-------|---------------------------|---------------------|
| "db is slow" | ❌ Nothing (no exact match) | ✅ runbook-db-performance.md |
| "production is down" | ❌ Nothing | ✅ playbook-sev1-response.md |
| "SQL taking forever" | ❌ Nothing | ✅ guide-query-optimization.md |

**Vector search understands meaning, not just keywords.**

---

## Part 5: Bonus - Compare with Data Agent (Optional, 5 min)

Azure AI Foundry offers a built-in **Cosmos DB Data Agent** that connects to your database automatically.

### Quick Comparison

| | Custom RAG (This Lab) | Cosmos DB Data Agent |
|-|----------------------|----------------------|
| **Setup** | Write the tool yourself | Point-and-click config |
| **Search Type** | Semantic (vector) | SQL-based |
| **"slow database"** | ✅ Finds similar content | ⚠️ Needs exact keywords |
| **Control** | Full (middleware, caching) | Limited |
| **Best For** | Production apps | Quick prototypes |

### When to Use What

- **Use Custom RAG** when you need semantic search and full control
- **Use Data Agent** when you want fast setup and SQL queries are sufficient

---

## Cleanup

```bash
# Delete everything when done
az group delete --name rg-agent-labs --yes --no-wait
```

---

## Summary: What You Learned

| Concept | Key Insight |
|---------|-------------|
| **Vector Store** | Store text as numbers for similarity search |
| **Embedding** | AI turns "slow database" → `[0.23, 0.87, ...]` |
| **RAG** | Agent retrieves docs BEFORE answering → grounded responses |
| **Cosmos DB** | Serverless + DiskANN = cheap, fast vector search |

**One-liner:** RAG makes your agent use YOUR documentation instead of making things up.

---

## Files Delivered

| File | Purpose |
|------|---------|
| `lab1a-cosmosdb-vector-store.ipynb` | Hands-on notebook |
| `scripts/setup-cosmosdb.sh` | One-click Cosmos DB setup |
| `scripts/load_knowledge_base.py` | Load sample data |
| `demo-data/knowledge/*.md` | 3 sample documents |

---

## Next Steps

- **Lab 2:** Build an SRE agent that combines metrics + knowledge base for incident response
- **Lab 3:** Add observability and middleware to production-ready agents

---

## Appendix A: Full Provisioning Commands (Reference)

<details>
<summary>Click to expand Azure CLI commands</summary>

```bash
# Variables
RESOURCE_GROUP="rg-agent-labs"
LOCATION="eastus"
COSMOS_ACCOUNT="cosmos-sre-agent-dev"
DATABASE_NAME="sre-data"
CONTAINER_NAME="sre-knowledge"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Cosmos DB account (Serverless)
az cosmosdb create \
    --name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --locations regionName=$LOCATION \
    --capabilities EnableServerless \
    --default-consistency-level Session

# Create database
az cosmosdb sql database create \
    --account-name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --name $DATABASE_NAME

# Create container with vector index
az cosmosdb sql container create \
    --account-name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --database-name $DATABASE_NAME \
    --name $CONTAINER_NAME \
    --partition-key-path "/category" \
    --idx @infra/vector-index-policy.json
```

</details>

---

## Appendix B: Vector Index Policy (Reference)

<details>
<summary>Click to expand JSON configuration</summary>

**infra/vector-index-policy.json:**
```json
{
    "indexingMode": "consistent",
    "automatic": true,
    "includedPaths": [{ "path": "/*" }],
    "excludedPaths": [{ "path": "/contentVector/*" }],
    "vectorIndexes": [
        {
            "path": "/contentVector",
            "type": "diskANN"
        }
    ]
}
```

**Container vector policy:**
```json
{
    "vectorEmbeddings": [
        {
            "path": "/contentVector",
            "dataType": "float32",
            "distanceFunction": "cosine",
            "dimensions": 1536
        }
    ]
}
```

</details>

---

## Appendix C: Environment Variables

Add to your `.env` file:

```bash
# Cosmos DB (from setup script output)
COSMOS_ENDPOINT=https://<your-account>.documents.azure.com:443/
COSMOS_DATABASE=sre-data
COSMOS_CONTAINER=sre-knowledge
```

---

## References

| Resource | URL |
|----------|-----|
| Cosmos DB Vector Search | https://learn.microsoft.com/azure/cosmos-db/nosql/vector-search |
| Agent Framework RAG | https://learn.microsoft.com/agent-framework/user-guide/agents/agent-tools |
| Cost Calculator | https://azure.microsoft.com/pricing/details/cosmos-db/
