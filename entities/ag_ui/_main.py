# Copyright (c) Microsoft. All rights reserved.
"""SRE Agent for Agent Framework - HTTP Server Mode.

This module wraps the SRE Agent as an HTTP server for use with
AI Toolkit Agent Inspector and production deployments.
"""

import os
from typing import Annotated

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv
from pydantic import Field

# Load environment variables from .env file
load_dotenv()

# Configuration - loaded from .env file
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")

if not PROJECT_ENDPOINT or PROJECT_ENDPOINT.startswith("https://<"):
    raise ValueError("Please set PROJECT_ENDPOINT in your .env file (copy from .env.sample)")


# Define the SRE tool using type hints
def get_system_metrics(
    server_name: Annotated[str, Field(description="The name of the server (e.g., vm-prod-01, vm-db-01)")],
    metric_type: Annotated[str, Field(description="The type of metric: cpu, memory, disk, network_in, or all")],
) -> dict:
    """
    Retrieves current system metrics (CPU, memory, disk, network) for a specified server.
    Use this to diagnose performance issues.
    """
    # Simulated metrics data
    metrics_data = {
        "vm-prod-01": {"cpu": 78.5, "memory": 62.3, "disk": 45.0, "network_in": 125.6},
        "vm-prod-02": {"cpu": 23.1, "memory": 41.2, "disk": 72.8, "network_in": 89.3},
        "vm-db-01": {"cpu": 91.2, "memory": 88.5, "disk": 55.0, "network_in": 234.1},
    }

    server = metrics_data.get(server_name, {})
    if not server:
        return {"error": f"Server {server_name} not found"}

    if metric_type == "all":
        return {"server": server_name, "metrics": server}

    value = server.get(metric_type)
    if value is None:
        return {"error": f"Metric {metric_type} not found for {server_name}"}

    return {
        "server": server_name,
        "metric": metric_type,
        "value": value,
        "unit": "%" if metric_type != "network_in" else "Mbps",
    }


# Initialize credential for Azure RBAC authentication
credential = DefaultAzureCredential()

# Create the Azure AI Agent Client
chat_client = AzureAIAgentClient(
    project_endpoint=PROJECT_ENDPOINT,
    credential=credential,
    model_deployment_name="gpt-5.1",
)

# Create the SRE Agent
agent = ChatAgent(
    chat_client=chat_client,
    name="SRE-Assistant",
    description="An expert Site Reliability Engineer assistant for diagnosing infrastructure issues",
    instructions="""
You are an expert Site Reliability Engineer assistant. Your role is to help diagnose 
and troubleshoot infrastructure issues.

When analyzing server issues:
1. First gather relevant metrics using the get_system_metrics tool
2. Analyze the data for anomalies (CPU > 80%, Memory > 85%, Disk > 90% are concerning)
3. Provide clear, actionable recommendations

Be concise but thorough. Format output with clear sections.
""",
    tools=[get_system_metrics],
)


def main():
    """Launch the SRE Agent in DevUI server mode."""
    import logging

    from agent_framework.devui import serve

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    logger.info("Starting SRE Assistant Agent")
    logger.info("Available at: http://localhost:8080")
    logger.info("Entity ID: agent_SRE-Assistant")

    # Launch server with the agent
    serve(entities=[agent], port=8080, auto_open=False)


if __name__ == "__main__":
    main()
