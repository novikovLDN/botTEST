"""
Admin handlers module
Объединяет все admin подмодули в единый роутер
"""
from aiogram import Router
import sys
import importlib.util

# Временно: используем роутер напрямую из handlers.admin (старый файл)
# После разбиения admin.py на модули, здесь будет объединение подмодулей
spec = importlib.util.spec_from_file_location("admin_legacy", "handlers/admin.py")
admin_legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin_legacy)

router = admin_legacy.router

# TODO: После разбиения admin.py на модули, заменить на:
# from handlers.admin.dashboard import router as dashboard_router
# from handlers.admin.statistics import router as statistics_router
# from handlers.admin.referrals import router as referrals_router
# from handlers.admin.keys import router as keys_router
# from handlers.admin.users import router as users_router
# from handlers.admin.discounts import router as discounts_router
# from handlers.admin.system import router as system_router
# from handlers.admin.broadcast import router as broadcast_router
# from handlers.admin.payments import router as payments_router
# router.include_router(dashboard_router)
# router.include_router(statistics_router)
# router.include_router(referrals_router)
# router.include_router(keys_router)
# router.include_router(users_router)
# router.include_router(discounts_router)
# router.include_router(system_router)
# router.include_router(broadcast_router)
# router.include_router(payments_router)
