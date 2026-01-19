"""
Handlers module - объединение всех роутеров обработчиков.

Этот модуль служит точкой входа для всех обработчиков бота.
Он объединяет роутеры из подмодулей:
- handlers.user - пользовательские обработчики
- handlers.admin - административные обработчики
- handlers.payments - обработчики платежей

Все обработчики должны находиться в соответствующих подмодулях, а не в этом файле.

КРИТИЧНО: В aiogram 3.x порядок регистрации handlers критически важен.
Handlers обрабатываются в порядке их регистрации в каждом роутере.
При include_router handlers из подроутера добавляются в конец списка handlers основного роутера.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

# Создаем основной роутер
router = Router()

# КРИТИЧНО: Импортируем роутеры ДО их регистрации
# Это гарантирует, что все handlers из подроутеров будут зарегистрированы
from handlers.user import router as user_router
from handlers.admin import router as admin_router
from handlers.payments import router as payments_router

# Регистрируем подроутеры в правильном порядке
# КРИТИЧНО: В aiogram 3.x порядок регистрации handlers определяет порядок их обработки
# Более специфичные handlers должны быть зарегистрированы ПЕРВЫМИ
# 
# В aiogram 3.x при include_router:
# 1. Handlers из подроутера добавляются в конец списка handlers основного роутера
# 2. Порядок обработки: handlers из первого include_router → handlers из второго → ...
# 3. Fallback handler ДОЛЖЕН быть зарегистрирован ПОСЛЕ всех include_router
# 
# ВАЖНО: Порядок регистрации критически важен для правильной работы фильтров
# Если fallback handler регистрируется ДО конкретных handlers, он перехватит все callback_query
router.include_router(user_router)
router.include_router(admin_router)
router.include_router(payments_router)

# КРИТИЧНО: В aiogram 3.x Router НЕ имеет публичного атрибута .handlers
# Любая попытка обращения к .handlers вызывает AttributeError
# Это чисто отладочный код, который НЕ должен быть в production
# Логируем успешную регистрацию роутеров без интроспекции
logger.info(
    "Routers initialized successfully: "
    "user_router, admin_router, payments_router "
    "(aiogram 3.x, handlers registered via decorators)"
)


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