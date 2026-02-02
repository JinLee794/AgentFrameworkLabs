# SRE Agent Demo Data

This folder contains realistic dummy data for demonstrating the Azure SRE Agent capabilities.

## Files

| File | Description |
|------|-------------|
| `server_metrics.csv` | Time-series metrics (CPU, memory, disk, network) for 6 servers over 30 minutes |
| `application_logs.json` | Sample application logs with errors, warnings, and info messages |
| `active_alerts.json` | Currently firing alerts from Azure Monitor and Application Insights |
| `incidents.json` | Active and recent incidents with timelines and impact data |
| `infrastructure_inventory.json` | Server inventory with specs, services, and team ownership |
| `on_call_schedule.json` | On-call rotation and escalation policies |

## Demo Scenario

The data represents a **database performance degradation incident**:

1. **Root Cause**: `vm-db-01` (primary database) experiencing high CPU (94.7%) and memory (88.5%)
2. **Impact**: Connection pool exhaustion affecting `order-service` and `inventory-service`
3. **Cascading Effects**: Rate limiting on API gateway, cache memory pressure
4. **Response**: Automated failover initiated, SRE team investigating

## Usage

Upload these files to Azure AI Foundry as grounding data, or use them with the Agent Framework tools:

```python
import json

# Load alerts for agent context
with open("demo-data/active_alerts.json") as f:
    alerts = json.load(f)

# Use in agent tool
def get_active_alerts() -> dict:
    """Get all currently firing alerts."""
    return alerts
```

## Workflow Integration

See `sre-incident-workflow.yaml` in the parent folder for an automated incident response workflow that uses GitHub MCP and Teams notifications.
