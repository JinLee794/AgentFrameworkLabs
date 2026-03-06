#!/usr/bin/env python3
"""
Lab 1a: Load Knowledge Base into Azure Cosmos DB

This script reads markdown files from demo-data/knowledge/ and uploads them
to Cosmos DB with generated embeddings for vector search.

Usage:
    python scripts/load_knowledge_base.py

Requirements:
    - Azure Cosmos DB account with vector search enabled (run setup-cosmosdb.sh first)
    - Azure AI Foundry project with embedding model deployed
    - Environment variables in .env file
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


def check_environment():
    """Check that required environment variables are set."""
    required = ["COSMOS_ENDPOINT", "PROJECT_ENDPOINT"]
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease set these in your .env file.")
        print("Run './scripts/setup-cosmosdb.sh' to create the Cosmos DB resources.")
        sys.exit(1)


def get_cosmos_container():
    """Initialize Cosmos DB client and return container."""
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential
    
    endpoint = os.getenv("COSMOS_ENDPOINT")
    database_name = os.getenv("COSMOS_DATABASE", "sre-data")
    container_name = os.getenv("COSMOS_CONTAINER", "sre-knowledge")
    
    print(f"Connecting to Cosmos DB...")
    print(f"  Endpoint: {endpoint}")
    print(f"  Database: {database_name}")
    print(f"  Container: {container_name}")
    
    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)
    
    print("✓ Connected to Cosmos DB\n")
    return container


def get_embedding_client():
    """Initialize Azure OpenAI client for embeddings."""
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    
    # Use Azure AI Foundry project endpoint for embeddings
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    
    # Extract the base endpoint (remove /v1 if present)
    if project_endpoint.endswith("/v1"):
        base_endpoint = project_endpoint
    else:
        base_endpoint = project_endpoint.rstrip("/")
    
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, 
        "https://cognitiveservices.azure.com/.default"
    )
    
    # Use the inference endpoint for embeddings
    # AI Foundry projects expose OpenAI-compatible endpoints
    client = AzureOpenAI(
        azure_endpoint=base_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )
    
    print("✓ Connected to Azure OpenAI for embeddings\n")
    return client


def generate_embedding(client, text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Generate embedding vector for text."""
    # Truncate if too long (max ~8000 tokens for embedding models)
    if len(text) > 30000:
        text = text[:30000]
    
    response = client.embeddings.create(
        model=model,
        input=text,
        dimensions=1536  # Match the vector index configuration
    )
    
    return response.data[0].embedding


def parse_markdown_frontmatter(content: str) -> tuple[dict, str]:
    """Extract frontmatter metadata from markdown content."""
    metadata = {}
    body = content
    
    # Check for YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            body = parts[2].strip()
            
            # Parse simple key: value pairs
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace(" ", "_")
                    value = value.strip()
                    
                    # Handle comma-separated lists
                    if "," in value:
                        value = [v.strip() for v in value.split(",")]
                    
                    metadata[key] = value
    
    return metadata, body


def extract_title(content: str) -> str:
    """Extract title from first H1 heading."""
    for line in content.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def load_knowledge_documents(knowledge_dir: Path) -> list[dict]:
    """Load all markdown files from the knowledge directory."""
    documents = []
    
    for md_file in sorted(knowledge_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue
        
        print(f"Loading {md_file.name}...")
        
        content = md_file.read_text(encoding="utf-8")
        metadata, body = parse_markdown_frontmatter(content)
        
        # Determine category from filename or metadata
        filename = md_file.stem
        if "category" in metadata:
            category = metadata["category"]
        elif filename.startswith("runbook-"):
            category = "runbook"
        elif filename.startswith("playbook-"):
            category = "playbook"
        elif filename.startswith("guide-"):
            category = "guide"
        elif filename.startswith("postmortem-"):
            category = "postmortem"
        else:
            category = "general"
        
        # Generate stable ID from filename
        doc_id = filename
        
        doc = {
            "id": doc_id,
            "category": category,
            "title": extract_title(content) or metadata.get("title", filename),
            "content": body,
            "tags": metadata.get("tags", []),
            "severity": metadata.get("severity", []),
            "services": metadata.get("services", []),
            "source_file": md_file.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        documents.append(doc)
        print(f"  ✓ Parsed: {doc['title']} ({category})")
    
    return documents


def upload_documents(container, embedding_client, documents: list[dict]):
    """Upload documents with embeddings to Cosmos DB."""
    print(f"\nUploading {len(documents)} documents to Cosmos DB...\n")
    
    for i, doc in enumerate(documents, 1):
        print(f"[{i}/{len(documents)}] Processing: {doc['title']}")
        
        # Generate embedding from title + content
        text_to_embed = f"{doc['title']}\n\n{doc['content']}"
        print(f"  → Generating embedding ({len(text_to_embed):,} chars)...")
        
        try:
            embedding = generate_embedding(embedding_client, text_to_embed)
            doc["contentVector"] = embedding
            print(f"  → Generated embedding ({len(embedding)} dimensions)")
        except Exception as e:
            print(f"  ⚠ Embedding failed: {e}")
            print(f"    Skipping document...")
            continue
        
        # Upsert to Cosmos DB
        print(f"  → Uploading to Cosmos DB...")
        try:
            container.upsert_item(doc)
            print(f"  ✓ Uploaded: {doc['id']}")
        except Exception as e:
            print(f"  ❌ Upload failed: {e}")
        
        print()


def verify_upload(container, expected_count: int):
    """Verify documents were uploaded correctly."""
    print("Verifying upload...")
    
    # Count documents
    query = "SELECT VALUE COUNT(1) FROM c"
    result = list(container.query_items(query, enable_cross_partition_query=True))
    actual_count = result[0] if result else 0
    
    print(f"  Documents in container: {actual_count}")
    
    if actual_count >= expected_count:
        print("✓ Upload verification passed!\n")
    else:
        print(f"⚠ Expected {expected_count}, found {actual_count}\n")
    
    # List documents
    query = "SELECT c.id, c.category, c.title FROM c"
    docs = list(container.query_items(query, enable_cross_partition_query=True))
    
    print("Documents loaded:")
    for doc in docs:
        print(f"  - [{doc['category']}] {doc['title']}")
    print()


def main():
    """Main entry point."""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║       Lab 1a: Load Knowledge Base into Cosmos DB           ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Check environment
    check_environment()
    
    # Find knowledge directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    knowledge_dir = repo_root / "demo-data" / "knowledge"
    
    if not knowledge_dir.exists():
        print(f"❌ Knowledge directory not found: {knowledge_dir}")
        sys.exit(1)
    
    print(f"Loading documents from: {knowledge_dir}\n")
    
    # Load documents
    documents = load_knowledge_documents(knowledge_dir)
    
    if not documents:
        print("❌ No documents found to load")
        sys.exit(1)
    
    print(f"\n✓ Loaded {len(documents)} documents\n")
    
    # Initialize clients
    container = get_cosmos_container()
    embedding_client = get_embedding_client()
    
    # Upload with embeddings
    upload_documents(container, embedding_client, documents)
    
    # Verify
    verify_upload(container, len(documents))
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    Load Complete!                          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("Next steps:")
    print("  1. Open lab1a-cosmosdb-vector-store.ipynb")
    print("  2. Run the cells to test vector search")
    print()


if __name__ == "__main__":
    main()
