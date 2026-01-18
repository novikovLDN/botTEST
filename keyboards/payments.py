from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import localization
import config

def get_tariff_keyboard(language: str):
    """Клавиатура выбора тарифа (Basic/Plus)"""
    buttons = []
    
    for tariff_key in config.TARIFFS.keys():
        base_text = localization.get_text(language, f"tariff_button_{tariff_key}")
        buttons.append([InlineKeyboardButton(text=base_text, callback_data=f"tariff_type:{tariff_key}")])
    
    # Кнопка ввода промокода
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "enter_promo_button", default="🎟 Ввести промокод"),
        callback_data="enter_promo"
    )])
    
    buttons.append([InlineKeyboardButton(
        text=localization.get_text(language, "back"),
        callback_data="menu_main"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_method_keyboard(language: str):
    """Клавиатура выбора способа оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=localization.get_text(language, "payment_test"),
            callback_data="payment_test"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "payment_sbp"),
            callback_data="payment_sbp"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_buy_vpn"
        )],
    ])
    return keyboard


def get_sbp_payment_keyboard(language: str):
    """Клавиатура для оплаты СБП"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=localization.get_text(language, "paid_button"),
            callback_data="payment_paid"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_main"
        )],
    ])
    return keyboard


def get_pending_payment_keyboard(language: str):
    """Клавиатура после нажатия 'Я оплатил'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_main"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "support"),
            callback_data="menu_support"
        )],
    ])
    return keyboard

def get_vpn_key_keyboard(language: str):
    """Клавиатура для экрана выдачи VPN-ключа после оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=localization.get_text(language, "go_to_connection", default="🔌 Перейти к подключению"),
            callback_data="menu_instruction"
        )],
        [InlineKeyboardButton(
            text="📋 Скопировать ключ",
            callback_data="copy_vpn_key"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "profile"),
            callback_data="go_profile"
        )],
    ])
    return keyboard
