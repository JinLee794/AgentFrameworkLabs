# SEV1 Incident Response Playbook

**Category:** playbook  
**Severity:** sev1  
**Services:** all  
**Last Updated:** 2026-02-20  

---

## Overview

This playbook defines the standardized response protocol for SEV1 (Critical) incidents that impact production systems and customer experience.

## SEV1 Definition

An incident is classified as SEV1 when ANY of the following conditions are met:

| Condition | Example |
|-----------|---------|
| Complete service outage | API returning 5xx for all requests |
| Data loss or corruption | Database integrity compromised |
| Security breach | Unauthorized access detected |
| > 25% customer impact | Payment processing failures |
| Revenue impact > $10,000/hour | Checkout flow broken |

## Immediate Response (First 5 Minutes)

### 1. Acknowledge the Page

- Respond to PagerDuty alert within 5 minutes
- If unable to respond, escalate to backup on-call immediately

### 2. Open Incident Channel

```
/incident create sev1 "Brief description of the issue"
```

This automatically:
- Creates Slack channel `#incident-YYYY-MMDD-NNN`
- Pages the Incident Commander
- Starts incident timer
- Creates Jira ticket

### 3. Initial Assessment (2 minutes max)

Quickly determine:
- **What is broken?** (which service, which region)
- **When did it start?** (check alert timestamp)
- **What changed recently?** (deployments, config changes)
- **Who is affected?** (customer segment, percentage)

Post initial assessment to incident channel:
```
**Initial Assessment**
- Service: order-service (us-east-1)
- Started: 08:15 UTC (alert triggered)
- Impact: ~15% of orders failing
- Recent change: Deployment at 08:10 UTC
```

## Roles and Responsibilities

| Role | Responsibility | Assigned |
|------|----------------|----------|
| **Incident Commander (IC)** | Coordinates response, makes decisions | Senior SRE on-call |
| **Technical Lead** | Drives investigation and remediation | First responder |
| **Communications Lead** | Customer and stakeholder updates | Support team lead |
| **Scribe** | Documents timeline in real-time | Volunteer or assigned |

### Incident Commander Checklist

- [ ] Verify incident severity is correct
- [ ] Ensure all roles are filled
- [ ] Set 15-minute status update cadence
- [ ] Determine if customer communication needed
- [ ] Approve any high-risk remediation actions
- [ ] Call for escalation if needed

## Investigation Framework

### Step 1: Check Recent Changes

```bash
# List deployments in last 2 hours
kubectl get replicasets -n production --sort-by=.metadata.creationTimestamp | tail -10

# Check recent config changes
az appconfig revision list --name app-config-prod --datetime "2 hours ago"
```

### Step 2: Review Metrics Dashboards

Priority order:
1. Error rate / availability
2. Latency percentiles
3. Resource utilization (CPU, memory)
4. Dependency health (databases, caches, queues)

### Step 3: Check Logs for Errors

```kusto
// Azure Log Analytics query
AppServiceHTTPLogs
| where TimeGenerated > ago(30m)
| where ScStatus >= 500
| summarize count() by bin(TimeGenerated, 1m), CsUriStem
| order by TimeGenerated desc
```

### Step 4: Validate Dependencies

Run health checks against:
- [ ] Database (connection, query response)
- [ ] Cache (Redis connectivity)
- [ ] Message queue (backlog size)
- [ ] Third-party APIs (payment, shipping)

## Mitigation Strategies (Priority Order)

### 1. Rollback (Fastest - Preferred)

If a recent deployment is suspected:

```bash
# Kubernetes rollback
kubectl rollout undo deployment/order-service -n production

# Azure App Service slot swap
az webapp deployment slot swap \
    --name order-service \
    --resource-group rg-production \
    --slot staging \
    --target-slot production
```

### 2. Feature Flag Disable

If specific feature is problematic:
```bash
# LaunchDarkly CLI
ld flag update --project prod --env production --key new-checkout-flow --state off
```

### 3. Scale Out

If capacity-related:
```bash
# Kubernetes HPA override
kubectl scale deployment/order-service --replicas=10 -n production
```

### 4. Failover

If regional or primary system failure:
- Follow specific runbook for affected system
- Coordinate DNS changes with platform team

## Communication Cadence

| Time Since Start | Action |
|------------------|--------|
| 0 min | Incident channel created |
| 5 min | Initial assessment posted |
| 15 min | First status update |
| 30 min | Customer communication (if warranted) |
| Every 15-30 min | Ongoing updates |
| Resolution | Final update + ETA for postmortem |

### Status Update Template

```
**Status Update - [TIME]**
- Current status: [Investigating / Identified / Mitigating / Monitoring / Resolved]
- Impact: [Description of customer impact]
- Actions taken: [What we've done]
- Next steps: [What we're doing next]
- ETA to resolution: [If known]
```

## Resolution and Handoff

### Declaring Resolution

Incident is resolved when:
- [ ] Service metrics return to normal
- [ ] Error rates below threshold for 15 minutes
- [ ] Customer-facing functionality verified
- [ ] No new related alerts

### Handoff to Next Shift

If incident spans shifts:
1. Document current state in incident channel
2. Verbal handoff call (15 minutes)
3. Transfer IC role explicitly
4. Update PagerDuty acknowledgment

## Post-Incident Requirements

| Task | Owner | Deadline |
|------|-------|----------|
| Incident timeline finalized | Scribe | +2 hours |
| Customer follow-up | Comms Lead | +4 hours |
| Postmortem scheduled | IC | +24 hours |
| Postmortem completed | Tech Lead | +5 days |
| Action items tracked | IC | +5 days |

## Escalation Contacts

| Level | Contact | When to Escalate |
|-------|---------|------------------|
| L1 | Platform SRE on-call | Default |
| L2 | SRE Team Lead | > 30 min unresolved |
| L3 | VP Engineering | > 1 hour, major revenue impact |
| L4 | CTO / Exec team | > 2 hours, company-wide impact |

## Related Documentation

- [Runbook: Database Performance](./runbook-db-performance.md)
- [Runbook: Memory Pressure](./runbook-memory-pressure.md)
- [Playbook: Emergency Rollback](./playbook-rollback.md)
- [Communications Templates](../templates/customer-comms/)

## Change History

| Date | Author | Change |
|------|--------|--------|
| 2026-02-20 | incident-commander | Added Azure-specific commands |
| 2026-01-15 | sre-lead | Updated escalation matrix |
| 2025-11-01 | platform-team | Initial version |
