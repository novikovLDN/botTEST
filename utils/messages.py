import asyncio
import logging
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

def _markups_equal(markup1: InlineKeyboardMarkup, markup2: InlineKeyboardMarkup) -> bool:
    """
    Упрощённое сравнение клавиатур (проверка по callback_data)
    
    Args:
        markup1: Первая клавиатура
        markup2: Вторая клавиатура
    
    Returns:
        True если клавиатуры идентичны, False иначе
    """
    try:
        if markup1 is None and markup2 is None:
            return True
        if markup1 is None or markup2 is None:
            return False
        
        kb1 = markup1.inline_keyboard if hasattr(markup1, 'inline_keyboard') else []
        kb2 = markup2.inline_keyboard if hasattr(markup2, 'inline_keyboard') else []
        
        if len(kb1) != len(kb2):
            return False
        
        for row1, row2 in zip(kb1, kb2):
            if len(row1) != len(row2):
                return False
            for btn1, btn2 in zip(row1, row2):
                if btn1.callback_data != btn2.callback_data:
                    return False
        
        return True
    except Exception:
        # При ошибке сравнения считаем, что клавиатуры разные
        return False

async def safe_edit_text(message: Message, text: str, reply_markup: InlineKeyboardMarkup = None, parse_mode: str = None, bot: Bot = None):
    """
    Безопасное редактирование текста сообщения с обработкой ошибок
    
    Сравнивает текущий контент с новым перед редактированием, чтобы избежать ненужных вызовов API.
    Если сообщение недоступно (inaccessible), использует send_message вместо edit_message.
    
    Args:
        message: Message объект для редактирования
        text: Новый текст сообщения
        reply_markup: Новая клавиатура (опционально) - MUST be InlineKeyboardMarkup, NOT coroutine
        parse_mode: Режим парсинга (HTML, Markdown и т.д.)
        bot: Bot instance (требуется для fallback на send_message)
    """
    # Защита от передачи coroutine вместо InlineKeyboardMarkup
    if asyncio.iscoroutine(reply_markup):
        raise RuntimeError("reply_markup coroutine passed without await. Must await keyboard builder before passing to safe_edit_text.")
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА: Проверяем, что message доступен (не inaccessible/deleted)
    # В aiogram 3.x нет типа InaccessibleMessage, проверяем через hasattr
    if not hasattr(message, 'chat'):
        # Сообщение недоступно - используем send_message как fallback
        if bot is None:
            logger.warning("Message is inaccessible (no chat attr) and bot not provided, cannot send fallback message")
            return
        try:
            # Пытаемся получить chat_id из других источников
            chat_id = None
            if hasattr(message, 'from_user') and hasattr(message.from_user, 'id'):
                chat_id = message.from_user.id
            
            if chat_id:
                await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
                logger.info(f"Message inaccessible (no chat attr), sent new message instead: chat_id={chat_id}")
            else:
                logger.warning("Message inaccessible (no chat attr) and cannot determine chat_id")
        except Exception as send_error:
            logger.error(f"Failed to send fallback message after inaccessible check: {send_error}")
        return
    
    # Безопасная проверка атрибутов сообщения (никогда не обращаемся напрямую без hasattr)
    current_text = None
    try:
        if hasattr(message, 'text'):
            text_attr = getattr(message, 'text', None)
            if text_attr:
                current_text = text_attr
        if not current_text and hasattr(message, 'caption'):
            caption_attr = getattr(message, 'caption', None)
            if caption_attr:
                current_text = caption_attr
    except AttributeError:
        # Защита от AttributeError - сообщение может быть недоступно
        logger.debug("AttributeError while checking message text/caption, treating as inaccessible")
        current_text = None
    
    # Сравниваем текущий текст с новым (безопасно)
    if current_text and current_text == text:
        # Текст совпадает - проверяем клавиатуру (безопасно)
        current_markup = None
        try:
            if hasattr(message, 'reply_markup'):
                markup_attr = getattr(message, 'reply_markup', None)
                if markup_attr:
                    current_markup = markup_attr
        except AttributeError:
            # Защита от AttributeError
            current_markup = None
        
        if reply_markup is None:
            # Удаление клавиатуры - проверяем, есть ли она
            if current_markup is None:
                # Контент идентичен - не вызываем edit
                return
        else:
            # Сравниваем клавиатуры (упрощённая проверка)
            if current_markup and _markups_equal(current_markup, reply_markup):
                # Контент идентичен - не вызываем edit
                return
    
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "message is not modified" in error_msg:
            # Игнорируем ошибку "message is not modified" - сообщение уже имеет нужное содержимое
            logger.debug(f"Message not modified (expected): {e}")
            return
        elif any(keyword in error_msg for keyword in ["message to edit not found", "message can't be edited", "chat not found", "message is inaccessible"]):
            # Сообщение недоступно - используем send_message как fallback
            if bot is None:
                logger.warning(f"Message inaccessible and bot not provided, cannot send fallback message: {e}")
                return
            
            try:
                # Получаем chat_id безопасно (никогда не обращаемся напрямую без hasattr)
                chat_id = None
                try:
                    if hasattr(message, 'chat'):
                        chat_obj = getattr(message, 'chat', None)
                        if chat_obj and hasattr(chat_obj, 'id'):
                            chat_id = getattr(chat_obj, 'id', None)
                except AttributeError:
                    pass
                
                if not chat_id:
                    try:
                        if hasattr(message, 'from_user'):
                            user_obj = getattr(message, 'from_user', None)
                            if user_obj and hasattr(user_obj, 'id'):
                                chat_id = getattr(user_obj, 'id', None)
                    except AttributeError:
                        pass
                
                if chat_id:
                    await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
                    logger.info(f"Message inaccessible, sent new message instead: chat_id={chat_id}")
                else:
                    logger.warning(f"Message inaccessible and cannot determine chat_id: {e}")
            except Exception as send_error:
                logger.error(f"Failed to send fallback message after edit failure: {send_error}")
        else:
            # Другие ошибки - пробрасываем
            raise
    except AttributeError as e:
        # Защита от AttributeError при обращении к атрибутам сообщения
        logger.warning(f"AttributeError in safe_edit_text, message may be inaccessible: {e}")
        # Пытаемся использовать send_message как fallback
        if bot is not None:
            try:
                # Получаем chat_id безопасно (никогда не обращаемся напрямую без hasattr)
                chat_id = None
                try:
                    if hasattr(message, 'chat'):
                        chat_obj = getattr(message, 'chat', None)
                        if chat_obj and hasattr(chat_obj, 'id'):
                            chat_id = getattr(chat_obj, 'id', None)
                except AttributeError:
                    pass
                
                if not chat_id:
                    try:
                        if hasattr(message, 'from_user'):
                            user_obj = getattr(message, 'from_user', None)
                            if user_obj and hasattr(user_obj, 'id'):
                                chat_id = getattr(user_obj, 'id', None)
                    except AttributeError:
                        pass
                
                if chat_id:
                    await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
                    logger.info(f"AttributeError handled, sent new message instead: chat_id={chat_id}")
                else:
                    logger.warning(f"AttributeError handled but cannot determine chat_id: {e}")
            except Exception as send_error:
                logger.error(f"Failed to send fallback message after AttributeError: {send_error}")

