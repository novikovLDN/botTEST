import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
import config
import database
import redis_client
import handlers
import reminders
import healthcheck
# import outline_cleanup  # DISABLED - мигрировали на Xray Core
import fast_expiry_cleanup
import auto_renewal
import health_server
import admin_notifications
import trial_notifications

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    Main startup sequence:
    1. Validate environment variables (config.py)
    2. Connect Redis (fail-fast if unavailable)
    3. Connect Database
    4. Run migrations (fail-fast if failed)
    5. Start polling
    """
    # ====================================================================================
    # STEP 1: Validate Environment Variables
    # ====================================================================================
    # Конфигурация уже проверена в config.py
    # Если переменные окружения не заданы, программа завершится с ошибкой
    logger.info("✅ Environment variables validated")
    
    # ====================================================================================
    # STEP 2: Connect Redis (FAIL-FAST)
    # ====================================================================================
    # Redis is REQUIRED - no fallback to MemoryStorage in production
    logger.info("🔌 Connecting to Redis...")
    try:
        # Проверяем подключение к Redis перед созданием storage
        await redis_client.check_redis_connection()
        
        # Создаём Redis storage для FSM
        storage = RedisStorage.from_url(config.REDIS_URL)
        logger.info(f"✅ Redis Storage initialized at {config.REDIS_URL}")
    except Exception as e:
        error_msg = (
            f"❌ CRITICAL: Cannot connect to Redis!\n"
            f"Error: {type(e).__name__}: {e}\n"
            f"Redis is REQUIRED for FSM state storage.\n"
            f"Application will NOT start without Redis."
        )
        logger.error(error_msg)
        
        # В production режиме запрещаем запуск без Redis
        if config.IS_PRODUCTION:
            logger.error("Production mode: Redis is mandatory. Exiting.")
            sys.exit(1)
        else:
            # В dev режиме разрешаем MemoryStorage с предупреждением
            logger.warning("Dev mode: Falling back to MemoryStorage (NOT for production!)")
            from aiogram.fsm.storage.memory import MemoryStorage
            storage = MemoryStorage()
    
    # ====================================================================================
    # STEP 3: Initialize Bot and Dispatcher
    # ====================================================================================
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    
    # Регистрация handlers
    dp.include_router(handlers.router)
    
    # ====================================================================================
    # STEP 4: Connect Database and Run Migrations (FAIL-FAST)
    # ====================================================================================
    
    logger.info("🔌 Connecting to Database...")
    # Сбрасываем флаги уведомлений при старте (чтобы уведомления отправлялись при каждом старте)
    admin_notifications.reset_notification_flags()
    
    try:
        success = await database.init_db()
        if success:
            logger.info("✅ Database initialized successfully")
            database.DB_READY = True
        else:
            error_msg = (
                f"❌ CRITICAL: Database initialization failed!\n"
                f"DB_INIT_STATUS: {database.DB_INIT_STATUS.value}\n"
                f"Migrations may not be applied.\n"
                f"Application will NOT start without successful DB initialization."
            )
            logger.error(error_msg)
            raise RuntimeError(f"Database initialization failed: {database.DB_INIT_STATUS.value}")
    except Exception as e:
        # FAIL-FAST: Не продолжаем запуск при ошибке БД
        logger.exception("❌ CRITICAL: Database initialization error")
        logger.error(f"Database initialization error: {type(e).__name__}: {e}")
        database.DB_READY = False
        
        # Уведомляем администратора о критической ошибке
        try:
            await admin_notifications.notify_admin_degraded_mode(bot)
        except Exception as e:
            logger.error(f"Failed to send critical error notification: {e}")
        
        # Завершаем процесс с ошибкой
        raise RuntimeError(f"Database initialization failed: {e}") from e
    
    # Запуск фоновой задачи для напоминаний (только если БД готова)
    reminder_task = None
    if database.DB_READY:
        reminder_task = asyncio.create_task(reminders.reminders_task(bot))
        logger.info("Reminders task started")
    else:
        logger.warning("Reminders task skipped (DB not ready)")
    
    # Запуск фоновой задачи для trial-уведомлений (только если БД готова)
    trial_notifications_task = None
    if database.DB_READY:
        trial_notifications_task = asyncio.create_task(trial_notifications.run_trial_scheduler(bot))
        logger.info("Trial notifications scheduler started")
    else:
        logger.warning("Trial notifications scheduler skipped (DB not ready)")
    
    # Запуск фоновой задачи для health-check
    healthcheck_task = asyncio.create_task(healthcheck.health_check_task(bot))
    logger.info("Health check task started")
    
    # ====================================================================================
    # HTTP Health Check Server
    # ====================================================================================
    # Запускаем HTTP сервер для мониторинга и диагностики
    # Endpoint: GET /health - возвращает статус БД и приложения
    # ====================================================================================
    health_server_host = os.getenv("HEALTH_SERVER_HOST", "0.0.0.0")
    health_server_port = int(os.getenv("HEALTH_SERVER_PORT", "8080"))
    health_server_task = asyncio.create_task(
        health_server.health_server_task(host=health_server_host, port=health_server_port, bot=bot)
    )
    logger.info(f"Health check HTTP server started on http://{health_server_host}:{health_server_port}/health")
    
    # ====================================================================================
    # Background Tasks Setup
    # ====================================================================================
    # Все задачи запускаются только после успешной инициализации БД (fail-fast гарантирует это)
    
    # Outline cleanup task DISABLED - мигрировали на Xray Core (VLESS)
    # Старая задача outline_cleanup больше не используется
    # cleanup_task = asyncio.create_task(outline_cleanup.outline_cleanup_task())
    # logger.info("Outline cleanup task started")
    cleanup_task = None
    logger.info("Outline cleanup task disabled (using Xray Core now)")
    
    # Запуск фоновой задачи для быстрой очистки истёкших подписок (только если БД готова)
    fast_cleanup_task = None
    if database.DB_READY:
        fast_cleanup_task = asyncio.create_task(fast_expiry_cleanup.fast_expiry_cleanup_task())
        logger.info("Fast expiry cleanup task started")
    else:
        logger.warning("Fast expiry cleanup task skipped (DB not ready)")
    
    # Запуск фоновой задачи для автопродления подписок (только если БД готова)
    auto_renewal_task = None
    if database.DB_READY:
        auto_renewal_task = asyncio.create_task(auto_renewal.auto_renewal_task(bot))
        logger.info("Auto-renewal task started")
    else:
        logger.warning("Auto-renewal task skipped (DB not ready)")
    
    # Запуск фоновой задачи для автоматической проверки CryptoBot платежей (только если БД готова)
    crypto_watcher_task = None
    if database.DB_READY:
        try:
            import crypto_payment_watcher
            crypto_watcher_task = asyncio.create_task(crypto_payment_watcher.crypto_payment_watcher_task(bot))
            logger.info("Crypto payment watcher task started")
        except Exception as e:
            logger.warning(f"Crypto payment watcher task skipped: {e}")
    else:
        logger.warning("Crypto payment watcher task skipped (DB not ready)")
    
    # ====================================================================================
    # STEP 5: Start Polling (FAIL-FAST GUARD)
    # ====================================================================================
    # Запрещаем запуск polling, если миграции не применены
    if database.DB_INIT_STATUS != database.DBInitStatus.READY:
        error_msg = (
            f"❌ CRITICAL: Cannot start bot polling - DB migrations not applied!\n"
            f"DB_INIT_STATUS: {database.DB_INIT_STATUS.value}\n"
            f"Expected: READY\n"
            f"Bot will NOT start in degraded mode - this is a critical error."
        )
        logger.error(error_msg)
        # Уведомляем администратора о критической ошибке
        try:
            await admin_notifications.notify_admin_degraded_mode(bot)
        except Exception as e:
            logger.error(f"Failed to send critical error notification: {e}")
        # Завершаем процесс с ошибкой
        raise RuntimeError(f"Database migrations not applied: {database.DB_INIT_STATUS.value}")
    
    logger.info("✅ Bot starting in full functionality mode")
    logger.info("🚀 Starting bot polling...")
    
    try:
        await dp.start_polling(bot)
    finally:
        # ====================================================================================
        # Cleanup: Отменяем все фоновые задачи
        # ====================================================================================
        logger.info("Shutting down...")
        
        if reminder_task:
            reminder_task.cancel()
        if trial_notifications_task:
            trial_notifications_task.cancel()
        healthcheck_task.cancel()
        health_server_task.cancel()
        if auto_renewal_task:
            auto_renewal_task.cancel()
        if cleanup_task:
            cleanup_task.cancel()
        if fast_cleanup_task:
            fast_cleanup_task.cancel()
        if crypto_watcher_task:
            crypto_watcher_task.cancel()
        
        # Ожидаем завершения всех задач
        tasks_to_wait = [
            reminder_task,
            trial_notifications_task,
            healthcheck_task,
            health_server_task,
            auto_renewal_task,
            cleanup_task,
            fast_cleanup_task,
            crypto_watcher_task,
        ]
        
        for task in tasks_to_wait:
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Закрываем пул соединений к БД
        await database.close_pool()
        logger.info("Database connection pool closed")
        
        # Закрываем Redis клиент
        await redis_client.close_redis_client()
        logger.info("Redis client closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")

