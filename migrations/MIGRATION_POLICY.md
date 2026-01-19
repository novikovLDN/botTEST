# Migration Policy - Enterprise Standard

## Overview

This document defines the migration policy for the enterprise Telegram bot project. All migrations must follow these standards to ensure idempotency, compatibility with asyncpg, and safe re-runs.

## Core Principles

1. **Idempotency**: All migrations must be safely re-runnable
2. **Fail-Fast**: Any migration error must stop the service immediately
3. **Transaction Safety**: Each migration runs in its own transaction
4. **asyncpg Compatibility**: All SQL must be compatible with `asyncpg.execute()`

## Allowed SQL Constructs

### ✅ ALLOWED: DDL with IF NOT EXISTS

```sql
-- CREATE statements
CREATE TABLE IF NOT EXISTS table_name (...);
CREATE INDEX IF NOT EXISTS idx_name ON table_name(column);

-- ALTER statements
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE;
```

### ✅ ALLOWED: DO $$ BEGIN ... END $$ Blocks

For complex logic that requires conditional execution:

```sql
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public'
          AND table_name = 'table_name' 
          AND column_name = 'column_name'
    ) THEN
        ALTER TABLE table_name ALTER COLUMN column_name DROP NOT NULL;
    END IF;
END $$;
```

### ✅ ALLOWED: INSERT with ON CONFLICT

```sql
INSERT INTO table_name (column1, column2)
VALUES (value1, value2)
ON CONFLICT (unique_column) DO NOTHING;
```

### ✅ ALLOWED: INSERT ... SELECT ... WHERE NOT EXISTS

```sql
INSERT INTO table_name (column1, column2)
SELECT value1, value2
WHERE NOT EXISTS (SELECT 1 FROM table_name WHERE condition);
```

## Forbidden Constructs

### ❌ FORBIDDEN: Naked IF Statements

```sql
-- WRONG: IF outside DO $$ block
IF EXISTS (...) THEN
    ALTER TABLE ...;
END IF;

-- CORRECT: IF inside DO $$ block
DO $$
BEGIN
    IF EXISTS (...) THEN
        ALTER TABLE ...;
    END IF;
END $$;
```

### ❌ FORBIDDEN: Non-Idempotent Operations

```sql
-- WRONG: Will fail on re-run
ALTER TABLE table_name ADD COLUMN column_name TYPE;

-- CORRECT: Idempotent
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE;
```

### ❌ FORBIDDEN: DROP without IF EXISTS (where applicable)

```sql
-- WRONG: Will fail if doesn't exist
DROP INDEX idx_name;

-- CORRECT: Safe
DROP INDEX IF EXISTS idx_name;
```

## Migration Structure

Each migration file must:

1. Start with a comment describing the migration purpose
2. Use only allowed SQL constructs
3. Be fully idempotent
4. Handle edge cases (missing tables, columns, etc.)

## Example Migration

```sql
-- Migration XXX: Add new feature fields
-- Adds feature columns to existing table

-- Add new columns (idempotent)
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS feature_flag BOOLEAN DEFAULT FALSE;
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS feature_data TEXT;

-- Complex logic requires DO $$ block
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public'
          AND table_name = 'table_name' 
          AND column_name = 'old_column'
    ) THEN
        -- Migration logic here
        ALTER TABLE table_name ALTER COLUMN old_column DROP NOT NULL;
    END IF;
END $$;

-- Create indexes (idempotent)
CREATE INDEX IF NOT EXISTS idx_table_feature_flag ON table_name(feature_flag);
```

## Error Handling

- **Migration errors**: Must raise exception (fail-fast)
- **Transaction rollback**: Automatic on error
- **Service shutdown**: Required on migration failure

## Testing

Before deploying:

1. Test migration on clean database
2. Test migration re-run (idempotency)
3. Test migration on database with existing data
4. Verify asyncpg compatibility

## References

- PostgreSQL Documentation: https://www.postgresql.org/docs/
- asyncpg Documentation: https://magicstack.github.io/asyncpg/
- Migration Engine: `migrations.py`
