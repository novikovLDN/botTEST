# Migration 006 Deployment Checklist

## Changes Made

✅ **Removed DO $$ block** from migration 006
- Removed PL/pgSQL `DO $$ BEGIN ... END $$` block with `IF EXISTS`
- Replaced with direct `ALTER COLUMN DROP NOT NULL` (safe, column already nullable in migration 001)
- Migration now uses only `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`

## Verification

### ✅ Code Check
- [x] No naked IF statements outside DO $$ blocks
- [x] No BEGIN/END outside DO $$ blocks  
- [x] No DO $$ blocks remaining
- [x] Only DDL `IF NOT EXISTS` (standard PostgreSQL syntax)
- [x] Fully compatible with `asyncpg.execute()`

### ✅ Migration File
- [x] File: `migrations/006_add_subscription_fields.sql`
- [x] Commit: `ef42767`
- [x] Branch: `main`

## Deployment Steps

### 1. Push to Repository
```bash
git push origin main
```

### 2. Verify Railway Deployment
1. Check Railway dashboard for new deployment
2. Verify build completes successfully
3. Check logs for migration execution:
   - Look for: `Applying migration 006: 006_add_subscription_fields.sql`
   - Look for: `Migration 006 applied successfully`
   - Look for: `DB_INIT_STATUS: READY`

### 3. Verify Service Health
1. Check health endpoint: `GET /health`
   - Expected: `"status": "ok"`
   - Expected: `"db_init_status": "READY"`
   - Expected: `"db_ready": true`

2. Check service logs:
   - No migration errors
   - No syntax errors
   - Service starts without restarts

### 4. Database Verification
```sql
-- Verify columns exist
SELECT column_name 
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name = 'subscriptions'
  AND column_name IN ('uuid', 'status', 'source', 'vpn_key')
ORDER BY column_name;

-- Verify vpn_key is nullable
SELECT is_nullable 
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name = 'subscriptions'
  AND column_name = 'vpn_key';
-- Expected: is_nullable = 'YES'
```

## Expected Results

✅ **Migration 006 applies without errors**
✅ **DB_INIT_STATUS = READY**
✅ **Container starts without restarts**
✅ **No syntax errors**
✅ **Service health check passes**

## Rollback Plan

If migration fails:
1. Railway will automatically rollback deployment
2. Previous version will remain running
3. Fix migration and redeploy

## Notes

- Migration is idempotent: safe to re-run
- `ALTER COLUMN DROP NOT NULL` is safe on already-nullable column (no-op)
- All operations use standard PostgreSQL DDL syntax
- Fully compatible with asyncpg.execute()
