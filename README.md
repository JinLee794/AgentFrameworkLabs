# Agent Framework Labs

Hands-on labs for building AI agents with the **Microsoft Agent Framework** and exploring **Azure SRE Agent** capabilities.

## What You'll Learn

- Building conversational agents with tool-calling capabilities
- Orchestrating multi-agent workflows (incident response, triage)
- Integrating agents with AG-UI for interactive web experiences
- Working with Azure SRE Agent for automated site reliability operations

## Labs

| Lab | Description |
|-----|-------------|
| [lab1-agent-basics.ipynb](lab1-agent-basics.ipynb) | Core Agent Framework concepts and tool definitions |
| [lab2-sre-agent-basics.ipynb](lab2-sre-agent-basics.ipynb) | Azure SRE Agent fundamentals |
| [lab3-sre-extensibility.ipynb](lab3-sre-extensibility.ipynb) | Extending Azure SRE Agent with custom subagents |
| [lab-agui-integration.ipynb](lab-agui-integration.ipynb) | AG-UI protocol for streaming agent UIs |

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.sample .env  # Add your PROJECT_ENDPOINT from Azure AI Foundry
```

## Running Agents

### VS Code AI Toolkit + DevUI

The [AI Toolkit extension](https://marketplace.visualstudio.com/items?itemName=ms-windows-ai-studio.windows-ai-studio) provides a local development UI for testing agents.

```bash
# Launch DevUI (discovers agents in workspace)
devui --port 8080 entities
```

Or use the VS Code task: **Start Agent Server (DevUI Discovery)**

### Direct Server

```bash
python entities/ag_ui/agui_server.py  # Starts AG-UI server on port 8888
```

## Azure SRE Agent (Portal)

For production SRE scenarios, use **Azure SRE Agent** in the Azure Portal:

1. Navigate to **Azure SRE Agent** in your subscription
2. Configure **Subagents** using YAML definitions (see [db-performance-subagent.yaml](db-performance-subagent.yaml))
3. Set up **alert triggers** to automatically invoke agents on incidents
4. Monitor agent actions and incident timelines in the dashboard

The [sre-incident-workflow.yaml](sre-incident-workflow.yaml) demonstrates multi-agent orchestration with GitHub and Teams integrations.

## Demo Data

The [demo-data/](demo-data/) folder contains realistic metrics, logs, and alerts for a database performance incident scenario.

## Requirements

- Python 3.11+
- Azure subscription with OpenAI access
- VS Code with AI Toolkit extension (optional)
