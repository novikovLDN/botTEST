"""
Configuration Module - Enterprise Standard

All environment variables are declared at the top of the file.
No business logic before full ENV initialization.
Fail-fast on invalid configuration.
"""

import os
import sys
from typing import Optional

# ====================================================================================
# ENVIRONMENT CONFIGURATION (MUST BE FIRST)
# ====================================================================================
# ENVIRONMENT is required and must be one of: dev, staging, production
# Default: "production" for Railway deployments

_ENVIRONMENT_RAW = os.getenv("ENVIRONMENT", "production").lower()
_ALLOWED_ENVIRONMENTS = {"dev", "staging", "production"}

if _ENVIRONMENT_RAW not in _ALLOWED_ENVIRONMENTS:
    print(
        f"ERROR: Invalid ENVIRONMENT value: '{_ENVIRONMENT_RAW}'",
        file=sys.stderr
    )
    print(
        f"ERROR: Allowed values: {', '.join(sorted(_ALLOWED_ENVIRONMENTS))}",
        file=sys.stderr
    )
    sys.exit(1)

ENVIRONMENT: str = _ENVIRONMENT_RAW
IS_PRODUCTION: bool = ENVIRONMENT == "production"
IS_STAGING: bool = ENVIRONMENT == "staging"
IS_DEV: bool = ENVIRONMENT == "dev"

# ====================================================================================
# REQUIRED ENVIRONMENT VARIABLES (NO DEFAULTS)
# ====================================================================================

# Telegram Bot Configuration
BOT_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN environment variable is not set!", file=sys.stderr)
    sys.exit(1)

# Admin Configuration
ADMIN_TELEGRAM_ID_STR: Optional[str] = os.getenv("ADMIN_TELEGRAM_ID")
if not ADMIN_TELEGRAM_ID_STR:
    print("ERROR: ADMIN_TELEGRAM_ID environment variable is not set!", file=sys.stderr)
    sys.exit(1)

try:
    ADMIN_TELEGRAM_ID: int = int(ADMIN_TELEGRAM_ID_STR)
except ValueError:
    print(
        f"ERROR: ADMIN_TELEGRAM_ID must be a number, got: {ADMIN_TELEGRAM_ID_STR}",
        file=sys.stderr
    )
    sys.exit(1)

# Database Configuration
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set!", file=sys.stderr)
    sys.exit(1)

# Redis Configuration
REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
if not REDIS_URL:
    print("ERROR: REDIS_URL environment variable is not set!", file=sys.stderr)
    print("ERROR: Redis is required for production deployment (FSM state storage)", file=sys.stderr)
    sys.exit(1)

# ====================================================================================
# OPTIONAL ENVIRONMENT VARIABLES (WITH SAFE DEFAULTS)
# ====================================================================================

# Support Configuration
SUPPORT_EMAIL: str = os.getenv("SUPPORT_EMAIL", "support@example.com")
SUPPORT_TELEGRAM: str = os.getenv("SUPPORT_TELEGRAM", "@support")

# Telegram Payments Configuration
TG_PROVIDER_TOKEN: str = os.getenv("TG_PROVIDER_TOKEN", "")

# Card Payments Feature Flag
# Set to "false" to disable card payments when PAYMENT_PROVIDER_INVALID occurs
# This prevents creating unnecessary pending purchases and hitting Telegram API
PAYMENTS_CARD_ENABLED: bool = os.getenv("PAYMENTS_CARD_ENABLED", "true").lower() in ("true", "1", "yes")

# Xray Core API Configuration (OPTIONAL)
XRAY_API_URL: str = os.getenv("XRAY_API_URL", "")
XRAY_API_KEY: str = os.getenv("XRAY_API_KEY", "")

# Xray VLESS REALITY Server Configuration
XRAY_SERVER_IP: str = os.getenv("XRAY_SERVER_IP", "172.86.67.9")
XRAY_PORT: int = int(os.getenv("XRAY_PORT", "443"))
XRAY_SNI: str = os.getenv("XRAY_SNI", "www.cloudflare.com")
XRAY_FP: str = os.getenv("XRAY_FP", "ios")  # Default: ios for REALITY protocol

