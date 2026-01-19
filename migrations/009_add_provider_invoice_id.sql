-- Migration 009: Add provider_invoice_id column to pending_purchases table
-- This column stores the payment provider's invoice ID (e.g., CryptoBot invoice_id)
-- NULL for non-cryptobot purchases, TEXT for cryptobot invoice IDs

-- Add column if it doesn't exist (idempotent)
-- Используем ALTER TABLE ADD COLUMN IF NOT EXISTS вместо DO $$ блока
ALTER TABLE pending_purchases ADD COLUMN IF NOT EXISTS provider_invoice_id TEXT;
