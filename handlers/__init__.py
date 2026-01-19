"""
Handlers module - Fallback handler для необработанных callback_query.

КРИТИЧНО: В aiogram 3.x порядок регистрации handlers критически важен.
Handlers обрабатываются в порядке их регистрации.

ВАЖНО: Этот модуль содержит ТОЛЬКО fallback handler.
Конкретные handlers регистрируются напрямую на Dispatcher в main.py
для гарантии правильного порядка обработки.
"""

import logging
from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

# Создаем роутер ТОЛЬКО для fallback handler
router = Router()


# ====================================================================================
# GLOBAL FALLBACK HANDLER: Обработка необработанных callback_query
# ====================================================================================
# КРИТИЧНО: Этот handler ДОЛЖЕН быть зарегистрирован ПОСЛЕ всех конкретных handlers
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
    
    ВАЖНО: Если этот handler срабатывает для известных callback_data (lang_ru, menu_main, admin:*),
    это означает проблему с регистрацией или фильтрами конкретных handlers.
    """
    callback_data = callback.data
    telegram_id = callback.from_user.id
    current_state = await state.get_state()
    
    # ВАЖНО: Отвечаем СРАЗУ, чтобы избежать "Действие недоступно" в Telegram
    try:
        await callback.answer()
    except Exception as e:
        logger.error(f"Error answering callback_query in fallback: {e}")
    
    # Логируем для отладки с дополнительной информацией
    logger.warning(
        f"Unhandled callback_query: user={telegram_id}, "
        f"callback_data='{callback_data}', "
        f"fsm_state={current_state}, "
        f"message_id={callback.message.message_id if callback.message else 'N/A'}"
    )
    
    # Дополнительная диагностика: проверяем, что handlers действительно зарегистрированы
    if callback_data in ['lang_ru', 'lang_en', 'menu_main', 'admin:main']:
        logger.error(
            f"CRITICAL: Known callback_data '{callback_data}' reached fallback handler! "
            f"This indicates a problem with handler registration or filters."
        )