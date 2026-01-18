"""
Payments handlers module
Объединяет все payments подмодули в единый роутер
"""
from aiogram import Router

# Временно: используем роутер напрямую из handlers.payments
# После разбиения payments.py на модули, здесь будет объединение подмодулей
import sys
import importlib.util

# Импортируем роутер из handlers/payments.py (старый файл)
spec = importlib.util.spec_from_file_location("payments_legacy", "handlers/payments.py")
payments_legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payments_legacy)

router = payments_legacy.router

# TODO: После разбиения payments.py на модули, заменить на:
# from handlers.payments.purchase import router as purchase_router
# from handlers.payments.balance import router as balance_router
# from handlers.payments.promo import router as promo_router
# from handlers.payments.invoice import router as invoice_router
# router.include_router(purchase_router)
# router.include_router(balance_router)
# router.include_router(promo_router)
# router.include_router(invoice_router)
