from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot
import localization
import database
import logging

logger = logging.getLogger(__name__)

async def get_main_menu_keyboard(language: str, telegram_id: int = None):
    """Клавиатура главного меню
    
    Args:
        language: Язык пользователя
        telegram_id: Telegram ID пользователя (обязательно для проверки trial availability)
    
    Кнопка "Пробный период 3 дня" показывается ТОЛЬКО если:
    - trial_used_at IS NULL
    - Нет активной подписки
    - Нет платных подписок в истории (source='payment')
    """
    buttons = []
    
    # КРИТИЧНО: Кнопка "Пробный период 3 дня" только для новых пользователей
    # Используем is_trial_available() для строгой проверки всех условий
    if telegram_id and database.DB_READY:
        try:
            is_available = await database.is_trial_available(telegram_id)
            if is_available:
                buttons.append([InlineKeyboardButton(
                    text=localization.get_text(language, "trial_button", default="🎁 Пробный период 3 дня"),
                    callback_data="activate_trial"
                )])
        except Exception as e:
            logger.warning(f"Error checking trial availability for user {telegram_id}: {e}")
    
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "profile"),
        callback_data="menu_profile"
    )])
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "buy_vpn"),
        callback_data="menu_buy_vpn"
    )])
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "instruction"),
        callback_data="menu_instruction"
    )])
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "referral_program"),
        callback_data="menu_referral"
    )])
    buttons.append([
        InlineKeyboardButton(
            text=localization.get_text(language, "about"),
            callback_data="menu_about"
        ),
        InlineKeyboardButton(
            text=localization.get_text(language, "support"),
            callback_data="menu_support"
        ),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_keyboard(language: str, has_active_subscription: bool = False, auto_renew: bool = False):
    """Клавиатура профиля (обновленная версия)"""
    buttons = []
    
    # Кнопка продления или покупки подписки
    if has_active_subscription:
        # Если есть активная подписка - показываем кнопку продления
        buttons.append([InlineKeyboardButton(
            text=localization.get_text(language, "renew_subscription"),
            callback_data="menu_buy_vpn"  # Используем стандартный flow покупки/продления
        )])
        
        # Кнопка автопродления (только для активных подписок)
        try:
            if auto_renew:
                buttons.append([InlineKeyboardButton(
                    text=localization.get_text(language, "auto_renew_disable", default="⏸ Отключить автопродление"),
                    callback_data="toggle_auto_renew:off"
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text=localization.get_text(language, "auto_renew_enable", default="🔄 Включить автопродление"),
                    callback_data="toggle_auto_renew:on"
                )])
        except KeyError:
            # Если ключи локализации отсутствуют, пропускаем кнопку автопродления
            pass
    else:
        # Если нет активной подписки - показываем кнопку покупки
        buttons.append([InlineKeyboardButton(
            text=localization.get_text(language, "buy_vpn"),
            callback_data="menu_buy_vpn"
        )])
    
    # Кнопка пополнения баланса (всегда показываем)
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "topup_balance"),
        callback_data="topup_balance"
    )])
    
    # Кнопка копирования ключа (one-tap copy, всегда показываем)
    buttons.append([InlineKeyboardButton(
        text="📋 Скопировать ключ",
        callback_data="copy_key"
    )])
    
    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "back"),
        callback_data="menu_main"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_language_keyboard():
    """Клавиатура для выбора языка (канонический вид)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en"),
        ],
        [
            InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz"),
            InlineKeyboardButton(text="🇹🇯 Тоҷикӣ", callback_data="lang_tj"),
        ],
    ])
    return keyboard

def get_back_keyboard(language: str):
    """Кнопка Назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_main"
        )]
    ])

def get_support_keyboard(language: str):
    """Клавиатура раздела 'Поддержка'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💬 Написать в поддержку",
            url="https://t.me/asc_support"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_main"
        )],
    ])
    return keyboard

def get_about_keyboard(language: str):
    """Клавиатура раздела 'О сервисе'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=localization.get_text(language, "privacy_policy"),
            callback_data="about_privacy"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "our_channel", default="Наш канал"),
            url="https://t.me/atlas_secure"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_main"
        )],
    ])
    return keyboard

def get_instruction_keyboard(language: str, platform: str = "unknown"):
    """
    Клавиатура экрана 'Инструкция' для v2RayTun
    """
    buttons = []
    
    # Определяем какие кнопки скачивания показывать
    if platform == "ios":
        # Только iOS
        buttons.append([
            InlineKeyboardButton(
                text="📱 Скачать v2RayTun (iOS)",
                url="https://apps.apple.com/ua/app/v2raytun/id6476628951"
            )
        ])
    elif platform == "android":
        # Только Android
        buttons.append([
            InlineKeyboardButton(
                text="🤖 Скачать v2RayTun (Android)",
                url="https://play.google.com/store/apps/details?id=com.v2raytun.android"
            )
        ])
    else:
        # Unknown - показываем все кнопки
        buttons.append([
            InlineKeyboardButton(
                text="📱 Скачать v2RayTun (iOS)",
                url="https://apps.apple.com/ua/app/v2raytun/id6476628951"
            ),
            InlineKeyboardButton(
                text="🤖 Скачать v2RayTun (Android)",
                url="https://play.google.com/store/apps/details?id=com.v2raytun.android"
            ),
        ])
        buttons.append([
            InlineKeyboardButton(
                text="💻 Скачать v2RayTun (ПК)",
                url="https://v2raytun.com"
            ),
        ])
    
    # Всегда показываем кнопку копирования ключа (one-tap copy)
    buttons.append([
        InlineKeyboardButton(
            text="📋 Скопировать ключ",
            callback_data="copy_vpn_key"
        ),
    ])
    
    # Кнопки навигации
    buttons.append([
        InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_main"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text=localization.get_text(language, "support"),
            callback_data="menu_support"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
