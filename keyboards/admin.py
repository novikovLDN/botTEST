from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

def get_admin_dashboard_keyboard():
    """Клавиатура главного экрана админ-дашборда"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="💰 Аналитика", callback_data="admin:analytics")],
        [InlineKeyboardButton(text="📈 Метрики", callback_data="admin:metrics")],
        [InlineKeyboardButton(text="📜 Аудит", callback_data="admin:audit")],
        [InlineKeyboardButton(text="🔑 VPN-ключи", callback_data="admin:keys")],
        [InlineKeyboardButton(text="👤 Пользователь", callback_data="admin:user")],
        [InlineKeyboardButton(text="💰 Выдать средства", callback_data="admin:credit_balance")],
        [InlineKeyboardButton(text="🚨 Система", callback_data="admin:system")],
        [InlineKeyboardButton(text="📤 Экспорт данных", callback_data="admin:export")],
        [InlineKeyboardButton(text="📣 Уведомления", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="📊 Статистика промокодов", callback_data="admin_promo_stats")],
        [InlineKeyboardButton(text="🤝 Реферальная статистика", callback_data="admin:referral_stats")],
    ])
    return keyboard


def get_admin_back_keyboard():
    """Клавиатура с кнопкой 'Назад' для админ-разделов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")],
    ])
    return keyboard


def get_reissue_notification_keyboard():
    """Клавиатура для уведомления о перевыпуске VPN-ключа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Перейти к инструкции", callback_data="menu_instruction")],
        [InlineKeyboardButton(text="📋 Скопировать ключ", callback_data="copy_vpn_key")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu_profile")],
    ])
    return keyboard


def get_broadcast_test_type_keyboard():
    """Клавиатура выбора типа тестирования"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Обычное уведомление", callback_data="broadcast_test_type:normal")],
        [InlineKeyboardButton(text="🔬 A/B тест", callback_data="broadcast_test_type:ab")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin:broadcast")],
    ])
    return keyboard


def get_broadcast_type_keyboard():
    """Клавиатура выбора типа уведомления"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="broadcast_type:info")],
        [InlineKeyboardButton(text="🔧 Технические работы", callback_data="broadcast_type:maintenance")],
        [InlineKeyboardButton(text="🔒 Безопасность", callback_data="broadcast_type:security")],
        [InlineKeyboardButton(text="🎯 Промо", callback_data="broadcast_type:promo")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin:broadcast")],
    ])
    return keyboard


def get_broadcast_segment_keyboard():
    """Клавиатура выбора сегмента получателей"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Все пользователи", callback_data="broadcast_segment:all_users")],
        [InlineKeyboardButton(text="🔐 Только активные подписки", callback_data="broadcast_segment:active_subscriptions")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin:broadcast")],
    ])
    return keyboard


def get_broadcast_confirm_keyboard():
    """Клавиатура подтверждения отправки уведомления"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast:confirm_send")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast")],
    ])
    return keyboard


def get_ab_test_list_keyboard(ab_tests: list) -> InlineKeyboardMarkup:
    """Клавиатура списка A/B тестов"""
    buttons = []
    for test in ab_tests[:20]:  # Ограничиваем 20 тестами
        test_id = test["id"]
        title = test["title"][:30] + "..." if len(test["title"]) > 30 else test["title"]
        created_at = test["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        date_str = created_at.strftime("%d.%m.%Y")
        button_text = f"#{test_id} {title} ({date_str})"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"broadcast:ab_stat:{test_id}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin:broadcast")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_export_keyboard():
    """Клавиатура выбора типа экспорта"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:export:users")],
        [InlineKeyboardButton(text="🔑 Активные подписки", callback_data="admin:export:subscriptions")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")],
    ])
    return keyboard


def get_admin_user_keyboard(has_active_subscription: bool = False, user_id: int = None, has_discount: bool = False, is_vip: bool = False):
    """Клавиатура для раздела пользователя"""
    buttons = []
    if has_active_subscription:
        callback_data = f"admin:user_reissue:{user_id}" if user_id else "admin:user_reissue"
        buttons.append([InlineKeyboardButton(text="🔁 Перевыпустить ключ", callback_data=callback_data)])
    if user_id:
        buttons.append([InlineKeyboardButton(text="🧾 История подписок", callback_data=f"admin:user_history:{user_id}")])
        # Кнопки выдачи и лишения доступа (всегда доступны)
        buttons.append([
            InlineKeyboardButton(text="🟢 Выдать доступ", callback_data=f"admin:grant:{user_id}"),
            InlineKeyboardButton(text="🔴 Лишить доступа", callback_data=f"admin:revoke:{user_id}")
        ])
        # Кнопки управления скидками
        if has_discount:
            buttons.append([InlineKeyboardButton(text="❌ Удалить скидку", callback_data=f"admin:discount_delete:{user_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="🎯 Назначить скидку", callback_data=f"admin:discount_create:{user_id}")])
        # Кнопки управления VIP-статусом
        if is_vip:
            buttons.append([InlineKeyboardButton(text="❌ Снять VIP", callback_data=f"admin:vip_revoke:{user_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="👑 Выдать VIP", callback_data=f"admin:vip_grant:{user_id}")])
        # Кнопка выдачи средств
        buttons.append([InlineKeyboardButton(text="💰 Выдать средства", callback_data=f"admin:credit_balance:{user_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def get_admin_payment_keyboard(payment_id: int):
    """Клавиатура для администратора (подтверждение/отклонение платежа)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"approve_payment:{payment_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"reject_payment:{payment_id}"
            ),
        ],
    ])
    return keyboard
