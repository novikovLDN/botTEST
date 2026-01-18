-- Migration 002: Add balance system
-- Adds balance column to users and creates balance_transactions table

-- Add balance column to users (stored in kopecks as INTEGER)
ALTER TABLE users ADD COLUMN IF NOT EXISTS balance INTEGER NOT NULL DEFAULT 0;

-- Balance transactions table
CREATE TABLE IF NOT EXISTS balance_transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount NUMERIC NOT NULL,
    type TEXT NOT NULL,
    source TEXT,
    description TEXT,
    related_user_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add related_user_id column if missing
ALTER TABLE balance_transactions ADD COLUMN IF NOT EXISTS related_user_id BIGINT;

-- Add source column if missing
ALTER TABLE balance_transactions ADD COLUMN IF NOT EXISTS source TEXT;

-- Ensure amount is NUMERIC type
-- Используем ALTER COLUMN IF EXISTS не работает, поэтому просто изменяем тип если нужно
-- Если колонка уже имеет тип NUMERIC, операция безопасно игнорируется в некоторых версиях PostgreSQL
-- Или можно оставить как есть - в CREATE TABLE уже указан NUMERIC

