# SQL Standards

## No SELECT *

Never use `SELECT *` in SQL queries. Always specify exact column names.

Reasons:
- Explicit columns make the code self-documenting
- Prevents breakage when columns are added or reordered
- Reduces data transfer to only what's needed
- Makes it clear which fields the code depends on

Bad:
```sql
SELECT * FROM pr_snapshots WHERE id = $1
```

Good:
```sql
SELECT id, snapshot_date, repo_owner, repo_name, total_prs, unassigned_count, old_prs_count
FROM pr_snapshots WHERE id = $1
```