# Xray Security Keys (REQUIRED in production, optional in dev)
_XRAY_PUBLIC_KEY_RAW: Optional[str] = os.getenv("XRAY_PUBLIC_KEY")
_XRAY_SHORT_ID_RAW: Optional[str] = os.getenv("XRAY_SHORT_ID")

# Crypto Bot Configuration
CRYPTOBOT_TOKEN: str = os.getenv("CRYPTOBOT_TOKEN", "")
CRYPTOBOT_API_URL: str = os.getenv("CRYPTOBOT_API_URL", "https://pay.crypt.bot/api")
CRYPTOBOT_WEBHOOK_SECRET: str = os.getenv("CRYPTOBOT_WEBHOOK_SECRET", "")

# Health Server Configuration
HEALTH_SERVER_HOST: str = os.getenv("HEALTH_SERVER_HOST", "0.0.0.0")
HEALTH_SERVER_PORT: int = int(os.getenv("HEALTH_SERVER_PORT", "8080"))

# ====================================================================================
# BUSINESS LOGIC (AFTER FULL ENV INITIALIZATION)
# ====================================================================================

# Import business constants (safe - no config dependencies)
from constants import (
    TARIFFS,
    BALANCE_TOPUP_AMOUNTS,
    SBP_DETAILS,
)

# VPN Keys File (DEPRECATED - keys are created via Xray API)
VPN_KEYS_FILE: str = "vpn_keys.txt"

# VPN API Availability Flag
VPN_ENABLED: bool = bool(XRAY_API_URL and XRAY_API_KEY)

# Xray Security Keys Validation (production requires explicit values)
if IS_PRODUCTION or IS_STAGING:
    if not _XRAY_PUBLIC_KEY_RAW or not _XRAY_SHORT_ID_RAW:
        print(
            "ERROR: XRAY_PUBLIC_KEY and XRAY_SHORT_ID must be set in production/staging!",
            file=sys.stderr
        )
        print(
            "ERROR: Set ENVIRONMENT=dev for development mode with default values",
            file=sys.stderr
        )
        sys.exit(1)
    XRAY_PUBLIC_KEY: str = _XRAY_PUBLIC_KEY_RAW
    XRAY_SHORT_ID: str = _XRAY_SHORT_ID_RAW
elif IS_DEV:
    # Dev mode: use safe defaults if not provided
    XRAY_PUBLIC_KEY: str = _XRAY_PUBLIC_KEY_RAW or "fDixPEehAKSEsRGm5Q9HY-BNs9uMmN5NIzEDKngDOk8"
    XRAY_SHORT_ID: str = _XRAY_SHORT_ID_RAW or "a1b2c3d4"
else:
    # Fallback (should never happen due to validation above)
    XRAY_PUBLIC_KEY: str = _XRAY_PUBLIC_KEY_RAW or ""
    XRAY_SHORT_ID: str = _XRAY_SHORT_ID_RAW or ""

# ====================================================================================
# VALIDATION & STARTUP MESSAGES
# ====================================================================================

# Log environment configuration
if IS_PRODUCTION:
    print("INFO: Running in PRODUCTION mode", file=sys.stderr)
elif IS_STAGING:
    print("INFO: Running in STAGING mode", file=sys.stderr)
else:
    print("INFO: Running in DEV mode", file=sys.stderr)

# VPN API Status
if not VPN_ENABLED:
    print("WARNING: XRAY_API_URL or XRAY_API_KEY is not set!", file=sys.stderr)
    print(
        "WARNING: VPN operations will be BLOCKED until XRAY_API_URL and XRAY_API_KEY are configured",
        file=sys.stderr
    )
    print(
        "WARNING: Bot will continue running, but subscriptions cannot be activated",
        file=sys.stderr
    )
else:
    print("INFO: VPN API configured successfully (VLESS + REALITY)", file=sys.stderr)
