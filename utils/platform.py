"""
Platform detection utilities for Telegram bot

В aiogram 3.x нет прямого способа определить платформу пользователя из CallbackQuery.
Используем эвристики на основе доступной информации.
"""
from aiogram.types import CallbackQuery, Message
from typing import Literal

def detect_platform(callback_or_message: CallbackQuery | Message) -> Literal["ios", "android", "unknown"]:
    """
    Определяет платформу пользователя по CallbackQuery или Message
    
    В aiogram 3.x нет прямого доступа к user agent или device info.
    Используем эвристики:
    - По умолчанию возвращаем "unknown" (показываем все кнопки)
    - В будущем можно добавить определение по другим признакам
    
    Args:
        callback_or_message: CallbackQuery или Message объект
        
    Returns:
        "ios", "android" или "unknown"
    """
    # В aiogram 3.x нет прямого способа определить платформу из CallbackQuery/Message
    # Возвращаем "unknown" - это покажет все кнопки скачивания
    # В будущем можно добавить определение через:
    # - Сохранение платформы при первом взаимодействии
    # - Анализ других признаков (если появятся в API)
    
    return "unknown"
