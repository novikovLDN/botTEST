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
from handlers.user import router as user_router
from handlers.admin import router as admin_router
from handlers.payments import router as payments_router

router.include_router(user_router)
router.include_router(admin_router)
router.include_router(payments_router)


# ====================================================================================
# GLOBAL FALLBACK HANDLER: Обработка необработанных callback_query
# ====================================================================================
# ВАЖНО: Этот handler должен быть зарегистрирован ПОСЛЕ всех конкретных handlers
# В aiogram 3.x handlers обрабатываются в порядке регистрации
# Fallback handler с пустым фильтром перехватывает все необработанные callback_query
@router.callback_query()
async def callback_fallback(callback: CallbackQuery, state: FSMContext):
    """
    Глобальный fallback handler для всех необработанных callback_query
    
    Логирует callback_data и текущее FSM-состояние для отладки.
    Отвечает пользователю, чтобы избежать висящих callback_query.
    """
    callback_data = callback.data
    telegram_id = callback.from_user.id
    current_state = await state.get_state()
    
    logger.warning(
        f"Unhandled callback_query: user={telegram_id}, "
        f"callback_data='{callback_data}', "
        f"fsm_state={current_state}"
    )
    
    # Отвечаем пользователю, чтобы избежать висящих callback_query
    try:
        await callback.answer("Действие недоступно", show_alert=False)
    except Exception as e:
        logger.error(f"Error answering callback_query: {e}")