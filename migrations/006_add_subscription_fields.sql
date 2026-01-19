-- Migration 006: Add extended subscription fields
-- Adds Xray Core fields and notification flags to subscriptions

-- Xray Core fields for VLESS
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS uuid TEXT;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'payment';

-- Make vpn_key nullable (for Xray Core migration)
-- Note: vpn_key is already nullable in migration 001, so DROP NOT NULL is safe
-- This operation is idempotent: DROP NOT NULL on nullable column is a no-op
ALTER TABLE subscriptions ALTER COLUMN vpn_key DROP NOT NULL;

-- Auto-renewal fields
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_auto_renewal_at TIMESTAMP;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_notification_sent_at TIMESTAMP;

-- Smart notification flags
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS activated_at TIMESTAMP;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_bytes BIGINT DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS first_traffic_at TIMESTAMP;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_no_traffic_20m_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_no_traffic_24h_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_first_connection_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_3days_usage_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_7days_before_expiry_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_expiry_day_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_expired_24h_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS smart_notif_vip_offer_sent BOOLEAN DEFAULT FALSE;

