#!/usr/bin/env python3
"""
Test script for migration 006
Tests compatibility with asyncpg.execute()
"""
import asyncio
import asyncpg
import os
import sys

async def test_migration_006():
    """Test migration 006 with asyncpg"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    
    migration_path = "migrations/006_add_subscription_fields.sql"
    
    try:
        # Read migration file
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Connect to database
        conn = await asyncpg.connect(database_url)
        
        try:
            # Execute migration SQL
            await conn.execute(sql_content)
            print("✅ Migration 006 executed successfully via asyncpg.execute()")
            
            # Verify columns exist
            columns = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = 'subscriptions'
                  AND column_name IN ('uuid', 'status', 'source', 'vpn_key')
                ORDER BY column_name
            """)
            
            expected_columns = {'uuid', 'status', 'source', 'vpn_key'}
            actual_columns = {row['column_name'] for row in columns}
            
            if expected_columns.issubset(actual_columns):
                print(f"✅ All expected columns exist: {sorted(actual_columns)}")
            else:
                missing = expected_columns - actual_columns
                print(f"❌ Missing columns: {missing}", file=sys.stderr)
                sys.exit(1)
            
            # Check vpn_key is nullable
            vpn_key_info = await conn.fetchrow("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = 'subscriptions'
                  AND column_name = 'vpn_key'
            """)
            
            if vpn_key_info and vpn_key_info['is_nullable'] == 'YES':
                print("✅ vpn_key column is nullable")
            else:
                print("❌ vpn_key column is not nullable", file=sys.stderr)
                sys.exit(1)
            
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"❌ Migration test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_migration_006())