async def safe_edit_reply_markup(message: Message, reply_markup: InlineKeyboardMarkup = None):
    """
    Безопасное редактирование клавиатуры сообщения с обработкой ошибки "message is not modified"
    
    Сравнивает текущую клавиатуру с новой перед редактированием.
    
    Args:
        message: Message объект для редактирования
        reply_markup: Новая клавиатура (или None для удаления)
    """
    # Сравниваем текущую клавиатуру с новой
    if reply_markup is None:
        if message.reply_markup is None:
            # Клавиатура уже удалена - не вызываем edit
            return
    else:
        if message.reply_markup and _markups_equal(message.reply_markup, reply_markup):
            # Клавиатуры идентичны - не вызываем edit
            return
    
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
        # Игнорируем ошибку "message is not modified" - клавиатура уже имеет нужное содержимое
        logger.debug(f"Reply markup not modified (expected): {e}")

from aiogram.types import CallbackQuery
import database
import localization

async def ensure_db_ready_message(message_or_query) -> bool:
    """
    Проверка готовности базы данных с отправкой сообщения пользователю
    
    Args:
        message_or_query: Message или CallbackQuery объект
        
    Returns:
        True если БД готова, False если БД недоступна (сообщение отправлено)
    """
    if not database.DB_READY:
        # Определяем язык пользователя (по умолчанию русский)
        # ВАЖНО: Не обращаемся к БД если она не готова
        language = "ru"
        
        # Получаем текст сообщения
        error_text = localization.get_text(
            language,
            "service_unavailable",
            default="⚠️ Сервис временно недоступен. Попробуйте позже."
        )
        
        # Отправляем сообщение
        try:
            if hasattr(message_or_query, 'answer') and hasattr(message_or_query, 'text'):
                # Это Message
                await message_or_query.answer(error_text)
            elif hasattr(message_or_query, 'message') and hasattr(message_or_query, 'answer'):
                # Это CallbackQuery
                await message_or_query.message.answer(error_text)
                await message_or_query.answer()
        except Exception as e:
            logger.exception(f"Error sending degraded mode message: {e}")
        
        return False
    return True


async def ensure_db_ready_callback(callback: CallbackQuery) -> bool:
    """
    Проверка готовности базы данных для CallbackQuery (для удобства)
    
    Args:
        callback: CallbackQuery объект
        
    Returns:
        True если БД готова, False если БД недоступна (сообщение отправлено)
    """
    return await ensure_db_ready_message(callback)
