# Copyright (c) Microsoft. All rights reserved.

"""SRE Incident Response Workflow for DevUI.

This workflow automates incident response with:
1. Alert Processing - Receives and validates incoming alerts
2. Incident Triage - Analyzes severity and affected services
3. GitHub Issue Creation - Creates tracking issue (simulated)
4. Teams Notification - Posts to incident channel (simulated)
5. Final Report - Summarizes actions taken

For demo purposes, GitHub and Teams integrations are simulated.
In production, these would use actual MCP servers.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# Optional: Set up OpenTelemetry tracing for AI Toolkit
# Uncomment the following lines if you have opentelemetry-exporter-otlp-proto-grpc installed
# from agent_framework.observability import configure_otel_providers
# configure_otel_providers(
#     vs_code_extension_port=4317,  # AI Toolkit gRPC port
#     enable_sensitive_data=True  # Enable capturing prompts and completions
# )

from agent_framework import (
    Case,
    Default,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)
from pydantic import BaseModel, Field
from typing_extensions import Never


# ============================================================================
# Data Models
# ============================================================================

class AlertInput(BaseModel):
    """Input model for incoming alerts."""
    
    alert_id: str = Field(
        default="ALT-2026-0131-001",
        description="Unique alert identifier"
    )
    title: str = Field(
        default="Database Server CPU Critical",
        description="Alert title"
    )
    severity: Literal["critical", "high", "medium", "low"] = Field(
        default="critical",
        description="Alert severity level"
    )
    description: str = Field(
        default="vm-db-01 CPU utilization exceeded 90% for more than 5 minutes",
        description="Detailed alert description"
    )
    source: str = Field(
        default="Azure Monitor",
        description="Alert source system"
    )
    resource: str = Field(
        default="vm-db-01",
        description="Affected resource"
    )
    metrics: str = Field(
        default='{"cpu_percent": 94.7, "memory_percent": 88.5}',
        description="JSON string of current metrics"
    )


@dataclass
class ProcessedAlert:
    """Validated and enriched alert data."""
    alert_id: str
    title: str
    severity: str
    description: str
    source: str
    resource: str
    metrics: dict
    received_at: str
    is_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class TriageResult:
    """Result of incident triage analysis."""
    alert: ProcessedAlert
    incident_severity: str  # sev1, sev2, sev3, sev4
    incident_title: str
    summary: str
    affected_services: list[str]
    recommended_actions: list[str]
    assigned_team: str
    runbook_url: str
    priority: str  # P1, P2, P3, P4


class TriageApproval(BaseModel):
    """Human approval for triage classification."""
    
    approved: Literal["approve", "override to sev1", "override to sev2", "override to sev3"] = Field(
        description="Approve the triage or override the severity"
    )
    notes: str = Field(
        default="",
        description="Optional notes about the incident"
    )


@dataclass
class GitHubIssue:
    """Created GitHub issue details."""
    triage: TriageResult
    issue_number: int
    issue_url: str
    labels: list[str]
    created_at: str


@dataclass
class TeamsNotification:
    """Teams notification result."""
    github_issue: GitHubIssue
    channel: str
    message_id: str
    posted_at: str
    success: bool


@dataclass
class IncidentReport:
    """Final incident report."""
    incident_id: str
    severity: str
    github_url: str
    teams_posted: bool
    summary: str
    processing_time: float


# ============================================================================
# Executors
# ============================================================================

class AlertProcessor(Executor):
    """Step 1: Receives and validates incoming alerts."""
    
    @handler
    async def process_alert(self, alert: AlertInput, ctx: WorkflowContext[ProcessedAlert]) -> None:
        """Validate and enrich the incoming alert."""
        await asyncio.sleep(0.5)  # Simulate processing
        
        # Parse metrics JSON
        try:
            metrics = json.loads(alert.metrics) if isinstance(alert.metrics, str) else alert.metrics
        except json.JSONDecodeError:
            metrics = {}
        
        validation_errors = []
        
        # Validate required fields
        if not alert.alert_id:
            validation_errors.append("Missing alert_id")
        if not alert.title:
            validation_errors.append("Missing title")
        if alert.severity not in ["critical", "high", "medium", "low"]:
            validation_errors.append(f"Invalid severity: {alert.severity}")
        
        processed = ProcessedAlert(
            alert_id=alert.alert_id,
            title=alert.title,
            severity=alert.severity,
            description=alert.description,
            source=alert.source,
            resource=alert.resource,
            metrics=metrics,
            received_at=datetime.now().isoformat(),
            is_valid=len(validation_errors) == 0,
            validation_errors=validation_errors
        )
        
        await ctx.send_message(processed)


class IncidentTriageExecutor(Executor):
    """Step 2: Analyzes alert and determines incident severity."""
    
    # Service to team mapping
    SERVICE_TEAMS = {
        "vm-db": "platform-sre-team",
        "vm-prod": "backend-team",
        "vm-api": "api-team",
        "vm-cache": "platform-team",
    }
    
    # Runbook URLs
    RUNBOOKS = {
        "cpu": "https://wiki.contoso.com/runbooks/high-cpu",
        "memory": "https://wiki.contoso.com/runbooks/high-memory",
        "disk": "https://wiki.contoso.com/runbooks/disk-space",
        "network": "https://wiki.contoso.com/runbooks/network-issues",
        "default": "https://wiki.contoso.com/runbooks/general-triage",
    }
    
    @handler
    async def triage_alert(self, alert: ProcessedAlert, ctx: WorkflowContext[TriageResult]) -> None:
        """Analyze the alert and determine incident classification."""
        await asyncio.sleep(1.0)  # Simulate analysis
        
        # Map alert severity to incident severity
        severity_map = {
            "critical": "sev1",
            "high": "sev2",
            "medium": "sev3",
            "low": "sev4"
        }
        incident_severity = severity_map.get(alert.severity, "sev3")
        
        # Determine priority
        priority_map = {
            "sev1": "P1",
            "sev2": "P2",
            "sev3": "P3",
            "sev4": "P4"
        }
        
        # Find assigned team based on resource name
        assigned_team = "platform-sre-team"  # default
        for prefix, team in self.SERVICE_TEAMS.items():
            if alert.resource.startswith(prefix):
                assigned_team = team
                break
        
        # Determine affected services based on resource
        affected_services = []
        if "db" in alert.resource:
            affected_services = ["database-primary", "order-service", "inventory-service"]
        elif "api" in alert.resource:
            affected_services = ["api-gateway", "payment-service"]
        elif "cache" in alert.resource:
            affected_services = ["redis-cache", "session-service"]
        else:
            affected_services = [alert.resource]
        
        # Get appropriate runbook
        runbook_url = self.RUNBOOKS["default"]
        for keyword, url in self.RUNBOOKS.items():
            if keyword in alert.title.lower() or keyword in alert.description.lower():
                runbook_url = url
                break
        
        # Generate recommended actions
        recommended_actions = []
        metrics = alert.metrics
        
        if metrics.get("cpu_percent", 0) > 90:
            recommended_actions.append("Check for runaway processes")
            recommended_actions.append("Consider scaling up or out")
        if metrics.get("memory_percent", 0) > 85:
            recommended_actions.append("Identify memory-intensive queries")
            recommended_actions.append("Check for memory leaks")
        if not recommended_actions:
            recommended_actions.append("Review recent deployments")
            recommended_actions.append("Check system logs for errors")
        
        triage = TriageResult(
            alert=alert,
            incident_severity=incident_severity,
            incident_title=f"[{incident_severity.upper()}] {alert.title}",
            summary=f"{alert.description}. Resource: {alert.resource}. Current metrics show elevated {', '.join(k for k, v in metrics.items() if isinstance(v, (int, float)) and v > 80)}.",
            affected_services=affected_services,
            recommended_actions=recommended_actions,
            assigned_team=assigned_team,
            runbook_url=runbook_url,
            priority=priority_map[incident_severity]
        )
        
        # Request human approval for sev1/sev2 incidents
        if incident_severity in ["sev1", "sev2"]:
            await ctx.request_info(
                request_data=triage,
                response_type=TriageApproval,
            )
        else:
            await ctx.send_message(triage)
    
    @response_handler
    async def handle_approval(
        self, 
        original_triage: TriageResult, 
        response: TriageApproval, 
        ctx: WorkflowContext[TriageResult]
    ) -> None:
        """Process human approval and update triage if needed."""
        triage = original_triage
        
        # Handle severity overrides
        if response.approved.startswith("override"):
            new_severity = response.approved.split()[-1]  # e.g., "override to sev2" -> "sev2"
            triage.incident_severity = new_severity
            triage.incident_title = f"[{new_severity.upper()}] {triage.alert.title}"
            triage.priority = {"sev1": "P1", "sev2": "P2", "sev3": "P3"}[new_severity]
        
        await ctx.send_message(triage)


class GitHubIssueCreator(Executor):
    """Step 3: Creates a GitHub issue for incident tracking (simulated)."""
    
    @handler
    async def create_issue(self, triage: TriageResult, ctx: WorkflowContext[GitHubIssue]) -> None:
        """Create a GitHub issue for the incident."""
        await asyncio.sleep(1.5)  # Simulate API call
        
        # Simulate issue creation (in production, use GitHub MCP)
        issue_number = hash(triage.alert.alert_id) % 10000 + 1000
        
        labels = [
            f"severity:{triage.incident_severity}",
            f"priority:{triage.priority}",
            "incident",
            triage.assigned_team,
        ]
        
        issue = GitHubIssue(
            triage=triage,
            issue_number=issue_number,
            issue_url=f"https://github.com/contoso/incidents/issues/{issue_number}",
            labels=labels,
            created_at=datetime.now().isoformat()
        )
        
        await ctx.send_message(issue)


class TeamsNotifier(Executor):
    """Step 4: Posts notification to Teams channel (simulated)."""
    
    @handler
    async def notify_teams(self, issue: GitHubIssue, ctx: WorkflowContext[TeamsNotification]) -> None:
        """Post an incident notification to Teams."""
        await asyncio.sleep(1.0)  # Simulate API call
        
        # Determine channel based on severity
        channel_map = {
            "sev1": "#incident-critical",
            "sev2": "#incident-high",
            "sev3": "#ops-alerts",
            "sev4": "#ops-info"
        }
        channel = channel_map.get(issue.triage.incident_severity, "#ops-alerts")
        
        # Simulate Teams notification (in production, use Teams MCP/webhook)
        notification = TeamsNotification(
            github_issue=issue,
            channel=channel,
            message_id=f"msg-{hash(issue.issue_url) % 100000}",
            posted_at=datetime.now().isoformat(),
            success=True
        )
        
        await ctx.send_message(notification)


class IncidentReporter(Executor):
    """Step 5: Generates final incident report."""
    
    @handler
    async def generate_report(
        self, 
        notification: TeamsNotification, 
        ctx: WorkflowContext[Never, str]
    ) -> None:
        """Generate the final incident report."""
        await asyncio.sleep(0.5)
        
        issue = notification.github_issue
        triage = issue.triage
        
        # Build report
        severity_emoji = {
            "sev1": "🔴",
            "sev2": "🟠", 
            "sev3": "🟡",
            "sev4": "🔵"
        }
        
        emoji = severity_emoji.get(triage.incident_severity, "⚪")
        
        report = f"""
{emoji} INCIDENT RESPONSE COMPLETE {emoji}
════════════════════════════════════════

