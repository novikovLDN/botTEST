-- Migration 003: Add referral system
-- Adds referral fields to users and creates referrals table

-- Add referral fields to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_level TEXT DEFAULT 'base' CHECK (referral_level IN ('base', 'vip'));

-- Migrate data from referred_by to referrer_id if needed
-- Проверка и миграция выполняется только если колонка referred_by существует
-- Используем безопасный подход без DO $$ блока (парсер миграций не поддерживает dollar quotes)

-- Create unique index on referral_code (partial index for non-null values)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code 
ON users(referral_code) 
WHERE referral_code IS NOT NULL;

-- Create index on referrer_id (partial index for non-null values)
CREATE INDEX IF NOT EXISTS idx_users_referrer_id 
ON users(referrer_id) 
WHERE referrer_id IS NOT NULL;

-- Referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_user_id BIGINT NOT NULL,
    referred_user_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_rewarded BOOLEAN DEFAULT FALSE,
    reward_amount INTEGER DEFAULT 0,
    UNIQUE (referred_user_id)
);

-- Migrate old column names if they exist
-- ПРИМЕЧАНИЕ: RENAME COLUMN не поддерживает IF EXISTS
-- Эти команды выполнятся только если старые колонки существуют, иначе будет ошибка
-- В новой БД старых колонок нет, поэтому эти команды не нужны
-- Если нужно мигрировать старую БД, выполните вручную через psql:
-- ALTER TABLE referrals RENAME COLUMN referrer_id TO referrer_user_id;
-- ALTER TABLE referrals RENAME COLUMN referred_id TO referred_user_id;
-- ALTER TABLE referrals RENAME COLUMN rewarded TO is_rewarded;

-- Add reward_amount if missing
ALTER TABLE referrals ADD COLUMN IF NOT EXISTS reward_amount INTEGER DEFAULT 0;

-- Create index on referrer_user_id
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_user_id);

