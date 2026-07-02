# Database Performance Degradation Runbook

**Category:** runbook  
**Severity:** sev1, sev2  
**Services:** vm-db-01, vm-db-02, database-tier  
**Last Updated:** 2026-02-15  

---

## Overview

This runbook covers troubleshooting and remediation steps for database performance degradation incidents, including high CPU utilization, memory pressure, and query bottlenecks.

## Symptoms

- High CPU utilization (>80%) on database servers
- Increased query latency (p99 > 500ms, p50 > 100ms)
- Connection pool exhaustion errors in application logs
- Cascading failures in dependent services (order-service, inventory-service)
- Error messages: "Connection timeout", "Too many connections", "Lock wait timeout exceeded"

## Diagnostic Steps

### Step 1: Verify Alert and Gather Initial Metrics

```sql
-- Check current connections
SELECT COUNT(*) as connection_count, state 
FROM sys.dm_exec_sessions 
GROUP BY state;

-- Check current CPU usage
SELECT scheduler_id, cpu_id, current_tasks_count, runnable_tasks_count
FROM sys.dm_os_schedulers
WHERE scheduler_id < 255;
```

### Step 2: Identify Long-Running Queries

```sql
-- Find queries running longer than 30 seconds
SELECT 
    r.session_id,
    r.start_time,
    DATEDIFF(SECOND, r.start_time, GETDATE()) as duration_seconds,
    t.text as query_text,
    r.wait_type,
    r.blocking_session_id
FROM sys.dm_exec_requests r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE DATEDIFF(SECOND, r.start_time, GETDATE()) > 30
ORDER BY duration_seconds DESC;
```

### Step 3: Check for Blocking Chains

```sql
-- Identify blocking hierarchies
WITH BlockingTree AS (
    SELECT 
        session_id,
        blocking_session_id,
        wait_type,
        wait_time,
        1 as level
    FROM sys.dm_exec_requests
    WHERE blocking_session_id = 0 AND session_id IN (
        SELECT blocking_session_id FROM sys.dm_exec_requests WHERE blocking_session_id != 0
    )
    UNION ALL
    SELECT 
        r.session_id,
        r.blocking_session_id,
        r.wait_type,
        r.wait_time,
        bt.level + 1
    FROM sys.dm_exec_requests r
    INNER JOIN BlockingTree bt ON r.blocking_session_id = bt.session_id
)
SELECT * FROM BlockingTree ORDER BY level, session_id;
```

## Immediate Mitigation Actions

### Action 1: Kill Blocking Queries (if safe)

```sql
-- Only kill after verifying it's safe to do so
KILL <session_id>;
```

**Caution:** Coordinate with application team before killing sessions. Document the killed query for postmortem.

### Action 2: Enable Rate Limiting

Contact the API Gateway team via `#platform-ops` Slack channel to:
1. Reduce rate limits by 50% on affected endpoints
2. Enable circuit breaker for non-critical paths

### Action 3: Failover to Secondary (if primary unrecoverable)

```bash
# Initiate read replica promotion
az sql db replica set-primary \
    --name sre-primary-db \
    --resource-group rg-production \
    --server sql-server-secondary
```

**Prerequisites:** 
- Confirm secondary is in sync (replication lag < 5 seconds)
- Notify dependent teams via incident channel
- Update DNS if using manual failover

### Action 4: Scale Up (vertical)

```bash
# Increase compute tier temporarily
az sql db update \
    --name sre-primary-db \
    --resource-group rg-production \
    --server sql-server-primary \
    --service-objective P6
```

## Escalation Matrix

| Condition | Action | Contact |
|-----------|--------|---------|
| CPU > 90% for 15+ minutes | Page DBA on-call | database-sre-team |
| > 50% connections blocked | Initiate failover | platform-sre-team |
| Data corruption suspected | Engage Microsoft Support | Sev A ticket |
| Customer impact confirmed | Start customer comms | incident-commander |

## Post-Incident Actions

1. **Collect diagnostics before remediation:**
   - Query execution plans
   - Wait statistics
   - Buffer pool hit ratio
   - Transaction log usage

2. **Document timeline in incident ticket**

3. **Schedule postmortem within 48 hours**

## Related Documentation

- [Query Optimization Guide](./guide-query-optimization.md)
- [CPU Analysis Guide](./guide-cpu-analysis.md)
- [Playbook: SEV1 Response](./playbook-sev1-response.md)

## Change History

| Date | Author | Change |
|------|--------|--------|
| 2026-02-15 | oncall@contoso.com | Added failover procedure for Azure SQL |
| 2026-01-20 | dba-team | Updated blocking query detection |
| 2025-12-01 | platform-team | Initial version |