📋 Incident: {triage.incident_title}
🎫 Ticket: #{issue.issue_number}
🔗 GitHub: {issue.issue_url}

📊 Classification:
   • Severity: {triage.incident_severity.upper()}
   • Priority: {triage.priority}
   • Assigned: {triage.assigned_team}

⚠️ Affected Services:
   • {chr(10) + '   • '.join(triage.affected_services)}

📝 Summary:
   {triage.summary}

✅ Recommended Actions:
   1. {chr(10) + '   2. '.join(triage.recommended_actions[:2]) if len(triage.recommended_actions) > 1 else triage.recommended_actions[0] if triage.recommended_actions else 'Review logs'}

📚 Runbook: {triage.runbook_url}

💬 Teams Notification:
   • Channel: {notification.channel}
   • Status: {'✓ Posted' if notification.success else '✗ Failed'}

════════════════════════════════════════
        """.strip()
        
        await ctx.yield_output(report)


# ============================================================================
# Workflow Definition
# ============================================================================

# Create executors
alert_processor = AlertProcessor(id="alert_processor")
incident_triage = IncidentTriageExecutor(id="incident_triage")
github_creator = GitHubIssueCreator(id="github_creator")
teams_notifier = TeamsNotifier(id="teams_notifier")
incident_reporter = IncidentReporter(id="incident_reporter")

# Build the workflow
workflow = (
    WorkflowBuilder(
        name="SRE Incident Response",
        description="Automated incident triage with GitHub issue creation and Teams notifications"
    )
    .set_start_executor(alert_processor)
    .add_edge(alert_processor, incident_triage)
    .add_edge(incident_triage, github_creator)
    .add_edge(github_creator, teams_notifier)
    .add_edge(teams_notifier, incident_reporter)
    .build()
)


def main():
    """Launch the SRE incident workflow in DevUI."""
    from agent_framework.devui import serve
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    
    logger.info("Starting SRE Incident Response Workflow")
    logger.info("Available at: http://localhost:8090")
    
    serve(entities=[workflow], port=8090, auto_open=True)


if __name__ == "__main__":
    main()
