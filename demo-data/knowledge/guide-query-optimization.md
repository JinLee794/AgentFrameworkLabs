# Database Query Optimization Guide

**Category:** guide  
**Severity:** sev2, sev3  
**Services:** database-tier, vm-db-01, vm-db-02  
**Last Updated:** 2026-02-10  

---

## Overview

This guide covers techniques for identifying and optimizing problematic database queries that contribute to performance degradation.

## When to Use This Guide

- Query latency exceeds SLO (p99 > 500ms)
- Database CPU consistently > 70%
- Lock contention alerts firing
- Slow query log growing rapidly

## Query Analysis Framework

### Step 1: Identify Slow Queries

```sql
-- Find top 10 slowest queries by total execution time
SELECT TOP 10
    qs.total_elapsed_time / qs.execution_count AS avg_elapsed_time_ms,
    qs.execution_count,
    qs.total_logical_reads / qs.execution_count AS avg_logical_reads,
    SUBSTRING(qt.text, 1, 200) AS query_text
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
ORDER BY avg_elapsed_time_ms DESC;
```

### Step 2: Analyze Execution Plans

```sql
-- Get execution plan for a specific query
SET STATISTICS PROFILE ON;
-- Run your query here
SET STATISTICS PROFILE OFF;

-- Or use Query Store
SELECT 
    q.query_id,
    qt.query_sql_text,
    p.plan_id,
    rs.avg_duration,
    rs.avg_cpu_time,
    rs.avg_logical_io_reads
FROM sys.query_store_query q
JOIN sys.query_store_query_text qt ON q.query_text_id = qt.query_text_id
JOIN sys.query_store_plan p ON q.query_id = p.query_id
JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
WHERE rs.avg_duration > 100000 -- > 100ms
ORDER BY rs.avg_duration DESC;
```

### Step 3: Check Index Usage

```sql
-- Find missing indexes
SELECT 
    mid.statement AS table_name,
    mid.equality_columns,
    mid.inequality_columns,
    mid.included_columns,
    migs.user_seeks,
    migs.avg_user_impact
FROM sys.dm_db_missing_index_details mid
JOIN sys.dm_db_missing_index_groups mig ON mid.index_handle = mig.index_handle
JOIN sys.dm_db_missing_index_group_stats migs ON mig.index_group_handle = migs.group_handle
ORDER BY migs.avg_user_impact DESC;
```

## Common Optimization Patterns

### Pattern 1: Missing Index

**Symptom:** Index Scan instead of Index Seek in execution plan

**Solution:**
```sql
-- Create covering index
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId_Status
ON Orders (CustomerId, Status)
INCLUDE (OrderDate, TotalAmount);
```

**Validation:** Re-run query and verify Seek operation in plan

### Pattern 2: Parameter Sniffing

**Symptom:** Query performs well for some parameters, poorly for others

**Solutions:**

Option A - Local variables:
```sql
DECLARE @local_param INT = @input_param;
SELECT * FROM Orders WHERE CustomerId = @local_param;
```

Option B - OPTIMIZE FOR hint:
```sql
SELECT * FROM Orders 
WHERE CustomerId = @CustomerId
OPTION (OPTIMIZE FOR (@CustomerId = 'typical_value'));
```

Option C - RECOMPILE (use sparingly):
```sql
SELECT * FROM Orders 
WHERE CustomerId = @CustomerId
OPTION (RECOMPILE);
```

### Pattern 3: N+1 Query Problem

**Symptom:** Application makes many small queries instead of one batch

**Solution:** Use JOINs or batch queries:
```sql
-- Instead of multiple queries per order
-- Use a single query with JOIN
SELECT o.OrderId, o.CustomerId, oi.ProductId, oi.Quantity
FROM Orders o
JOIN OrderItems oi ON o.OrderId = oi.OrderId
WHERE o.CustomerId = @CustomerId;
```

### Pattern 4: Large Result Sets

**Symptom:** Query returns thousands of rows to application

**Solution:** Implement pagination:
```sql
-- Use OFFSET-FETCH for pagination
SELECT OrderId, CustomerId, OrderDate
FROM Orders
WHERE Status = 'Shipped'
ORDER BY OrderDate DESC
OFFSET @PageNumber * @PageSize ROWS
FETCH NEXT @PageSize ROWS ONLY;
```

### Pattern 5: Implicit Conversions

**Symptom:** CONVERT_IMPLICIT in execution plan

**Solution:** Match data types explicitly:
```sql
-- Bad: varchar parameter against int column
WHERE OrderId = @OrderIdString

-- Good: proper type
DECLARE @OrderIdInt INT = CAST(@OrderIdString AS INT);
WHERE OrderId = @OrderIdInt;
```

## Performance Benchmarks

| Query Type | Acceptable | Warning | Critical |
|------------|------------|---------|----------|
| Point lookup | < 5ms | 5-20ms | > 20ms |
| Range scan | < 50ms | 50-200ms | > 200ms |
| Aggregation | < 200ms | 200-500ms | > 500ms |
| Report query | < 2s | 2-5s | > 5s |

## Index Maintenance

### Weekly Tasks

```sql
-- Rebuild fragmented indexes
ALTER INDEX ALL ON Orders REBUILD 
WHERE avg_fragmentation_in_percent > 30;

-- Reorganize lightly fragmented
ALTER INDEX ALL ON Orders REORGANIZE
WHERE avg_fragmentation_in_percent BETWEEN 10 AND 30;
```

### Update Statistics

```sql
-- Update statistics with full scan for critical tables
UPDATE STATISTICS Orders WITH FULLSCAN;
UPDATE STATISTICS OrderItems WITH FULLSCAN;
```

## Query Store Best Practices

1. **Enable Query Store** on all production databases:
   ```sql
   ALTER DATABASE [YourDatabase] SET QUERY_STORE = ON;
   ```

2. **Configure retention** (30 days recommended):
   ```sql
   ALTER DATABASE [YourDatabase] SET QUERY_STORE (
       OPERATION_MODE = READ_WRITE,
       DATA_FLUSH_INTERVAL_SECONDS = 900,
       INTERVAL_LENGTH_MINUTES = 60,
       MAX_STORAGE_SIZE_MB = 1000,
       QUERY_CAPTURE_MODE = AUTO,
       CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = 30)
   );
   ```

3. **Use regressed queries report** to find performance regressions

## Emergency Query Optimization

When under pressure during an incident:

1. **Kill the offending query** (if safe):
   ```sql
   KILL <session_id>;
   ```

2. **Force a known-good plan**:
   ```sql
   EXEC sp_query_store_force_plan @query_id = 123, @plan_id = 456;
   ```

3. **Add hint to bypass bad plan**:
   ```sql
   SELECT * FROM Orders WITH (FORCESEEK)
   WHERE CustomerId = @CustomerId;
   ```

## Related Documentation

- [Runbook: Database Performance Degradation](./runbook-db-performance.md)
- [Guide: CPU Analysis](./guide-cpu-analysis.md)
- [Azure SQL Performance Tuning](https://docs.microsoft.com/azure/azure-sql/database/performance-guidance)

## Change History

| Date | Author | Change |
|------|--------|--------|
| 2026-02-10 | dba-team | Added Query Store force plan section |
| 2026-01-05 | platform-sre | Updated benchmarks |
| 2025-10-15 | dba-team | Initial version |
