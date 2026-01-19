"""
Handlers module - объединение всех роутеров обработчиков.

Этот модуль служит точкой входа для всех обработчиков бота.
Он объединяет роутеры из подмодулей:
- handlers.user - пользовательские обработчики
- handlers.admin - административные обработчики
- handlers.payments - обработчики платежей

Все обработчики должны находиться в соответствующих подмодулях, а не в этом файле.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

# Создаем основной роутер
router = Router()

# Включаем роутеры из подмодулей
# ВАЖНО: Порядок регистрации важен - более специфичные handlers должны быть зарегистрированы первыми
# В aiogram 3.x handlers обрабатываются в порядке регистрации в каждом роутере
# При include_router handlers из подроутера добавляются в конец списка handlers основного роутера
from handlers.user import router as user_router
from handlers.admin import router as admin_router
from handlers.payments import router as payments_router

# Регистрируем подроутеры
# Порядок важен: handlers из этих роутеров будут обрабатываться в порядке их регистрации внутри каждого роутера
router.include_router(user_router)
router.include_router(admin_router)
router.include_router(payments_router)


# ====================================================================================
# GLOBAL FALLBACK HANDLER: Обработка необработанных callback_query
# ====================================================================================
# КРИТИЧНО: Этот handler должен быть зарегистрирован ПОСЛЕ всех конкретных handlers
# В aiogram 3.x handlers обрабатываются в порядке регистрации
# Fallback handler с пустым фильтром (@router.callback_query()) перехватывает ВСЕ callback_query,
# которые не были обработаны предыдущими handlers с более специфичными фильтрами
# 
# ВАЖНО: Этот handler ВСЕГДА вызывает callback.answer() для предотвращения
# висящих callback_query и сообщения "Действие недоступно" в Telegram
@router.callback_query()
async def callback_fallback(callback: CallbackQuery, state: FSMContext):
    """
    Глобальный fallback handler для всех необработанных callback_query
    
    Этот handler обрабатывает callback_query, которые не были обработаны
    более специфичными handlers из подроутеров.
    
    ВСЕГДА вызывает callback.answer() для предотвращения висящих callback_query.
    """
    callback_data = callback.data
    telegram_id = callback.from_user.id
    current_state = await state.get_state()
    
    # ВАЖНО: Отвечаем СРАЗУ, чтобы избежать "Действие недоступно" в Telegram
    try:
        await callback.answer()
    except Exception as e:
        logger.error(f"Error answering callback_query in fallback: {e}")
    
    # Логируем для отладки
    logger.warning(
        f"Unhandled callback_query: user={telegram_id}, "
        f"callback_data='{callback_data}', "
        f"fsm_state={current_state}"
    )