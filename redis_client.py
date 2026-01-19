"""
Redis Client Module

Manages Redis connection for FSM storage and cache.
Provides health check and connection validation.
"""
import asyncio
import logging
from typing import Optional
import redis.asyncio as redis
import config

logger = logging.getLogger(__name__)

# Глобальный Redis клиент для health checks
_redis_client: Optional[redis.Redis] = None

# Глобальный флаг готовности Redis (для health checks без блокировки)
REDIS_READY: bool = False


async def create_redis_client() -> redis.Redis:
    """
    Создать Redis клиент для проверки подключения
    
    Returns:
        Redis клиент
        
    Raises:
        redis.RedisError: При ошибке подключения
    """
    if not config.REDIS_URL:
        raise ValueError("REDIS_URL is not set")
    
    # Парсим URL и создаём клиент
    client = redis.from_url(
        config.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,  # 5 секунд на подключение
        socket_timeout=5,  # 5 секунд на операции
        retry_on_timeout=True,
        health_check_interval=30,  # Проверка здоровья каждые 30 секунд
    )
    
    return client


async def check_redis_connection() -> bool:
    """
    Проверить подключение к Redis
    
    Returns:
        True если подключение успешно
        
    Raises:
        redis.RedisError: При ошибке подключения
    """
    global _redis_client, REDIS_READY
    
    try:
        if _redis_client is None:
            _redis_client = await create_redis_client()
        
        # Выполняем простую команду для проверки подключения
        await _redis_client.ping()
        REDIS_READY = True
        logger.info("✅ Redis connection verified")
        return True
    except Exception as e:
        REDIS_READY = False
        logger.error(f"❌ Redis connection check failed: {e}")
        raise


async def close_redis_client():
    """Закрыть Redis клиент"""
    global _redis_client, REDIS_READY
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        REDIS_READY = False
        logger.info("Redis client closed")


async def get_redis_client() -> Optional[redis.Redis]:
    """Получить глобальный Redis клиент для health checks"""
    return _redis_client
