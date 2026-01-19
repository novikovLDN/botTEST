from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, LabeledPrice, PreCheckoutQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram.filters import StateFilter
from datetime import datetime, timedelta
import logging
import database
import localization
import config
import time
import csv
import tempfile
import os
import asyncio
import random
from typing import Optional, Dict, Any
from keyboards.admin import (
    get_admin_dashboard_keyboard, get_admin_back_keyboard,
    get_reissue_notification_keyboard, get_broadcast_test_type_keyboard,
    get_broadcast_type_keyboard, get_broadcast_segment_keyboard,
    get_broadcast_confirm_keyboard, get_ab_test_list_keyboard,
    get_admin_export_keyboard, get_admin_user_keyboard,
    get_admin_payment_keyboard
)
from states import (
    AdminUserSearch, AdminReferralSearch, BroadcastCreate, IncidentEdit,
    AdminGrantAccess, AdminDiscountCreate, AdminCreditBalance, PurchaseState,
    PromoCodeInput, TopUpStates
)
from utils.referral import send_referral_cashback_notification
from utils.messages import safe_edit_text

# Время запуска бота (для uptime)
_bot_start_time = time.time()
router = Router()

# Инициализация logger
logger = logging.getLogger(__name__)













async def format_promo_stats_text(stats: list) -> str:
    """Форматировать статистику промокодов в текст"""
    if not stats:
        return "Промокоды не найдены."
    
    text = "📊 Статистика промокодов\n\n"
    
    for promo in stats:
        code = promo["code"]
        discount_percent = promo["discount_percent"]
        max_uses = promo["max_uses"]
        used_count = promo["used_count"]
        is_active = promo["is_active"]
        
        text += f"{code}\n"
        text += f"— Скидка: {discount_percent}%\n"
        
        if max_uses is not None:
            text += f"— Использовано: {used_count} / {max_uses}\n"
            if is_active:
                text += "— Статус: активен\n"
            else:
                text += "— Статус: исчерпан\n"
        else:
            text += f"— Использовано: {used_count}\n"
            text += "— Статус: без ограничений\n"
        
        text += "\n"
    
    return text


@router.message(Command("promo_stats"))
async def cmd_promo_stats(message: Message):
    """Команда для просмотра статистики промокодов (только для администратора)"""
    telegram_id = message.from_user.id
    
    # Проверяем, что пользователь - администратор
    if telegram_id != config.ADMIN_TELEGRAM_ID:
        user = await database.get_user(telegram_id)
        language = user.get("language", "ru") if user else "ru"
        await message.answer(localization.get_text(language, "error_access_denied"))
        return
    
    try:
        # Получаем статистику промокодов
        stats = await database.get_promo_stats()
        
        # Формируем текст ответа
        text = await format_promo_stats_text(stats)
        await message.answer(text)
    except Exception as e:
        logger.error(f"Error getting promo stats: {e}")
        await message.answer("Ошибка при получении статистики промокодов.")












@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Административный дашборд"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        logging.warning(f"Unauthorized admin dashboard attempt by user {message.from_user.id}")
        await message.answer("Недостаточно прав доступа")
        return
    
    text = "🛠 Atlas Secure · Admin Dashboard\n\nВыберите действие:"
    await message.answer(text, reply_markup=get_admin_dashboard_keyboard())


@router.callback_query(F.data == "admin:main")
async def callback_admin_main(callback: CallbackQuery):
    """
    Главный экран админ-дашборда
    
    - Проверяет права доступа
    - Показывает админ-дашборд
    - Вызывает callback.answer() для мгновенного отклика
    """
    # ДИАГНОСТИКА: Логируем, что handler вызван
    logger.info(f"✅ callback_admin_main handler MATCHED: callback_data='{callback.data}'")
    
    # Отвечаем сразу для мгновенного отклика UI
    await callback.answer()
    
    # Проверяем права доступа
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        text = "🛠 Atlas Secure · Admin Dashboard\n\nВыберите действие:"
        await safe_edit_text(callback.message, text, reply_markup=get_admin_dashboard_keyboard())
        logger.debug(f"Admin dashboard shown for user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error in callback_admin_main: {e}", exc_info=True)
        try:
            await callback.answer("Ошибка при открытии админ-панели", show_alert=True)
        except:
            pass


@router.callback_query(F.data == "admin_promo_stats")
async def callback_admin_promo_stats(callback: CallbackQuery):
    """
    Обработчик кнопки статистики промокодов в админ-дашборде
    
    - Проверяет права доступа
    - Показывает статистику промокодов
    - Вызывает callback.answer() для мгновенного отклика
    """
    # Отвечаем сразу для мгновенного отклика UI
    await callback.answer()
    
    # Проверяем права доступа
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        # Уже ответили выше, но показываем alert для ошибки доступа
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Получаем статистику промокодов
        stats = await database.get_promo_stats()
        
        # Формируем текст ответа
        text = await format_promo_stats_text(stats)
        
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        logger.debug(f"Admin promo stats shown for user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error getting promo stats: {e}", exc_info=True)
        try:
            await callback.answer("Ошибка при получении статистики промокодов.", show_alert=True)
        except:
            pass


@router.callback_query(F.data == "admin:metrics")
async def callback_admin_metrics(callback: CallbackQuery):
    """Раздел Метрики"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        metrics = await database.get_business_metrics()
        
        text = "📈 Бизнес-метрики\n\n"
        
        # Среднее время подтверждения оплаты
        approval_time = metrics.get('avg_payment_approval_time_seconds')
        if approval_time:
            minutes = int(approval_time / 60)
            seconds = int(approval_time % 60)
            text += f"⏱ Среднее время подтверждения оплаты: {minutes} мин {seconds} сек\n"
        else:
            text += "⏱ Среднее время подтверждения оплаты: нет данных\n"
        
        # Среднее время жизни подписки
        lifetime = metrics.get('avg_subscription_lifetime_days')
        if lifetime:
            text += f"📅 Среднее время жизни подписки: {lifetime:.1f} дней\n"
        else:
            text += "📅 Среднее время жизни подписки: нет данных\n"
        
        # Количество продлений на пользователя
        renewals = metrics.get('avg_renewals_per_user', 0.0)
        text += f"🔄 Среднее количество продлений на пользователя: {renewals:.2f}\n"
        
        # Процент подтвержденных платежей
        approval_rate = metrics.get('approval_rate_percent', 0.0)
        text += f"✅ Процент подтвержденных платежей: {approval_rate:.1f}%\n"
        
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
        # Логируем действие
        await database._log_audit_event_atomic_standalone("admin_view_metrics", callback.from_user.id, None, "Admin viewed business metrics")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_metrics: {e}")
        await callback.answer("Ошибка при получении метрик. Проверь логи.", show_alert=True)


@router.callback_query(F.data == "admin:stats")
async def callback_admin_stats(callback: CallbackQuery):
    """Раздел Статистика"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        stats = await database.get_admin_stats()
        
        text = "📊 Статистика\n\n"
        text += f"👥 Всего пользователей: {stats['total_users']}\n"
        text += f"🔑 Активных подписок: {stats['active_subscriptions']}\n"
        text += f"⛔ Истёкших подписок: {stats['expired_subscriptions']}\n"
        text += f"💳 Всего платежей: {stats['total_payments']}\n"
        text += f"✅ Подтверждённых платежей: {stats['approved_payments']}\n"
        text += f"❌ Отклонённых платежей: {stats['rejected_payments']}\n"
        text += f"🔓 Свободных VPN-ключей: {stats['free_vpn_keys']}"
        
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
        # Логируем просмотр статистики
        await database._log_audit_event_atomic_standalone("admin_view_stats", callback.from_user.id, None, "Admin viewed statistics")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_stats: {e}")
        await callback.answer("Ошибка при получении статистики", show_alert=True)


@router.callback_query(F.data == "admin:referral_stats")
async def callback_admin_referral_stats(callback: CallbackQuery):
    """Реферальная статистика - главный экран с общей статистикой"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        # Получаем общую статистику
        overall_stats = await database.get_referral_overall_stats()
        
        # Получаем топ рефереров (первые 10, отсортированные по доходу)
        top_referrers = await database.get_admin_referral_stats(
            search_query=None,
            sort_by="total_revenue",
            sort_order="DESC",
            limit=10,
            offset=0
        )
        
        # Безопасная обработка статистики с дефолтами
        if not overall_stats:
            overall_stats = {
                "total_referrers": 0,
                "total_referrals": 0,
                "total_paid_referrals": 0,
                "total_revenue": 0.0,
                "total_cashback_paid": 0.0,
                "avg_cashback_per_referrer": 0.0
            }
        
        # Безопасное извлечение значений с дефолтами
        total_referrers = database.safe_int(overall_stats.get("total_referrers", 0))
        total_referrals = database.safe_int(overall_stats.get("total_referrals", 0))
        total_paid_referrals = database.safe_int(overall_stats.get("total_paid_referrals", 0))
        total_revenue = database.safe_float(overall_stats.get("total_revenue", 0.0))
        total_cashback_paid = database.safe_float(overall_stats.get("total_cashback_paid", 0.0))
        avg_cashback_per_referrer = database.safe_float(overall_stats.get("avg_cashback_per_referrer", 0.0))
        
        # Формируем текст с общей статистикой
        text = "📈 Реферальная статистика\n\n"
        text += "📊 Общая статистика:\n"
        text += f"• Всего рефереров: {total_referrers}\n"
        text += f"• Всего приглашённых: {total_referrals}\n"
        text += f"• Всего оплат: {total_paid_referrals}\n"
        text += f"• Общий доход: {total_revenue:.2f} ₽\n"
        text += f"• Выплачено кешбэка: {total_cashback_paid:.2f} ₽\n"
        text += f"• Средний кешбэк на реферера: {avg_cashback_per_referrer:.2f} ₽\n\n"
        
        # Топ рефереров (безопасная обработка)
        if top_referrers:
            text += "🏆 Топ рефереров:\n\n"
            for idx, stat in enumerate(top_referrers[:10], 1):
                try:
                    # Безопасное извлечение значений
                    referrer_id = stat.get("referrer_id", "N/A")
                    username = stat.get("username") or f"ID{referrer_id}"
                    invited_count = database.safe_int(stat.get("invited_count", 0))
                    paid_count = database.safe_int(stat.get("paid_count", 0))
                    conversion = database.safe_float(stat.get("conversion_percent", 0.0))
                    revenue = database.safe_float(stat.get("total_invited_revenue", 0.0))
                    cashback = database.safe_float(stat.get("total_cashback_paid", 0.0))
                    cashback_percent = database.safe_int(stat.get("current_cashback_percent", 10))
                    
                    text += f"{idx}. @{username} (ID: {referrer_id})\n"
                    text += f"   Оплативших: {paid_count} | Уровень: {cashback_percent}%\n"
                    text += f"   Доход: {revenue:.2f} ₽ | Кешбэк: {cashback:.2f} ₽\n\n"
                except Exception as e:
                    logger.warning(f"Error processing referrer stat in admin dashboard: {e}, stat={stat}")
                    continue  # Пропускаем проблемную строку
        else:
            text += "🏆 Топ рефереров:\nРефереры не найдены.\n\n"
        
        # Клавиатура с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 История начислений", callback_data="admin:referral_history"),
                InlineKeyboardButton(text="📈 Топ рефереров", callback_data="admin:referral_top")
            ],
            [
                InlineKeyboardButton(text="📈 По доходу", callback_data="admin:referral_sort:total_revenue"),
                InlineKeyboardButton(text="👥 По приглашениям", callback_data="admin:referral_sort:invited_count")
            ],
            [
                InlineKeyboardButton(text="💰 По кешбэку", callback_data="admin:referral_sort:cashback_paid"),
                InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:referral_search")
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        # Логируем просмотр статистики
        try:
            await database._log_audit_event_atomic_standalone(
                "admin_view_referral_stats", 
                callback.from_user.id, 
                None, 
                f"Admin viewed referral stats: {total_referrers} referrers"
            )
        except Exception as log_error:
            logger.warning(f"Error logging admin referral stats view: {log_error}")
        
    except Exception as e:
        # Структурированное логирование для разработчиков
        logger.exception(
            f"admin_referral_stats_failed: telegram_id={callback.from_user.id}, handler=callback_admin_referral_stats, error={type(e).__name__}: {e}"
        )
        
        # Graceful fallback: показываем пустую статистику, а не ошибку
        try:
            fallback_text = (
                "📈 Реферальная статистика\n\n"
                "📊 Общая статистика:\n"
                "• Всего рефереров: 0\n"
                "• Всего приглашённых: 0\n"
                "• Всего оплат: 0\n"
                "• Общий доход: 0.00 ₽\n"
                "• Выплачено кешбэка: 0.00 ₽\n"
                "• Средний кешбэк на реферера: 0.00 ₽\n\n"
                "🏆 Топ рефереров:\nРефереры не найдены.\n\n"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📋 История начислений", callback_data="admin:referral_history"),
                    InlineKeyboardButton(text="📈 Топ рефереров", callback_data="admin:referral_top")
                ],
                [
                    InlineKeyboardButton(text="📈 По доходу", callback_data="admin:referral_sort:total_revenue"),
                    InlineKeyboardButton(text="👥 По приглашениям", callback_data="admin:referral_sort:invited_count")
                ],
                [
                    InlineKeyboardButton(text="💰 По кешбэку", callback_data="admin:referral_sort:cashback_paid"),
                    InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:referral_search")
                ],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
            ])
            
            await safe_edit_text(callback.message, fallback_text, reply_markup=keyboard)
        except Exception as fallback_error:
            logger.exception(f"Error in fallback admin referral stats: {fallback_error}")
            await callback.answer("Ошибка при получении реферальной статистики", show_alert=True)


@router.callback_query(F.data.startswith("admin:referral_sort:"))
async def callback_admin_referral_sort(callback: CallbackQuery):
    """Сортировка реферальной статистики"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        # Извлекаем параметр сортировки
        sort_by = callback.data.split(":")[-1]
        
        # Получаем статистику с новой сортировкой
        stats_list = await database.get_admin_referral_stats(
            search_query=None,
            sort_by=sort_by,
            sort_order="DESC",
            limit=20,
            offset=0
        )
        
        if not stats_list:
            text = "📊 Реферальная статистика\n\nРефереры не найдены."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
            ])
            await safe_edit_text(callback.message, text, reply_markup=keyboard)
            return
        
        # Формируем текст со статистикой
        sort_labels = {
            "total_revenue": "По доходу",
            "invited_count": "По приглашениям",
            "cashback_paid": "По кешбэку"
        }
        sort_label = sort_labels.get(sort_by, "По доходу")
        
        text = f"📊 Реферальная статистика\nСортировка: {sort_label}\n\n"
        text += f"Всего рефереров: {len(stats_list)}\n\n"
        
        # Показываем топ-10 рефереров
        for idx, stat in enumerate(stats_list[:10], 1):
            username = stat["username"]
            invited_count = stat["invited_count"]
            paid_count = stat["paid_count"]
            conversion = stat["conversion_percent"]
            revenue = stat["total_invited_revenue"]
            cashback = stat["total_cashback_paid"]
            cashback_percent = stat["current_cashback_percent"]
            
            text += f"{idx}. @{username} (ID: {stat['referrer_id']})\n"
            text += f"   Приглашено: {invited_count} | Оплатили: {paid_count} ({conversion}%)\n"
            text += f"   Доход: {revenue:.2f} ₽ | Кешбэк: {cashback:.2f} ₽ ({cashback_percent}%)\n\n"
        
        if len(stats_list) > 10:
            text += f"... и еще {len(stats_list) - 10} рефереров\n\n"
        
        # Клавиатура с кнопками фильтров и сортировки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 По доходу", callback_data="admin:referral_sort:total_revenue"),
                InlineKeyboardButton(text="👥 По приглашениям", callback_data="admin:referral_sort:invited_count")
            ],
            [
                InlineKeyboardButton(text="💰 По кешбэку", callback_data="admin:referral_sort:cashback_paid"),
                InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:referral_search")
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_referral_sort: {e}")
        await callback.answer("Ошибка при сортировке статистики", show_alert=True)


@router.callback_query(F.data == "admin:referral_search")
async def callback_admin_referral_search(callback: CallbackQuery, state: FSMContext):
    """Поиск реферальной статистики"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    text = "🔍 Поиск реферальной статистики\n\nВведите telegram_id или username для поиска:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:referral_stats")]
    ])
    
    await safe_edit_text(callback.message, text, reply_markup=keyboard)
    await state.set_state(AdminReferralSearch.waiting_for_search_query)


@router.message(AdminReferralSearch.waiting_for_search_query)
async def process_admin_referral_search(message: Message, state: FSMContext):
    """Обработка поискового запроса"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        await message.answer("Недостаточно прав доступа")
        await state.clear()
        return
    
    search_query = message.text.strip()
    await state.clear()
    
    try:
        # Получаем статистику с поисковым запросом
        stats_list = await database.get_admin_referral_stats(
            search_query=search_query,
            sort_by="total_revenue",
            sort_order="DESC",
            limit=20,
            offset=0
        )
        
        if not stats_list:
            text = f"📊 Реферальная статистика\n\nПо запросу '{search_query}' ничего не найдено."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:referral_stats")]
            ])
            await message.answer(text, reply_markup=keyboard)
            return
        
        # Формируем текст со статистикой
        text = f"📊 Реферальная статистика\nПоиск: '{search_query}'\n\n"
        text += f"Найдено рефереров: {len(stats_list)}\n\n"
        
        # Показываем результаты поиска
        for idx, stat in enumerate(stats_list[:10], 1):
            username = stat["username"]
            invited_count = stat["invited_count"]
            paid_count = stat["paid_count"]
            conversion = stat["conversion_percent"]
            revenue = stat["total_invited_revenue"]
            cashback = stat["total_cashback_paid"]
            cashback_percent = stat["current_cashback_percent"]
            
            text += f"{idx}. @{username} (ID: {stat['referrer_id']})\n"
            text += f"   Приглашено: {invited_count} | Оплатили: {paid_count} ({conversion}%)\n"
            text += f"   Доход: {revenue:.2f} ₽ | Кешбэк: {cashback:.2f} ₽ ({cashback_percent}%)\n\n"
        
        if len(stats_list) > 10:
            text += f"... и еще {len(stats_list) - 10} рефереров\n\n"
        
        # Клавиатура
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 По доходу", callback_data="admin:referral_sort:total_revenue"),
                InlineKeyboardButton(text="👥 По приглашениям", callback_data="admin:referral_sort:invited_count")
            ],
            [
                InlineKeyboardButton(text="💰 По кешбэку", callback_data="admin:referral_sort:cashback_paid"),
                InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:referral_search")
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        
    except Exception as e:
        logging.exception(f"Error in process_admin_referral_search: {e}")
        await message.answer("Ошибка при поиске статистики")


@router.callback_query(F.data.startswith("admin:referral_detail:"))
async def callback_admin_referral_detail(callback: CallbackQuery):
    """Детальная информация по рефереру"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        # Извлекаем referrer_id
        referrer_id = int(callback.data.split(":")[-1])
        
        # Получаем детальную информацию
        detail = await database.get_admin_referral_detail(referrer_id)
        
        if not detail:
            await callback.answer("Реферер не найден", show_alert=True)
            return
        
        # Формируем текст с детальной информацией
        username = detail["username"]
        invited_list = detail["invited_list"]
        
        text = f"📊 Детали реферера\n\n"
        text += f"@{username} (ID: {referrer_id})\n\n"
        text += f"Всего приглашено: {len(invited_list)}\n\n"
        
        if invited_list:
            text += "Приглашённые пользователи:\n\n"
            for idx, invited in enumerate(invited_list[:15], 1):  # Ограничение 15 записей для читаемости
                invited_username = invited["username"]
                registered_at = invited["registered_at"]
                first_payment = invited["first_payment_date"]
                purchase_amount = invited["purchase_amount"]
                cashback_amount = invited["cashback_amount"]
                
                text += f"{idx}. @{invited_username} (ID: {invited['invited_user_id']})\n"
                text += f"   Зарегистрирован: {registered_at.strftime('%Y-%m-%d') if registered_at else 'N/A'}\n"
                if first_payment:
                    text += f"   Первая оплата: {first_payment.strftime('%Y-%m-%d')}\n"
                    text += f"   Сумма: {purchase_amount:.2f} ₽ | Кешбэк: {cashback_amount:.2f} ₽\n"
                else:
                    text += f"   Оплаты нет\n"
                text += "\n"
            
            if len(invited_list) > 15:
                text += f"... и еще {len(invited_list) - 15} пользователей\n\n"
        else:
            text += "Приглашённые пользователи отсутствуют.\n\n"
        
        # Клавиатура
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="admin:referral_stats")]
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        # Логируем просмотр деталей
        await database._log_audit_event_atomic_standalone(
            "admin_view_referral_detail", 
            callback.from_user.id, 
            referrer_id, 
            f"Admin viewed referral detail for referrer_id={referrer_id}"
        )
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_referral_detail: {e}")
        await callback.answer("Ошибка при получении деталей", show_alert=True)


@router.callback_query(F.data == "admin:referral_history")
async def callback_admin_referral_history(callback: CallbackQuery):
    """История начислений реферального кешбэка"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        # Получаем историю начислений (первые 20 записей)
        history = await database.get_referral_rewards_history(
            date_from=None,
            date_to=None,
            limit=20,
            offset=0
        )
        
        # Получаем общее количество для пагинации
        total_count = await database.get_referral_rewards_history_count()
        
        if not history:
            text = "📋 История начислений\n\nНачисления не найдены."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:referral_stats")]
            ])
            await safe_edit_text(callback.message, text, reply_markup=keyboard)
            return
        
        # Формируем текст с историей
        text = "📋 История начислений\n\n"
        text += f"Всего записей: {total_count}\n\n"
        
        for idx, reward in enumerate(history[:20], 1):
            referrer = reward["referrer_username"]
            buyer = reward["buyer_username"]
            purchase_amount = reward["purchase_amount"]
            percent = reward["percent"]
            reward_amount = reward["reward_amount"]
            created_at = reward["created_at"].strftime("%d.%m.%Y %H:%M") if reward["created_at"] else "N/A"
            
            text += f"{idx}. {created_at}\n"
            text += f"   Реферер: @{referrer} (ID: {reward['referrer_id']})\n"
            text += f"   Покупатель: @{buyer} (ID: {reward['buyer_id']})\n"
            text += f"   Покупка: {purchase_amount:.2f} ₽ | Кешбэк: {percent}% = {reward_amount:.2f} ₽\n\n"
        
        if total_count > 20:
            text += f"... и еще {total_count - 20} записей\n\n"
        
        # Клавиатура
        keyboard_buttons = []
        if total_count > 20:
            keyboard_buttons.append([
                InlineKeyboardButton(text="➡️ Следующие", callback_data="admin:referral_history:page:1")
            ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin:referral_stats")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        # Логируем просмотр истории
        await database._log_audit_event_atomic_standalone(
            "admin_view_referral_history",
            callback.from_user.id,
            None,
            f"Admin viewed referral history: {len(history)} records"
        )
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_referral_history: {e}")
        await callback.answer("Ошибка при получении истории начислений", show_alert=True)


@router.callback_query(F.data.startswith("admin:referral_history:page:"))
async def callback_admin_referral_history_page(callback: CallbackQuery):
    """Пагинация истории начислений"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        # Извлекаем номер страницы
        page = int(callback.data.split(":")[-1])
        limit = 20
        offset = page * limit
        
        # Получаем историю начислений
        history = await database.get_referral_rewards_history(
            date_from=None,
            date_to=None,
            limit=limit,
            offset=offset
        )
        
        # Получаем общее количество
        total_count = await database.get_referral_rewards_history_count()
        total_pages = (total_count + limit - 1) // limit
        
        if not history:
            text = "📋 История начислений\n\nНачисления не найдены."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:referral_stats")]
            ])
            await safe_edit_text(callback.message, text, reply_markup=keyboard)
            return
        
        # Формируем текст
        text = f"📋 История начислений (стр. {page + 1}/{total_pages})\n\n"
        text += f"Всего записей: {total_count}\n\n"
        
        for idx, reward in enumerate(history, 1):
            referrer = reward["referrer_username"]
            buyer = reward["buyer_username"]
            purchase_amount = reward["purchase_amount"]
            percent = reward["percent"]
            reward_amount = reward["reward_amount"]
            created_at = reward["created_at"].strftime("%d.%m.%Y %H:%M") if reward["created_at"] else "N/A"
            
            text += f"{offset + idx}. {created_at}\n"
            text += f"   Реферер: @{referrer} (ID: {reward['referrer_id']})\n"
            text += f"   Покупатель: @{buyer} (ID: {reward['buyer_id']})\n"
            text += f"   Покупка: {purchase_amount:.2f} ₽ | Кешбэк: {percent}% = {reward_amount:.2f} ₽\n\n"
        
        # Клавиатура с пагинацией
        keyboard_buttons = []
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:referral_history:page:{page - 1}"))
        if offset + limit < total_count:
            nav_buttons.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"admin:referral_history:page:{page + 1}"))
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin:referral_stats")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_referral_history_page: {e}")
        await callback.answer("Ошибка при получении истории начислений", show_alert=True)


@router.callback_query(F.data == "admin:referral_top")
async def callback_admin_referral_top(callback: CallbackQuery):
    """Топ рефереров - расширенный список"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        # Получаем топ рефереров (50 лучших)
        top_referrers = await database.get_admin_referral_stats(
            search_query=None,
            sort_by="total_revenue",
            sort_order="DESC",
            limit=50,
            offset=0
        )
        
        if not top_referrers:
            text = "🏆 Топ рефереров\n\nРефереры не найдены."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:referral_stats")]
            ])
            await safe_edit_text(callback.message, text, reply_markup=keyboard)
            return
        
        # Формируем текст
        text = "🏆 Топ рефереров\n\n"
        
        for idx, stat in enumerate(top_referrers, 1):
            username = stat["username"]
            invited_count = stat["invited_count"]
            paid_count = stat["paid_count"]
            conversion = stat["conversion_percent"]
            revenue = stat["total_invited_revenue"]
            cashback = stat["total_cashback_paid"]
            cashback_percent = stat["current_cashback_percent"]
            
            text += f"{idx}. @{username} (ID: {stat['referrer_id']})\n"
            text += f"   Приглашено: {invited_count} | Оплатили: {paid_count} ({conversion}%)\n"
            text += f"   Доход: {revenue:.2f} ₽ | Кешбэк: {cashback:.2f} ₽ ({cashback_percent}%)\n\n"
        
        # Клавиатура
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 По доходу", callback_data="admin:referral_sort:total_revenue"),
                InlineKeyboardButton(text="👥 По приглашениям", callback_data="admin:referral_sort:invited_count")
            ],
            [
                InlineKeyboardButton(text="💰 По кешбэку", callback_data="admin:referral_sort:cashback_paid"),
                InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:referral_search")
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:referral_stats")]
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        # Логируем просмотр топа
        await database._log_audit_event_atomic_standalone(
            "admin_view_referral_top",
            callback.from_user.id,
            None,
            f"Admin viewed top referrers: {len(top_referrers)} referrers"
        )
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_referral_top: {e}")
        await callback.answer("Ошибка при получении топа рефереров", show_alert=True)


@router.callback_query(F.data == "admin:analytics")
async def callback_admin_analytics(callback: CallbackQuery):
    """📊 Финансовая аналитика - базовые метрики"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Получаем базовые метрики (оптимизированные запросы)
        total_revenue = await database.get_total_revenue()
        paying_users_count = await database.get_paying_users_count()
        arpu = await database.get_arpu()
        avg_ltv = await database.get_ltv()
        
        # Формируем отчет (краткий и понятный)
        text = (
            f"📊 Финансовая аналитика\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Общий доход\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"   {total_revenue:,.2f} ₽\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Платящие пользователи\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"   {paying_users_count} чел.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 ARPU (Average Revenue Per User)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"   {arpu:,.2f} ₽\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 Средний LTV (Lifetime Value)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"   {avg_ltv:,.2f} ₽\n"
        )
        
        # Клавиатура
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:analytics")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        await callback.answer()
        
        # Логируем действие
        await database._log_audit_event_atomic_standalone(
            "admin_view_analytics",
            callback.from_user.id,
            None,
            "Admin viewed financial analytics"
        )
        
    except Exception as e:
        logger.exception(f"Error in admin analytics: {e}")
        await callback.answer("Ошибка загрузки аналитики", show_alert=True)
        await callback.answer("Ошибка при расчете аналитики", show_alert=True)


@router.callback_query(F.data == "admin:analytics:monthly")
async def callback_admin_analytics_monthly(callback: CallbackQuery):
    """Ежемесячная сводка"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        now = datetime.now()
        current_month = await database.get_monthly_summary(now.year, now.month)
        
        # Предыдущий месяц
        if now.month == 1:
            prev_month = await database.get_monthly_summary(now.year - 1, 12)
        else:
            prev_month = await database.get_monthly_summary(now.year, now.month - 1)
        
        text = (
            f"📅 Ежемесячная сводка\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Текущий месяц ({current_month['year']}-{current_month['month']:02d})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"   Доход: {current_month['revenue']:.2f} ₽\n"
            f"   Платежей: {current_month['payments_count']}\n"
            f"   Новых пользователей: {current_month['new_users']}\n"
            f"   Новых подписок: {current_month['new_subscriptions']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Предыдущий месяц ({prev_month['year']}-{prev_month['month']:02d})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"   Доход: {prev_month['revenue']:.2f} ₽\n"
            f"   Платежей: {prev_month['payments_count']}\n"
            f"   Новых пользователей: {prev_month['new_users']}\n"
            f"   Новых подписок: {prev_month['new_subscriptions']}\n\n"
        )
        
        # Сравнение
        revenue_change = current_month['revenue'] - prev_month['revenue']
        revenue_change_percent = (revenue_change / prev_month['revenue'] * 100) if prev_month['revenue'] > 0 else 0
        
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Изменение дохода\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"   Изменение: {revenue_change:+.2f} ₽ ({revenue_change_percent:+.1f}%)\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к аналитике", callback_data="admin:analytics")]
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.exception(f"Error in monthly analytics: {e}")
        await callback.answer("Ошибка при получении ежемесячной сводки", show_alert=True)


@router.callback_query(F.data == "admin:audit")
async def callback_admin_audit(callback: CallbackQuery):
    """Раздел Аудит (переиспользование логики /admin_audit)"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Получаем последние 10 записей из audit_log
        audit_logs = await database.get_last_audit_logs(limit=10)
        
        if not audit_logs:
            text = "📜 Аудит\n\nАудит пуст. Действий не зафиксировано."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer()
            return
        
        # Формируем сообщение
        lines = ["📜 Аудит", ""]
        
        for log in audit_logs:
            # Форматируем дату и время
            created_at = log["created_at"]
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            elif isinstance(created_at, datetime):
                pass
            else:
                created_at = datetime.now()
            
            created_str = created_at.strftime("%Y-%m-%d %H:%M")
            
            lines.append(f"🕒 {created_str}")
            lines.append(f"Действие: {log['action']}")
            lines.append(f"Админ: {log['telegram_id']}")
            
            if log['target_user']:
                lines.append(f"Пользователь: {log['target_user']}")
            else:
                lines.append("Пользователь: —")
            
            if log['details']:
                details = log['details']
                if len(details) > 150:
                    details = details[:150] + "..."
                lines.append(f"Детали: {details}")
            else:
                lines.append("Детали: —")
            
            lines.append("")
            lines.append("⸻")
            lines.append("")
        
        # Убираем последний разделитель
        if lines[-1] == "" and lines[-2] == "⸻":
            lines = lines[:-2]
        
        text = "\n".join(lines)
        
        # Проверяем лимит Telegram (4096 символов на сообщение)
        if len(text) > 4000:
            # Уменьшаем до 5 записей
            audit_logs = await database.get_last_audit_logs(limit=5)
            lines = ["📜 Аудит", ""]
            
            for log in audit_logs:
                created_at = log["created_at"]
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                elif isinstance(created_at, datetime):
                    pass
                else:
                    created_at = datetime.now()
                
                created_str = created_at.strftime("%Y-%m-%d %H:%M")
                
                lines.append(f"🕒 {created_str}")
                lines.append(f"Действие: {log['action']}")
                lines.append(f"Админ: {log['telegram_id']}")
                
                if log['target_user']:
                    lines.append(f"Пользователь: {log['target_user']}")
                else:
                    lines.append("Пользователь: —")
                
                if log['details']:
                    details = log['details']
                    if len(details) > 100:
                        details = details[:100] + "..."
                    lines.append(f"Детали: {details}")
                else:
                    lines.append("Детали: —")
                
                lines.append("")
                lines.append("⸻")
                lines.append("")
            
            if lines[-1] == "" and lines[-2] == "⸻":
                lines = lines[:-2]
            
            text = "\n".join(lines)
        
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
        # Логируем просмотр аудита
        await database._log_audit_event_atomic_standalone("admin_view_audit", callback.from_user.id, None, "Admin viewed audit log")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_audit: {e}")
        await callback.answer("Ошибка при получении audit log", show_alert=True)


@router.callback_query(F.data == "admin:keys")
async def callback_admin_keys(callback: CallbackQuery):
    """Раздел VPN-ключи в админ-дашборде"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Показываем меню управления ключами
        text = "🔑 Управление VPN-ключами\n\n"
        text += "Доступные действия:\n"
        text += "• Перевыпустить ключ для одного пользователя\n"
        text += "• Перевыпустить ключи для всех активных пользователей\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Перевыпустить для пользователя", callback_data="admin:user")],
            [InlineKeyboardButton(text="🔄 Перевыпустить все ключи", callback_data="admin:keys:reissue_all")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_keys: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data == "admin:keys:reissue_all")
async def callback_admin_keys_reissue_all(callback: CallbackQuery, bot: Bot):
    """Массовый перевыпуск ключей для всех активных пользователей"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer("Начинаю массовый перевыпуск...")
    
    try:
        admin_telegram_id = callback.from_user.id
        
        # Получаем все активные подписки
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            now = datetime.now()
            subscriptions = await conn.fetch(
                """SELECT telegram_id, uuid, vpn_key, expires_at 
                   FROM subscriptions 
                   WHERE status = 'active' 
                   AND expires_at > $1 
                   AND uuid IS NOT NULL
                   ORDER BY telegram_id""",
                now
            )
        
        total_count = len(subscriptions)
        success_count = 0
        failed_count = 0
        failed_users = []
        
        if total_count == 0:
            await safe_edit_text(
                callback.message,
                "❌ Нет активных подписок для перевыпуска",
                reply_markup=get_admin_back_keyboard()
            )
            return
        
        # Отправляем начальное сообщение
        status_text = f"🔄 Массовый перевыпуск ключей\n\nВсего пользователей: {total_count}\nОбработано: 0/{total_count}\nУспешно: 0\nОшибок: 0"
        status_message = await callback.message.edit_text(status_text, reply_markup=None)
        # Примечание: status_message используется для динамического обновления, защита не нужна
        
        # Обрабатываем каждую подписку
        for idx, sub_row in enumerate(subscriptions, 1):
            subscription = dict(sub_row)
            telegram_id = subscription["telegram_id"]
            
            try:
                # Перевыпускаем ключ
                result = await database.reissue_vpn_key_atomic(telegram_id, admin_telegram_id)
                new_vpn_key, old_vpn_key = result
                
                if new_vpn_key is None:
                    failed_count += 1
                    failed_users.append(telegram_id)
                    logging.error(f"Failed to reissue key for user {telegram_id} in bulk operation")
                    continue
                
                success_count += 1
                
                # Отправляем уведомление пользователю
                try:
                    user_lang = await database.get_user(telegram_id)
                    language = user_lang.get("language", "ru") if user_lang else "ru"
                    
                    try:
                        user_text = localization.get_text(
                            language,
                            "admin_reissue_user_notification",
                            vpn_key=f"<code>{new_vpn_key}</code>"
                        )
                    except (KeyError, TypeError):
                        # Fallback to default if localization not found
                        user_text = get_reissue_notification_text(new_vpn_key)
                    
                    keyboard = get_reissue_notification_keyboard()
                    await bot.send_message(telegram_id, user_text, reply_markup=keyboard, parse_mode="HTML")
                except Exception as e:
                    logging.warning(f"Failed to send reissue notification to user {telegram_id}: {e}")
                
                # Обновляем статус каждые 10 пользователей или в конце
                if idx % 10 == 0 or idx == total_count:
                    status_text = (
                        f"🔄 Массовый перевыпуск ключей\n\n"
                        f"Всего пользователей: {total_count}\n"
                        f"Обработано: {idx}/{total_count}\n"
                        f"✅ Успешно: {success_count}\n"
                        f"❌ Ошибок: {failed_count}"
                    )
                    try:
                        try:
                            await status_message.edit_text(status_text)
                        except TelegramBadRequest as e:
                            if "message is not modified" not in str(e):
                                raise
                    except Exception:
                        pass
                
                # Rate limiting: 1-2 секунды между запросами
                if idx < total_count:
                    import asyncio
                    await asyncio.sleep(1.5)
                    
            except Exception as e:
                failed_count += 1
                failed_users.append(telegram_id)
                logging.exception(f"Error reissuing key for user {telegram_id} in bulk operation: {e}")
                continue
        
        # Финальное сообщение
        final_text = (
            f"✅ Массовый перевыпуск завершён\n\n"
            f"Всего пользователей: {total_count}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {failed_count}"
        )
        
        if failed_users:
            failed_list = ", ".join(map(str, failed_users[:10]))
            if len(failed_users) > 10:
                failed_list += f" и ещё {len(failed_users) - 10}"
            final_text += f"\n\nОшибки у пользователей: {failed_list}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:keys")]
        ])
        
        try:
            await status_message.edit_text(final_text, reply_markup=keyboard)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        
        # Логируем в audit_log
        await database._log_audit_event_atomic_standalone(
            "admin_reissue_all",
            admin_telegram_id,
            None,
            f"Bulk reissue: total={total_count}, success={success_count}, failed={failed_count}"
        )
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_keys_reissue_all: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при массовом перевыпуске: {str(e)}",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data.startswith("admin:reissue_key:"))
async def callback_admin_reissue_key(callback: CallbackQuery, bot: Bot):
    """Перевыпуск ключа для одной подписки (по subscription_id)"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Получаем subscription_id из callback_data
        subscription_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат команды", show_alert=True)
        return
    
    admin_telegram_id = callback.from_user.id
    
    try:
        import vpn_utils
        
        # Проверяем, что подписка активна и получаем данные
        subscription = await database.get_active_subscription(subscription_id)
        if not subscription:
            await callback.answer("Подписка не найдена или не активна", show_alert=True)
            return
        
        telegram_id = subscription.get("telegram_id")
        old_uuid = subscription.get("uuid")
        
        if not old_uuid:
            await callback.answer("У подписки нет UUID для перевыпуска", show_alert=True)
            return
        
        # Перевыпускаем ключ
        await callback.answer("Перевыпускаю ключ...")
        
        try:
            new_uuid = await database.reissue_subscription_key(subscription_id)
        except ValueError as e:
            await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
            return
        except Exception as e:
            logging.exception(f"Failed to reissue key for subscription {subscription_id}: {e}")
            await callback.answer(f"Ошибка при перевыпуске ключа: {str(e)}", show_alert=True)
            return
        
        # Генерируем новый VLESS URL для отображения
        try:
            vless_url = vpn_utils.generate_vless_url(new_uuid)
        except Exception as e:
            logging.warning(f"Failed to generate VLESS URL for new UUID: {e}")
            # Fallback: формируем простой VLESS URL
            try:
                vless_url = f"vless://{new_uuid}@{config.XRAY_SERVER_IP}:{config.XRAY_PORT}?encryption=none&security=reality&type=tcp#AtlasSecure"
            except Exception:
                vless_url = f"vless://{new_uuid}@SERVER:443..."
        
        # Показываем админу результат
        user = await database.get_user(telegram_id)
        username = user.get("username", "не указан") if user else "не указан"
        
        expires_at = subscription["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
        
        text = "✅ Ключ успешно перевыпущен\n\n"
        text += f"Подписка ID: {subscription_id}\n"
        text += f"Пользователь: @{username} ({telegram_id})\n"
        text += f"Срок действия: до {expires_str}\n\n"
        text += f"Новый VPN-ключ:\n<code>{vless_url}</code>"
        
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
        await callback.answer("Ключ успешно перевыпущен")
        
        # Логируем в audit_log
        await database._log_audit_event_atomic_standalone(
            "admin_reissue_key",
            admin_telegram_id,
            telegram_id,
            f"Reissued key for subscription_id={subscription_id}, old_uuid={old_uuid[:8]}..., new_uuid={new_uuid[:8]}..."
        )
        
        # НЕ отправляем уведомление пользователю автоматически (согласно требованиям)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_reissue_key: {e}")
        await callback.answer("Ошибка при перевыпуске ключа", show_alert=True)


@router.callback_query(F.data == "admin:reissue_all_active")
async def callback_admin_reissue_all_active(callback: CallbackQuery, bot: Bot):
    """Массовый перевыпуск ключей для всех активных подписок"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer("Начинаю массовый перевыпуск...")
    
    try:
        admin_telegram_id = callback.from_user.id
        
        # Получаем все активные подписки
        subscriptions = await database.get_all_active_subscriptions()
        
        total_count = len(subscriptions)
        success_count = 0
        failed_count = 0
        failed_subscriptions = []
        
        if total_count == 0:
            await safe_edit_text(
                callback.message,
                "❌ Нет активных подписок для перевыпуска",
                reply_markup=get_admin_back_keyboard()
            )
            return
        
        # Отправляем начальное сообщение
        status_text = f"🔄 Массовый перевыпуск ключей\n\nВсего подписок: {total_count}\nОбработано: 0/{total_count}\nУспешно: 0\nОшибок: 0"
        status_message = await callback.message.edit_text(status_text, reply_markup=None)
        # Примечание: status_message используется для динамического обновления, защита не нужна
        
        # Обрабатываем каждую подписку ИТЕРАТИВНО (НЕ параллельно)
        for idx, subscription in enumerate(subscriptions, 1):
            subscription_id = subscription.get("id")
            telegram_id = subscription.get("telegram_id")
            old_uuid = subscription.get("uuid")
            
            if not subscription_id or not old_uuid:
                failed_count += 1
                failed_subscriptions.append(subscription_id or telegram_id)
                continue
            
            try:
                # Перевыпускаем ключ
                new_uuid = await database.reissue_subscription_key(subscription_id)
                success_count += 1
                
                # Обновляем статус каждые 10 подписок или в конце
                if idx % 10 == 0 or idx == total_count:
                    status_text = (
                        f"🔄 Массовый перевыпуск ключей\n\n"
                        f"Всего подписок: {total_count}\n"
                        f"Обработано: {idx}/{total_count}\n"
                        f"✅ Успешно: {success_count}\n"
                        f"❌ Ошибок: {failed_count}"
                    )
                    try:
                        try:
                            await status_message.edit_text(status_text)
                        except TelegramBadRequest as e:
                            if "message is not modified" not in str(e):
                                raise
                    except Exception:
                        pass
                
                # Rate limiting: 1-2 секунды между запросами
                if idx < total_count:
                    import asyncio
                    await asyncio.sleep(1.5)
                    
            except Exception as e:
                failed_count += 1
                failed_subscriptions.append(subscription_id)
                logging.exception(f"Error reissuing key for subscription {subscription_id} (user {telegram_id}) in bulk operation: {e}")
                continue
        
        # Финальное сообщение
        final_text = (
            f"✅ Массовый перевыпуск завершён\n\n"
            f"Всего подписок: {total_count}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {failed_count}"
        )
        
        if failed_subscriptions:
            failed_list = ", ".join(map(str, failed_subscriptions[:10]))
            if len(failed_subscriptions) > 10:
                failed_list += f" и ещё {len(failed_subscriptions) - 10}"
            final_text += f"\n\nОшибки у подписок: {failed_list}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:keys")]
        ])
        
        try:
            await status_message.edit_text(final_text, reply_markup=keyboard)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        
        # Логируем в audit_log
        await database._log_audit_event_atomic_standalone(
            "admin_reissue_all_active",
            admin_telegram_id,
            None,
            f"Bulk reissue: total={total_count}, success={success_count}, failed={failed_count}"
        )
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_reissue_all_active: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при массовом перевыпуске: {str(e)}",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data.startswith("admin:keys:"))
async def callback_admin_keys_legacy(callback: CallbackQuery):
    """Раздел VPN-ключи"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        stats = await database.get_vpn_keys_stats()
        
        text = "🔑 VPN-ключи\n\n"
        text += f"Всего ключей: {stats['total']}\n"
        text += f"Использованных: {stats['used']}\n"
        
        if stats['free'] <= 5:
            text += f"⚠️ Свободных: {stats['free']}\n"
            text += "\n⚠️ ВНИМАНИЕ: Количество свободных ключей критически низкое!"
        else:
            text += f"Свободных: {stats['free']}"
        
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
        # Логируем просмотр статистики ключей
        await database._log_audit_event_atomic_standalone("admin_view_keys", callback.from_user.id, None, f"Admin viewed VPN keys stats: {stats['free']} free")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_keys: {e}")
        await callback.answer("Ошибка при получении статистики ключей", show_alert=True)


@router.callback_query(F.data == "admin:user")
async def callback_admin_user(callback: CallbackQuery, state: FSMContext):
    """Раздел Пользователь - запрос Telegram ID или username"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    text = "👤 Пользователь\n\nВведите Telegram ID или username пользователя:"
    await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard())
    await state.set_state(AdminUserSearch.waiting_for_user_id)
    await callback.answer()


@router.message(AdminUserSearch.waiting_for_user_id)
async def process_admin_user_id(message: Message, state: FSMContext):
    """Обработка введённого Telegram ID или username пользователя"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        await message.answer("Недостаточно прав доступа")
        await state.clear()
        return
    
    try:
        user_input = message.text.strip()
        
        # Определяем, является ли ввод числом (ID) или строкой (username)
        try:
            target_user_id = int(user_input)
            # Это число - ищем по ID
            user = await database.find_user_by_id_or_username(telegram_id=target_user_id)
            search_by = "ID"
            search_value = str(target_user_id)
        except ValueError:
            # Это строка - ищем по username
            username = user_input.lstrip('@')  # Убираем @, если есть
            if not username:  # Пустая строка после удаления @
                await message.answer("Пользователь не найден.\nПроверьте Telegram ID или username.")
                await state.clear()
                return
            username = username.lower()  # Приводим к нижнему регистру
            user = await database.find_user_by_id_or_username(username=username)
            search_by = "username"
            search_value = username
        
        # Если пользователь не найден
        if not user:
            await message.answer("Пользователь не найден.\nПроверьте Telegram ID или username.")
            await state.clear()
            return
        
        # Получаем информацию о подписке
        subscription = await database.get_subscription(user["telegram_id"])
        
        # Получаем расширенную статистику
        stats = await database.get_user_extended_stats(user["telegram_id"])
        
        # Формируем карточку пользователя
        text = "👤 Пользователь\n\n"
        text += f"Telegram ID: {user['telegram_id']}\n"
        username_display = user.get('username') or 'не указан'
        text += f"Username: @{username_display}\n"
        
        # Язык
        user_language = user.get('language') or 'ru'
        language_display = localization.LANGUAGE_BUTTONS.get(user_language, user_language)
        text += f"Язык: {language_display}\n"
        
        # Дата регистрации
        created_at = user.get('created_at')
        if created_at:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            created_str = created_at.strftime("%d.%m.%Y %H:%M")
            text += f"Дата регистрации: {created_str}\n"
        else:
            text += "Дата регистрации: —\n"
        
        text += "\n"
        
        if subscription:
            expires_at = subscription["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
            
            now = datetime.now()
            if expires_at > now:
                text += "Статус подписки: ✅ Активна\n"
            else:
                text += "Статус подписки: ⛔ Истекла\n"
            
            text += f"Срок действия: до {expires_str}\n"
            text += f"VPN-ключ: {subscription['vpn_key']}\n"
        else:
            text += "Статус подписки: ❌ Нет подписки\n"
            text += "VPN-ключ: —\n"
            text += "Срок действия: —\n"
        
        # Статистика
        text += f"\nКоличество продлений: {stats['renewals_count']}\n"
        text += f"Количество перевыпусков: {stats['reissues_count']}\n"
        
        # Проверяем наличие персональной скидки
        user_discount = await database.get_user_discount(user["telegram_id"])
        has_discount = user_discount is not None
        
        # Проверяем VIP-статус (явно определяем переменную)
        is_vip = await database.is_vip_user(user["telegram_id"])
        
        if user_discount:
            discount_percent = user_discount["discount_percent"]
            expires_at_discount = user_discount.get("expires_at")
            if expires_at_discount:
                if isinstance(expires_at_discount, str):
                    expires_at_discount = datetime.fromisoformat(expires_at_discount.replace('Z', '+00:00'))
                expires_str = expires_at_discount.strftime("%d.%m.%Y %H:%M")
                text += f"\n🎯 Персональная скидка: {discount_percent}% (до {expires_str})\n"
            else:
                text += f"\n🎯 Персональная скидка: {discount_percent}% (бессрочно)\n"
        
        # Добавляем информацию о VIP-статусе
        if is_vip:
            text += f"\n👑 VIP-статус: активен\n"
        
        if subscription:
            expires_at = subscription["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            now = datetime.now()
            has_active = expires_at > now
            await message.answer(text, reply_markup=get_admin_user_keyboard(has_active_subscription=has_active, user_id=user["telegram_id"], has_discount=has_discount, is_vip=is_vip), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=get_admin_user_keyboard(has_active_subscription=False, user_id=user["telegram_id"], has_discount=has_discount, is_vip=is_vip), parse_mode="HTML")
        
        # Логируем просмотр информации о пользователе
        details = f"Admin searched by {search_by}: {search_value}, found user {user['telegram_id']}"
        await database._log_audit_event_atomic_standalone("admin_view_user", message.from_user.id, user["telegram_id"], details)
        
        await state.clear()
        
    except Exception as e:
        logging.exception(f"Error in process_admin_user_id: {e}")
        await message.answer("Ошибка при получении информации о пользователе. Проверь логи.")
        await state.clear()


@router.callback_query(F.data.startswith("admin:user_history:"))
async def callback_admin_user_history(callback: CallbackQuery):
    """История подписок пользователя (админ)"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Получаем user_id из callback_data
        target_user_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат команды", show_alert=True)
        return
    
    try:
        # Получаем историю подписок
        history = await database.get_subscription_history(target_user_id, limit=10)
        
        if not history:
            text = "🧾 История подписок\n\nИстория подписок пуста."
            await callback.message.answer(text, reply_markup=get_admin_back_keyboard())
            await callback.answer()
            return
        
        # Формируем текст истории
        text = "🧾 История подписок\n\n"
        
        action_type_map = {
            "purchase": "Покупка",
            "renewal": "Продление",
            "reissue": "Выдача нового ключа",
            "manual_reissue": "Перевыпуск ключа",
        }
        
        for record in history:
            start_date = record["start_date"]
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            start_str = start_date.strftime("%d.%m.%Y")
            
            end_date = record["end_date"]
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date)
            end_str = end_date.strftime("%d.%m.%Y")
            
            action_type = record["action_type"]
            action_text = action_type_map.get(action_type, action_type)
            
            text += f"• {start_str} — {action_text}\n"
            
            # Для purchase и reissue показываем ключ
            if action_type in ["purchase", "reissue", "manual_reissue"]:
                text += f"  Ключ: {record['vpn_key']}\n"
            
            text += f"  До: {end_str}\n\n"
        
        await callback.message.answer(text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
        # Логируем просмотр истории
        await database._log_audit_event_atomic_standalone("admin_view_user_history", callback.from_user.id, target_user_id, f"Admin viewed subscription history for user {target_user_id}")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_user_history: {e}")
        await callback.answer("Ошибка при получении истории подписок", show_alert=True)


def get_admin_grant_days_keyboard(user_id: int):
    """Клавиатура для выбора срока доступа (1/7/14 дней, 1 год или 10 минут)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 день", callback_data=f"admin:grant_days:{user_id}:1"),
            InlineKeyboardButton(text="7 дней", callback_data=f"admin:grant_days:{user_id}:7"),
        ],
        [
            InlineKeyboardButton(text="14 дней", callback_data=f"admin:grant_days:{user_id}:14"),
        ],
        [
            InlineKeyboardButton(text="🗓 Выдать доступ на 1 год", callback_data=f"admin:grant_1_year:{user_id}"),
        ],
        [
            InlineKeyboardButton(text="⏱ Доступ на 10 минут", callback_data=f"admin:grant_minutes:{user_id}:10"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin:user"),
        ]
    ])
    return keyboard


@router.callback_query(F.data.startswith("admin:grant:"))
async def callback_admin_grant(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Выдать доступ'"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        # Сохраняем user_id в состоянии
        await state.update_data(user_id=user_id)
        
        # Показываем клавиатуру выбора срока
        text = "Выберите срок доступа:"
        await callback.message.edit_text(text, reply_markup=get_admin_grant_days_keyboard(user_id))
        await state.set_state(AdminGrantAccess.waiting_for_days)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_grant: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data.startswith("admin:grant_days:"))
async def callback_admin_grant_days(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора срока доступа"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        parts = callback.data.split(":")
        user_id = int(parts[2])
        days = int(parts[3])
        
        # Выдаем доступ через grant_access
        try:
            expires_at, vpn_key = await database.admin_grant_access_atomic(
                telegram_id=user_id,
                days=days,
                admin_telegram_id=callback.from_user.id
            )
            
            if not expires_at or not vpn_key:
                raise Exception(f"admin_grant_access_atomic returned None: expires_at={expires_at}, vpn_key={bool(vpn_key)}")
        except Exception as e:
            logger.exception(f"CRITICAL: Failed to grant admin access for user {user_id}, days={days}, admin={callback.from_user.id}: {e}")
            text = f"❌ Ошибка выдачи доступа: {str(e)[:100]}"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Ошибка создания ключа", show_alert=True)
            await state.clear()
            return
        else:
            # Успешно
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
            text = f"✅ Доступ выдан на {days} дней\nПользователь уведомлён."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            
            # Уведомляем пользователя
            try:
                user_lang = await database.get_user(user_id)
                language = user_lang.get("language", "ru") if user_lang else "ru"
                
                # Обертываем ключ в HTML тег для копирования
                vpn_key_html = f"<code>{vpn_key}</code>"
                user_text = localization.get_text(
                    language,
                    "admin_grant_user_notification",
                    days=days,
                    vpn_key=vpn_key_html,
                    date=expires_str
                )
                await bot.send_message(user_id, user_text, parse_mode="HTML")
            except Exception as e:
                logging.exception(f"Error sending notification to user {user_id}: {e}")
        
        await state.clear()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_grant_days: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)
        await state.clear()


@router.callback_query(F.data.startswith("admin:grant_minutes:"))
async def callback_admin_grant_minutes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выдачи доступа на N минут"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        parts = callback.data.split(":")
        user_id = int(parts[2])
        minutes = int(parts[3])
        
        # Выдаем доступ на минуты через grant_access
        try:
            expires_at, vpn_key = await database.admin_grant_access_minutes_atomic(
                telegram_id=user_id,
                minutes=minutes,
                admin_telegram_id=callback.from_user.id
            )
            
            if not expires_at or not vpn_key:
                raise Exception(f"admin_grant_access_minutes_atomic returned None: expires_at={expires_at}, vpn_key={bool(vpn_key)}")
        except Exception as e:
            logger.exception(f"CRITICAL: Failed to grant admin access (minutes) for user {user_id}, minutes={minutes}, admin={callback.from_user.id}: {e}")
            text = f"❌ Ошибка выдачи доступа: {str(e)[:100]}"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Ошибка создания ключа", show_alert=True)
            await state.clear()
            return
        else:
            # Успешно
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
            text = f"✅ Доступ выдан на {minutes} минут\nПользователь уведомлён."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            
            # Уведомляем пользователя
            try:
                user_lang = await database.get_user(user_id)
                language = user_lang.get("language", "ru") if user_lang else "ru"
                
                # Используем специальное уведомление для 10 минут
                user_text = localization.get_text(
                    language,
                    "admin_grant_user_notification_10m"
                )
                
                # Добавляем кнопку "Перейти к подключению"
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=localization.get_text(language, "go_to_connection"),
                        callback_data="menu_instruction"
                    )]
                ])
                
                await bot.send_message(user_id, user_text, reply_markup=keyboard)
            except Exception as e:
                logging.exception(f"Error sending notification to user {user_id}: {e}")
        
        await state.clear()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_grant_minutes: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)
        await state.clear()


@router.callback_query(F.data.startswith("admin:grant_1_year:"))
async def callback_admin_grant_1_year(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выдачи доступа на 1 год"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        parts = callback.data.split(":")
        user_id = int(parts[3])
        
        # Выдаем доступ на 1 год (365 дней) через grant_access
        try:
            expires_at, vpn_key = await database.admin_grant_access_atomic(
                telegram_id=user_id,
                days=365,
                admin_telegram_id=callback.from_user.id
            )
            
            if not expires_at or not vpn_key:
                raise Exception(f"admin_grant_access_atomic returned None: expires_at={expires_at}, vpn_key={bool(vpn_key)}")
        except Exception as e:
            logger.exception(f"CRITICAL: Failed to grant admin access (1 year) for user {user_id}, admin={callback.from_user.id}: {e}")
            text = f"❌ Ошибка выдачи доступа: {str(e)[:100]}"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Ошибка создания ключа", show_alert=True)
            await state.clear()
            return
        else:
            # Успешно
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
            text = f"✅ Доступ на 1 год выдан\n\nПользователь: {user_id}\nСрок действия обновлён."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            
            # Логируем действие
            logging.info(f"Admin {callback.from_user.id} granted 1 year access to user {user_id}")
            
            # Уведомляем пользователя
            try:
                user_lang = await database.get_user(user_id)
                language = user_lang.get("language", "ru") if user_lang else "ru"
                
                # Обертываем ключ в HTML тег для копирования
                vpn_key_html = f"<code>{vpn_key}</code>"
                user_text = localization.get_text(
                    language,
                    "admin_grant_user_notification_1_year",
                    vpn_key=vpn_key_html,
                    date=expires_str
                )
                await bot.send_message(user_id, user_text, parse_mode="HTML")
            except Exception as e:
                logging.exception(f"Error sending notification to user {user_id}: {e}")
        
        await state.clear()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_grant_1_year: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)
        await state.clear()


@router.callback_query(F.data.startswith("admin:revoke:"))
async def callback_admin_revoke(callback: CallbackQuery, bot: Bot):
    """Обработчик кнопки 'Лишить доступа'"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        # Лишаем доступа
        revoked = await database.admin_revoke_access_atomic(
            telegram_id=user_id,
            admin_telegram_id=callback.from_user.id
        )
        
        if not revoked:
            # Нет активной подписки
            text = "❌ У пользователя нет активной подписки"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Нет активной подписки", show_alert=True)
        else:
            # Успешно
            text = "✅ Доступ отозван\nПользователь уведомлён."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            
            # Уведомляем пользователя
            try:
                user_lang = await database.get_user(user_id)
                language = user_lang.get("language", "ru") if user_lang else "ru"
                
                user_text = localization.get_text(language, "admin_revoke_user_notification")
                await bot.send_message(user_id, user_text)
            except Exception as e:
                logging.exception(f"Error sending notification to user {user_id}: {e}")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_revoke: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data.startswith("admin:revoke:"))
async def callback_admin_revoke(callback: CallbackQuery, bot: Bot):
    """Обработчик кнопки 'Лишить доступа'"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        # Лишаем доступа
        revoked = await database.admin_revoke_access_atomic(
            telegram_id=user_id,
            admin_telegram_id=callback.from_user.id
        )
        
        if not revoked:
            # Нет активной подписки
            text = "❌ У пользователя нет активной подписки"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Нет активной подписки", show_alert=True)
        else:
            # Успешно
            text = "✅ Доступ отозван\nПользователь уведомлён."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            
            # Уведомляем пользователя
            try:
                user_lang = await database.get_user(user_id)
                language = user_lang.get("language", "ru") if user_lang else "ru"
                
                user_text = localization.get_text(language, "admin_revoke_user_notification")
                await bot.send_message(user_id, user_text)
            except Exception as e:
                logging.exception(f"Error sending notification to user {user_id}: {e}")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_revoke: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


# ==================== ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ ПЕРСОНАЛЬНЫМИ СКИДКАМИ ====================

def get_admin_discount_percent_keyboard(user_id: int):
    """Клавиатура для выбора процента скидки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="10%", callback_data=f"admin:discount_percent:{user_id}:10"),
            InlineKeyboardButton(text="15%", callback_data=f"admin:discount_percent:{user_id}:15"),
        ],
        [
            InlineKeyboardButton(text="25%", callback_data=f"admin:discount_percent:{user_id}:25"),
            InlineKeyboardButton(text="Ввести вручную", callback_data=f"admin:discount_percent_manual:{user_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")],
    ])
    return keyboard


def get_admin_discount_expires_keyboard(user_id: int, discount_percent: int):
    """Клавиатура для выбора срока действия скидки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 дней", callback_data=f"admin:discount_expires:{user_id}:{discount_percent}:7"),
            InlineKeyboardButton(text="30 дней", callback_data=f"admin:discount_expires:{user_id}:{discount_percent}:30"),
        ],
        [
            InlineKeyboardButton(text="Бессрочно", callback_data=f"admin:discount_expires:{user_id}:{discount_percent}:0"),
            InlineKeyboardButton(text="Ввести вручную", callback_data=f"admin:discount_expires_manual:{user_id}:{discount_percent}"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")],
    ])
    return keyboard


@router.callback_query(F.data.startswith("admin:discount_create:"))
async def callback_admin_discount_create(callback: CallbackQuery):
    """Обработчик кнопки 'Назначить скидку'"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        # Проверяем, есть ли уже скидка
        existing_discount = await database.get_user_discount(user_id)
        if existing_discount:
            discount_percent = existing_discount["discount_percent"]
            text = f"❌ У пользователя уже есть персональная скидка {discount_percent}%.\n\nСначала удалите существующую скидку."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Скидка уже существует", show_alert=True)
            return
        
        text = f"🎯 Назначить скидку\n\nВыберите процент скидки:"
        await callback.message.edit_text(text, reply_markup=get_admin_discount_percent_keyboard(user_id))
        await callback.answer()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_discount_create: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data.startswith("admin:discount_percent:"))
async def callback_admin_discount_percent(callback: CallbackQuery):
    """Обработчик выбора процента скидки"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        parts = callback.data.split(":")
        user_id = int(parts[2])
        discount_percent = int(parts[3])
        
        text = f"🎯 Назначить скидку {discount_percent}%\n\nВыберите срок действия скидки:"
        await callback.message.edit_text(text, reply_markup=get_admin_discount_expires_keyboard(user_id, discount_percent))
        await callback.answer()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_discount_percent: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data.startswith("admin:discount_percent_manual:"))
async def callback_admin_discount_percent_manual(callback: CallbackQuery, state: FSMContext):
    """Обработчик для ввода процента скидки вручную"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        await state.update_data(discount_user_id=user_id)
        await state.set_state(AdminDiscountCreate.waiting_for_percent)
        
        text = "🎯 Назначить скидку\n\nВведите процент скидки (число от 1 до 99):"
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_discount_percent_manual: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.message(AdminDiscountCreate.waiting_for_percent)
async def process_admin_discount_percent(message: Message, state: FSMContext):
    """Обработка введённого процента скидки"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        await message.answer("Недостаточно прав доступа")
        await state.clear()
        return
    
    try:
        data = await state.get_data()
        user_id = data.get("discount_user_id")
        
        try:
            discount_percent = int(message.text.strip())
            if discount_percent < 1 or discount_percent > 99:
                await message.answer("Процент скидки должен быть от 1 до 99. Попробуйте снова:")
                return
        except ValueError:
            await message.answer("Введите число от 1 до 99:")
            return
        
        await state.update_data(discount_percent=discount_percent)
        
        text = f"🎯 Назначить скидку {discount_percent}%\n\nВыберите срок действия скидки:"
        await message.answer(text, reply_markup=get_admin_discount_expires_keyboard(user_id, discount_percent))
        await state.set_state(AdminDiscountCreate.waiting_for_expires)
        
    except Exception as e:
        logging.exception(f"Error in process_admin_discount_percent: {e}")
        await message.answer("Ошибка. Проверь логи.")
        await state.clear()


@router.callback_query(F.data.startswith("admin:discount_expires:"))
async def callback_admin_discount_expires(callback: CallbackQuery, bot: Bot):
    """Обработчик выбора срока действия скидки"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        parts = callback.data.split(":")
        user_id = int(parts[2])
        discount_percent = int(parts[3])
        expires_days = int(parts[4])
        
        # Рассчитываем expires_at
        expires_at = None
        if expires_days > 0:
            expires_at = datetime.now() + timedelta(days=expires_days)
        
        # Создаём скидку
        success = await database.create_user_discount(
            telegram_id=user_id,
            discount_percent=discount_percent,
            expires_at=expires_at,
            created_by=callback.from_user.id
        )
        
        if success:
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "бессрочно"
            text = f"✅ Персональная скидка {discount_percent}% назначена\n\nСрок действия: {expires_str}"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Скидка назначена", show_alert=True)
        else:
            text = "❌ Ошибка при создании скидки"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Ошибка", show_alert=True)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_discount_expires: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data.startswith("admin:discount_expires_manual:"))
async def callback_admin_discount_expires_manual(callback: CallbackQuery, state: FSMContext):
    """Обработчик для ввода срока действия скидки вручную"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        parts = callback.data.split(":")
        user_id = int(parts[2])
        discount_percent = int(parts[3])
        
        await state.update_data(discount_user_id=user_id, discount_percent=discount_percent)
        await state.set_state(AdminDiscountCreate.waiting_for_expires)
        
        text = "🎯 Назначить скидку\n\nВведите количество дней действия скидки (или 0 для бессрочной):"
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_discount_expires_manual: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.message(AdminDiscountCreate.waiting_for_expires)
async def process_admin_discount_expires(message: Message, state: FSMContext, bot: Bot):
    """Обработка введённого срока действия скидки"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        await message.answer("Недостаточно прав доступа")
        await state.clear()
        return
    
    try:
        data = await state.get_data()
        user_id = data.get("discount_user_id")
        discount_percent = data.get("discount_percent")
        
        try:
            expires_days = int(message.text.strip())
            if expires_days < 0:
                await message.answer("Количество дней должно быть неотрицательным. Попробуйте снова:")
                return
        except ValueError:
            await message.answer("Введите число (количество дней или 0 для бессрочной):")
            return
        
        # Рассчитываем expires_at
        expires_at = None
        if expires_days > 0:
            expires_at = datetime.now() + timedelta(days=expires_days)
        
        # Создаём скидку
        success = await database.create_user_discount(
            telegram_id=user_id,
            discount_percent=discount_percent,
            expires_at=expires_at,
            created_by=message.from_user.id
        )
        
        if success:
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "бессрочно"
            text = f"✅ Персональная скидка {discount_percent}% назначена\n\nСрок действия: {expires_str}"
            await message.answer(text, reply_markup=get_admin_back_keyboard())
        else:
            text = "❌ Ошибка при создании скидки"
            await message.answer(text, reply_markup=get_admin_back_keyboard())
        
        await state.clear()
        
    except Exception as e:
        logging.exception(f"Error in process_admin_discount_expires: {e}")
        await message.answer("Ошибка. Проверь логи.")
        await state.clear()


@router.callback_query(F.data.startswith("admin:discount_delete:"))
async def callback_admin_discount_delete(callback: CallbackQuery):
    """Обработчик кнопки 'Удалить скидку'"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        # Удаляем скидку
        success = await database.delete_user_discount(
            telegram_id=user_id,
            deleted_by=callback.from_user.id
        )
        
        if success:
            text = "✅ Персональная скидка удалена"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Скидка удалена", show_alert=True)
        else:
            text = "❌ Скидка не найдена или уже удалена"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Скидка не найдена", show_alert=True)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_discount_delete: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


# ==================== ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ VIP-СТАТУСОМ ====================

async def _show_admin_user_card(message_or_callback, user_id: int):
    """Вспомогательная функция для отображения карточки пользователя администратору"""
    # Получаем данные пользователя
    user = await database.find_user_by_id_or_username(telegram_id=user_id)
    if not user:
        if hasattr(message_or_callback, 'edit_text'):
            await message_or_callback.edit_text("❌ Пользователь не найден", reply_markup=get_admin_back_keyboard())
        else:
            await message_or_callback.answer("❌ Пользователь не найден")
        return
    
    # Получаем информацию о подписке
    subscription = await database.get_subscription(user["telegram_id"])
    
    # Получаем расширенную статистику
    stats = await database.get_user_extended_stats(user["telegram_id"])
    
    # Формируем карточку пользователя
    text = "👤 Пользователь\n\n"
    text += f"Telegram ID: {user['telegram_id']}\n"
    username_display = user.get('username') or 'не указан'
    text += f"Username: @{username_display}\n"
    
    # Язык
    user_language = user.get('language') or 'ru'
    language_display = localization.LANGUAGE_BUTTONS.get(user_language, user_language)
    text += f"Язык: {language_display}\n"
    
    # Дата регистрации
    created_at = user.get('created_at')
    if created_at:
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        created_str = created_at.strftime("%d.%m.%Y %H:%M")
        text += f"Дата регистрации: {created_str}\n"
    else:
        text += "Дата регистрации: —\n"
    
    text += "\n"
    
    if subscription:
        expires_at = subscription["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
        
        now = datetime.now()
        if expires_at > now:
            text += "Статус подписки: ✅ Активна\n"
        else:
            text += "Статус подписки: ⛔ Истекла\n"
        
        text += f"Срок действия: до {expires_str}\n"
        text += f"VPN-ключ: {subscription['vpn_key']}\n"
    else:
        text += "Статус подписки: ❌ Нет подписки\n"
        text += "VPN-ключ: —\n"
        text += "Срок действия: —\n"
    
    # Статистика
    text += f"\nКоличество продлений: {stats['renewals_count']}\n"
    text += f"Количество перевыпусков: {stats['reissues_count']}\n"
    
    # Проверяем наличие персональной скидки
    user_discount = await database.get_user_discount(user["telegram_id"])
    has_discount = user_discount is not None
    
    # Проверяем VIP-статус (явно определяем переменную)
    is_vip = await database.is_vip_user(user["telegram_id"])
    
    if user_discount:
        discount_percent = user_discount["discount_percent"]
        expires_at_discount = user_discount.get("expires_at")
        if expires_at_discount:
            if isinstance(expires_at_discount, str):
                expires_at_discount = datetime.fromisoformat(expires_at_discount.replace('Z', '+00:00'))
            expires_str = expires_at_discount.strftime("%d.%m.%Y %H:%M")
            text += f"\n🎯 Персональная скидка: {discount_percent}% (до {expires_str})\n"
        else:
            text += f"\n🎯 Персональная скидка: {discount_percent}% (бессрочно)\n"
    
    # Добавляем информацию о VIP-статусе
    if is_vip:
        text += f"\n👑 VIP-статус: активен\n"
    
    # Определяем статус подписки для клавиатуры
    if subscription:
        expires_at = subscription["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        now = datetime.now()
        has_active = expires_at > now
    else:
        has_active = False
    
    # Отображаем карточку
    keyboard = get_admin_user_keyboard(has_active_subscription=has_active, user_id=user["telegram_id"], has_discount=has_discount, is_vip=is_vip)
    
    if hasattr(message_or_callback, 'edit_text'):
        await message_or_callback.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:vip_grant:"))
async def callback_admin_vip_grant(callback: CallbackQuery):
    """Обработчик кнопки 'Выдать VIP'"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        # Проверяем, есть ли уже VIP-статус
        existing_vip = await database.is_vip_user(user_id)
        if existing_vip:
            # Если уже есть VIP, просто обновляем карточку
            await _show_admin_user_card(callback.message, user_id)
            await callback.answer("VIP уже назначен", show_alert=True)
            return
        
        # Назначаем VIP-статус
        success = await database.grant_vip_status(
            telegram_id=user_id,
            granted_by=callback.from_user.id
        )
        
        if success:
            # После успешного назначения VIP обновляем карточку пользователя
            await _show_admin_user_card(callback.message, user_id)
            await callback.answer("✅ VIP-статус выдан", show_alert=True)
        else:
            text = "❌ Ошибка при назначении VIP-статуса"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("Ошибка", show_alert=True)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_vip_grant: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data.startswith("admin:vip_revoke:"))
async def callback_admin_vip_revoke(callback: CallbackQuery):
    """Обработчик кнопки 'Снять VIP'"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[2])
        
        # Отзываем VIP-статус
        success = await database.revoke_vip_status(
            telegram_id=user_id,
            revoked_by=callback.from_user.id
        )
        
        if success:
            # После успешного снятия VIP обновляем карточку пользователя
            await _show_admin_user_card(callback.message, user_id)
            await callback.answer("✅ VIP-статус снят", show_alert=True)
        else:
            text = "❌ VIP-статус не найден или уже снят"
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            await callback.answer("VIP не найден", show_alert=True)
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_vip_revoke: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data.startswith("admin:user_reissue:"))
async def callback_admin_user_reissue(callback: CallbackQuery):
    """Перевыпуск ключа из админ-дашборда"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Получаем user_id из callback_data
        target_user_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат команды", show_alert=True)
        return
    
    try:
        admin_telegram_id = callback.from_user.id
        
        # Атомарно перевыпускаем ключ
        result = await database.reissue_vpn_key_atomic(target_user_id, admin_telegram_id)
        new_vpn_key, old_vpn_key = result
        
        if new_vpn_key is None:
            await callback.answer("Не удалось перевыпустить ключ. Нет активной подписки или ошибка создания ключа.", show_alert=True)
            return
        
        # Обновляем информацию о пользователе
        user = await database.get_user(target_user_id)
        subscription = await database.get_subscription(target_user_id)
        
        text = "👤 Информация о пользователе\n\n"
        text += f"Telegram ID: {target_user_id}\n"
        text += f"Username: @{user.get('username', 'не указан') if user else 'не указан'}\n"
        text += "\n"
        
        if subscription:
            expires_at = subscription["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
            
            text += "Статус подписки: ✅ Активна\n"
            text += f"Срок действия: до {expires_str}\n"
            text += f"VPN-ключ: <code>{new_vpn_key}</code>\n"
            text += f"\n✅ Ключ перевыпущен!\nСтарый ключ: {old_vpn_key[:20]}..."
            
            # Проверяем VIP-статус и скидку
            is_vip = await database.is_vip_user(target_user_id)
            has_discount = await database.get_user_discount(target_user_id) is not None
            
            await callback.message.edit_text(text, reply_markup=get_admin_user_keyboard(has_active_subscription=True, user_id=target_user_id, has_discount=has_discount, is_vip=is_vip), parse_mode="HTML")
        
        await callback.answer("Ключ успешно перевыпущен")
        
        # Уведомляем пользователя
        try:
            user_text = get_reissue_notification_text(new_vpn_key)
            keyboard = get_reissue_notification_keyboard()
            await callback.bot.send_message(target_user_id, user_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Error sending reissue notification to user {target_user_id}: {e}")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_user_reissue: {e}")
        await callback.answer("Ошибка при перевыпуске ключа", show_alert=True)


@router.callback_query(F.data == "admin:system")
async def callback_admin_system(callback: CallbackQuery):
    """Раздел Система"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        # Проверяем статус БД
        db_status = "ERROR"
        db_connections = "—"
        
        try:
            pool = await database.get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "ONLINE"
                # asyncpg не предоставляет прямых методов для получения количества соединений
                # Поэтому просто указываем, что пул работает
                db_connections = "Активен"
        except Exception as e:
            logging.error(f"Database health check failed: {e}")
            db_status = "ERROR"
            db_connections = "—"
        
        # Вычисляем uptime
        uptime_seconds = int(time.time() - _bot_start_time)
        uptime_days = uptime_seconds // 86400
        uptime_hours = (uptime_seconds % 86400) // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60
        
        uptime_str = f"{uptime_days}д {uptime_hours}ч {uptime_minutes}м"
        
        text = "🚨 Система\n\n"
        text += f"Статус БД: {db_status}\n"
        text += f"Активных соединений: {db_connections}\n"
        text += f"Время работы бота: {uptime_str}"
        
        await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
        await callback.answer()
        
        # Логируем просмотр системной информации
        await database._log_audit_event_atomic_standalone("admin_view_system", callback.from_user.id, None, f"Admin viewed system info: DB={db_status}")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_system: {e}")
        await callback.answer("Ошибка при получении системной информации", show_alert=True)


@router.callback_query(F.data == "admin:export")
async def callback_admin_export(callback: CallbackQuery):
    """Раздел Экспорт данных"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    text = "📤 Экспорт данных\n\nВыберите тип данных для экспорта:"
    await callback.message.edit_text(text, reply_markup=get_admin_export_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:export:"))
async def callback_admin_export_data(callback: CallbackQuery):
    """Обработка экспорта данных"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        export_type = callback.data.split(":")[2]  # users или subscriptions
        
        # Получаем данные из БД
        if export_type == "users":
            data = await database.get_all_users_for_export()
            filename = "users_export.csv"
            headers = ["ID", "Telegram ID", "Username", "Language", "Created At"]
        elif export_type == "subscriptions":
            data = await database.get_active_subscriptions_for_export()
            filename = "active_subscriptions_export.csv"
            headers = ["ID", "Telegram ID", "VPN Key", "Expires At", "Reminder Sent"]
        else:
            await callback.message.answer("Неверный тип экспорта")
            return
        
        if not data:
            await callback.message.answer("Нет данных для экспорта")
            return
        
        # Создаём временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='') as tmp_file:
            csv_file_path = tmp_file.name
            
            # Записываем CSV
            writer = csv.writer(tmp_file)
            writer.writerow(headers)
            
            # Маппинг заголовков на ключи в данных
            if export_type == "users":
                key_mapping = {
                    "ID": "id",
                    "Telegram ID": "telegram_id",
                    "Username": "username",
                    "Language": "language",
                    "Created At": "created_at"
                }
            else:  # subscriptions
                key_mapping = {
                    "ID": "id",
                    "Telegram ID": "telegram_id",
                    "VPN Key": "vpn_key",
                    "Expires At": "expires_at",
                    "Reminder Sent": "reminder_sent"
                }
            
            for row in data:
                csv_row = []
                for header in headers:
                    key = key_mapping[header]
                    value = row.get(key)
                    
                    if key == "created_at" or key == "expires_at":
                        # Форматируем дату
                        if value:
                            if isinstance(value, datetime):
                                csv_row.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                            elif isinstance(value, str):
                                csv_row.append(value)
                            else:
                                csv_row.append(str(value))
                        else:
                            csv_row.append("")
                    elif key == "reminder_sent":
                        # Преобразуем boolean в строку
                        csv_row.append("Да" if value else "Нет")
                    else:
                        csv_row.append(str(value) if value is not None else "")
                writer.writerow(csv_row)
        
        # Отправляем файл
        try:
            file_to_send = FSInputFile(csv_file_path, filename=filename)
            await callback.bot.send_document(
                config.ADMIN_TELEGRAM_ID,
                file_to_send,
                caption=f"📤 Экспорт: {export_type}"
            )
            await callback.message.answer("✅ Файл отправлен")
            
            # Логируем экспорт
            await database._log_audit_event_atomic_standalone(
                "admin_export_data",
                callback.from_user.id,
                None,
                f"Exported {export_type}: {len(data)} records"
            )
        finally:
            # Удаляем временный файл
            try:
                os.unlink(csv_file_path)
            except Exception as e:
                logging.error(f"Error deleting temp file {csv_file_path}: {e}")
        
    except Exception as e:
        logging.exception(f"Error in callback_admin_export_data: {e}")
        await callback.message.answer("Ошибка при экспорте данных. Проверь логи.")


@router.callback_query(F.data == "admin:incident")
async def callback_admin_incident(callback: CallbackQuery):
    """Раздел управления инцидентом"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    incident = await database.get_incident_settings()
    is_active = incident["is_active"]
    incident_text = incident.get("incident_text") or "Текст не указан"
    
    status_text = "🟢 Режим инцидента активен" if is_active else "⚪ Режим инцидента выключен"
    text = f"🚨 Инцидент\n\n{status_text}\n\nТекст инцидента:\n{incident_text}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Включить" if not is_active else "❌ Выключить",
            callback_data="admin:incident:toggle"
        )],
        [InlineKeyboardButton(text="📝 Изменить текст", callback_data="admin:incident:edit")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")],
    ])
    
    await safe_edit_text(callback.message, text, reply_markup=keyboard)
    
    # Логируем действие
    await database._log_audit_event_atomic_standalone("admin_view_incident", callback.from_user.id, None, f"Viewed incident settings (active: {is_active})")


@router.callback_query(F.data == "admin:incident:toggle")
async def callback_admin_incident_toggle(callback: CallbackQuery):
    """Переключение режима инцидента"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    incident = await database.get_incident_settings()
    new_state = not incident["is_active"]
    
    await database.set_incident_mode(new_state)
    
    action = "включен" if new_state else "выключен"
    await callback.answer(f"Режим инцидента {action}", show_alert=True)
    
    # Логируем действие
    await database._log_audit_event_atomic_standalone(
        "incident_mode_toggled",
        callback.from_user.id,
        None,
        f"Incident mode {'enabled' if new_state else 'disabled'}"
    )
    
    # Возвращаемся к экрану инцидента
    await callback_admin_incident(callback)


@router.callback_query(F.data == "admin:incident:edit")
async def callback_admin_incident_edit(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования текста инцидента"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    text = "Введите текст инцидента (или отправьте /cancel для отмены):"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin:incident")],
    ])
    
    await safe_edit_text(callback.message, text, reply_markup=keyboard)
    await state.set_state(IncidentEdit.waiting_for_text)


@router.message(IncidentEdit.waiting_for_text)
async def process_incident_text(message: Message, state: FSMContext):
    """Обработка текста инцидента"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        return
    
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Отменено")
        return
    
    incident_text = message.text
    
    # Включаем режим инцидента и сохраняем текст
    await database.set_incident_mode(True, incident_text)
    
    await message.answer(f"✅ Текст инцидента сохранён. Режим инцидента включён.")
    
    # Логируем действие
    await database._log_audit_event_atomic_standalone(
        "incident_text_updated",
        message.from_user.id,
        None,
        f"Incident text updated: {incident_text[:50]}..."
    )
    
    await state.clear()


@router.callback_query(F.data == "admin:broadcast")
async def callback_admin_broadcast(callback: CallbackQuery):
    """Раздел уведомлений"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    text = "📣 Уведомления\n\nВыберите действие:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать уведомление", callback_data="broadcast:create")],
        [InlineKeyboardButton(text="📊 A/B статистика", callback_data="broadcast:ab_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")],
    ])
    await safe_edit_text(callback.message, text, reply_markup=keyboard)
    await callback.answer()
    
    # Логируем действие
    await database._log_audit_event_atomic_standalone("admin_broadcast_view", callback.from_user.id, None, "Admin viewed broadcast section")


@router.callback_query(F.data == "broadcast:create")
async def callback_broadcast_create(callback: CallbackQuery, state: FSMContext):
    """Начать создание уведомления"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(BroadcastCreate.waiting_for_title)
    await callback.message.answer("Введите заголовок уведомления:")


@router.message(BroadcastCreate.waiting_for_title)
async def process_broadcast_title(message: Message, state: FSMContext):
    """Обработка заголовка уведомления"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        return
    
    await state.update_data(title=message.text)
    await state.set_state(BroadcastCreate.waiting_for_test_type)
    await message.answer("Выберите тип уведомления:", reply_markup=get_broadcast_test_type_keyboard())


@router.callback_query(F.data.startswith("broadcast_test_type:"))
async def callback_broadcast_test_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа тестирования"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    test_type = callback.data.split(":")[1]
    
    await state.update_data(is_ab_test=(test_type == "ab"))
    
    if test_type == "ab":
        await state.set_state(BroadcastCreate.waiting_for_message_a)
        await callback.message.edit_text("Введите текст варианта A:")
    else:
        await state.set_state(BroadcastCreate.waiting_for_message)
        await callback.message.edit_text("Введите текст уведомления:")


@router.message(BroadcastCreate.waiting_for_message_a)
async def process_broadcast_message_a(message: Message, state: FSMContext):
    """Обработка текста варианта A"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        return
    
    await state.update_data(message_a=message.text)
    await state.set_state(BroadcastCreate.waiting_for_message_b)
    await message.answer("Введите текст варианта B:")


@router.message(BroadcastCreate.waiting_for_message_b)
async def process_broadcast_message_b(message: Message, state: FSMContext):
    """Обработка текста варианта B"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        return
    
    await state.update_data(message_b=message.text)
    await state.set_state(BroadcastCreate.waiting_for_type)
    await message.answer("Выберите тип уведомления:", reply_markup=get_broadcast_type_keyboard())


@router.message(BroadcastCreate.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Обработка текста уведомления"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        return
    
    await state.update_data(message=message.text)
    await state.set_state(BroadcastCreate.waiting_for_type)
    await message.answer("Выберите тип уведомления:", reply_markup=get_broadcast_type_keyboard())


@router.callback_query(F.data.startswith("broadcast_type:"))
async def callback_broadcast_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа уведомления"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    broadcast_type = callback.data.split(":")[1]
    
    data = await state.get_data()
    title = data.get("title")
    message_text = data.get("message")
    
    # Формируем предпросмотр
    type_emoji = {
        "info": "ℹ️",
        "maintenance": "🔧",
        "security": "🔒",
        "promo": "🎯"
    }
    type_name = {
        "info": "Информация",
        "maintenance": "Технические работы",
        "security": "Безопасность",
        "promo": "Промо"
    }
    
    await state.update_data(type=broadcast_type)
    await state.set_state(BroadcastCreate.waiting_for_segment)
    
    await callback.message.edit_text(
        "Выберите сегмент получателей:",
        reply_markup=get_broadcast_segment_keyboard()
    )


@router.callback_query(F.data.startswith("broadcast_segment:"))
async def callback_broadcast_segment(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора сегмента получателей"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    segment = callback.data.split(":")[1]
    
    data = await state.get_data()
    title = data.get("title")
    message_text = data.get("message")
    broadcast_type = data.get("type")
    
    # Формируем предпросмотр
    type_emoji = {
        "info": "ℹ️",
        "maintenance": "🔧",
        "security": "🔒",
        "promo": "🎯"
    }
    type_name = {
        "info": "Информация",
        "maintenance": "Технические работы",
        "security": "Безопасность",
        "promo": "Промо"
    }
    segment_name = {
        "all_users": "Все пользователи",
        "active_subscriptions": "Только активные подписки"
    }
    
    data_for_preview = await state.get_data()
    is_ab_test = data_for_preview.get("is_ab_test", False)
    
    if is_ab_test:
        message_a = data_for_preview.get("message_a", "")
        message_b = data_for_preview.get("message_b", "")
        preview_text = (
            f"{type_emoji.get(broadcast_type, '📢')} {title}\n\n"
            f"🔬 A/B ТЕСТ\n\n"
            f"Вариант A:\n{message_a}\n\n"
            f"Вариант B:\n{message_b}\n\n"
            f"Тип: {type_name.get(broadcast_type, broadcast_type)}\n"
            f"Сегмент: {segment_name.get(segment, segment)}"
        )
    else:
        message_text = data_for_preview.get("message", "")
        preview_text = (
            f"{type_emoji.get(broadcast_type, '📢')} {title}\n\n"
            f"{message_text}\n\n"
            f"Тип: {type_name.get(broadcast_type, broadcast_type)}\n"
            f"Сегмент: {segment_name.get(segment, segment)}"
        )
    
    await state.update_data(segment=segment)
    await state.set_state(BroadcastCreate.waiting_for_confirm)
    
    await callback.message.edit_text(
        f"📋 Предпросмотр уведомления:\n\n{preview_text}\n\nПодтвердите отправку:",
        reply_markup=get_broadcast_confirm_keyboard()
    )


@router.callback_query(F.data == "broadcast:confirm_send")
async def callback_broadcast_confirm_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение и отправка уведомления"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    data = await state.get_data()
    title = data.get("title")
    message_text = data.get("message")
    message_a = data.get("message_a")
    message_b = data.get("message_b")
    is_ab_test = data.get("is_ab_test", False)
    broadcast_type = data.get("type")
    segment = data.get("segment")
    
    # Проверка данных
    if not all([title, broadcast_type, segment]):
        await callback.message.answer("Ошибка: не все данные заполнены. Начните заново.")
        await state.clear()
        return
    
    if is_ab_test:
        if not all([message_a, message_b]):
            await callback.message.answer("Ошибка: не заполнены тексты вариантов A и B. Начните заново.")
            await state.clear()
            return
    else:
        if not message_text:
            await callback.message.answer("Ошибка: не заполнен текст уведомления. Начните заново.")
            await state.clear()
            return
    
    try:
        # Создаем уведомление в БД
        broadcast_id = await database.create_broadcast(
            title, message_text, broadcast_type, segment, callback.from_user.id,
            is_ab_test=is_ab_test, message_a=message_a, message_b=message_b
        )
        
        # Формируем сообщения для отправки
        type_emoji = {
            "info": "ℹ️",
            "maintenance": "🔧",
            "security": "🔒",
            "promo": "🎯"
        }
        emoji = type_emoji.get(broadcast_type, "📢")
        
        if is_ab_test:
            final_message_a = f"{emoji} {title}\n\n{message_a}"
            final_message_b = f"{emoji} {title}\n\n{message_b}"
        else:
            final_message = f"{emoji} {title}\n\n{message_text}"
        
        # Получаем список пользователей по сегменту
        user_ids = await database.get_users_by_segment(segment)
        total_users = len(user_ids)
        
        await callback.message.edit_text(
            f"📤 Отправка уведомления...\n\nПользователей: {total_users}\nОжидайте завершения.",
            reply_markup=None
        )
        
        # Отправляем уведомления с задержкой
        sent_count = 0
        failed_count = 0
        
        for user_id in user_ids:
            try:
                if is_ab_test:
                    # Случайно выбираем вариант A или B (50/50)
                    variant = "A" if random.random() < 0.5 else "B"
                    message_to_send = final_message_a if variant == "A" else final_message_b
                    await bot.send_message(user_id, message_to_send)
                    await database.log_broadcast_send(broadcast_id, user_id, "sent", variant)
                else:
                    await bot.send_message(user_id, final_message)
                    await database.log_broadcast_send(broadcast_id, user_id, "sent")
                
                sent_count += 1
                
                # Задержка между отправками (0.3-0.5 сек)
                await asyncio.sleep(0.4)
                
            except Exception as e:
                logging.error(f"Error sending broadcast to user {user_id}: {e}")
                variant = None
                if is_ab_test:
                    # Для неудачных отправок тоже логируем вариант, если можем определить
                    variant = "A" if random.random() < 0.5 else "B"
                await database.log_broadcast_send(broadcast_id, user_id, "failed", variant)
                failed_count += 1
        
        # Логируем действие
        await database._log_audit_event_atomic_standalone(
            "broadcast_sent",
            callback.from_user.id,
            None,
            f"Broadcast ID: {broadcast_id}, Segment: {segment}, Sent: {sent_count}, Failed: {failed_count}"
        )
        
        # Показываем результат
        result_text = (
            f"✅ Уведомление отправлено\n\n"
            f"📊 Статистика:\n"
            f"✅ Отправлено: {sent_count}\n"
            f"❌ Ошибок: {failed_count}\n"
            f"📝 ID уведомления: {broadcast_id}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:broadcast")],
        ])
        
        await callback.message.edit_text(result_text, reply_markup=keyboard)
        
    except Exception as e:
        logging.exception(f"Error in broadcast send: {e}")
        await callback.message.answer(f"Ошибка при отправке уведомления: {e}")
    
    finally:
        await state.clear()


@router.callback_query(F.data == "broadcast:ab_stats")
async def callback_broadcast_ab_stats(callback: CallbackQuery):
    """Список A/B тестов"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        ab_tests = await database.get_ab_test_broadcasts()
        
        if not ab_tests:
            text = "📊 A/B статистика\n\nA/B тестов не найдено."
            await safe_edit_text(callback.message, text, reply_markup=get_admin_back_keyboard())
            return
        
        text = "📊 A/B статистика\n\nВыберите уведомление для просмотра статистики:"
        keyboard = get_ab_test_list_keyboard(ab_tests)
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        # Логируем действие
        await database._log_audit_event_atomic_standalone("admin_view_ab_stats_list", callback.from_user.id, None, f"Viewed {len(ab_tests)} A/B tests")
    
    except Exception as e:
        logging.exception(f"Error in callback_broadcast_ab_stats: {e}")
        await callback.message.answer("Ошибка при получении списка A/B тестов. Проверь логи.")


@router.callback_query(F.data.startswith("broadcast:ab_stat:"))
async def callback_broadcast_ab_stat_detail(callback: CallbackQuery):
    """Статистика конкретного A/B теста"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        broadcast_id = int(callback.data.split(":")[2])
        
        # Получаем информацию об уведомлении
        broadcast = await database.get_broadcast(broadcast_id)
        if not broadcast:
            await callback.message.answer("Уведомление не найдено.")
            return
        
        # Получаем статистику
        stats = await database.get_ab_test_stats(broadcast_id)
        
        if not stats:
            text = f"📊 A/B статистика\n\nУведомление: #{broadcast_id}\n\nНедостаточно данных для анализа."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="broadcast:ab_stats")],
            ])
            await safe_edit_text(callback.message, text, reply_markup=keyboard)
            return
        
        # Формируем текст статистики
        total_sent = stats["total_sent"]
        variant_a_sent = stats["variant_a_sent"]
        variant_b_sent = stats["variant_b_sent"]
        
        # Проценты
        if total_sent > 0:
            percent_a = round((variant_a_sent / total_sent) * 100)
            percent_b = round((variant_b_sent / total_sent) * 100)
        else:
            percent_a = 0
            percent_b = 0
        
        text = (
            f"📊 A/B статистика\n\n"
            f"Уведомление: #{broadcast_id}\n"
            f"Заголовок: {broadcast.get('title', '—')}\n\n"
            f"Вариант A:\n"
            f"— Отправлено: {variant_a_sent} ({percent_a}%)\n\n"
            f"Вариант B:\n"
            f"— Отправлено: {variant_b_sent} ({percent_b}%)\n\n"
            f"Всего отправлено: {total_sent}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="broadcast:ab_stats")],
        ])
        
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        # Логируем действие
        await database._log_audit_event_atomic_standalone("admin_view_ab_stat_detail", callback.from_user.id, None, f"Viewed A/B stats for broadcast {broadcast_id}")
    
    except (ValueError, IndexError) as e:
        logging.error(f"Error parsing broadcast ID: {e}")
        await callback.message.answer("Ошибка: неверный ID уведомления.")
    except Exception as e:
        logging.exception(f"Error in callback_broadcast_ab_stat_detail: {e}")
        await callback.message.answer("Ошибка при получении статистики A/B теста. Проверь логи.")


@router.message(Command("admin_audit"))
async def cmd_admin_audit(message: Message):
    """Показать последние записи audit_log (только для админа)"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        logging.warning(f"Unauthorized admin_audit attempt by user {message.from_user.id}")
        await message.answer("Недостаточно прав")
        return
    
    try:
        # Получаем последние 10 записей из audit_log
        audit_logs = await database.get_last_audit_logs(limit=10)
        
        if not audit_logs:
            await message.answer("Аудит пуст. Действий не зафиксировано.")
            return
        
        # Формируем сообщение
        lines = ["📜 Audit Log", ""]
        
        for log in audit_logs:
            # Форматируем дату и время
            created_at = log["created_at"]
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            elif isinstance(created_at, datetime):
                pass
            else:
                created_at = datetime.now()
            
            created_str = created_at.strftime("%Y-%m-%d %H:%M")
            
            lines.append(f"🕒 {created_str}")
            lines.append(f"Действие: {log['action']}")
            lines.append(f"Админ: {log['telegram_id']}")
            
            if log['target_user']:
                lines.append(f"Пользователь: {log['target_user']}")
            else:
                lines.append("Пользователь: —")
            
            if log['details']:
                lines.append(f"Детали: {log['details']}")
            else:
                lines.append("Детали: —")
            
            lines.append("")
            lines.append("⸻")
            lines.append("")
        
        # Убираем последний разделитель
        if lines[-1] == "" and lines[-2] == "⸻":
            lines = lines[:-2]
        
        text = "\n".join(lines)
        
        # Проверяем лимит Telegram (4096 символов на сообщение)
        if len(text) > 4000:
            # Если текст слишком длинный, обрезаем до первых записей
            # Попробуем уменьшить количество записей
            audit_logs = await database.get_last_audit_logs(limit=5)
            lines = ["📜 Audit Log", ""]
            
            for log in audit_logs:
                created_at = log["created_at"]
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                elif isinstance(created_at, datetime):
                    pass
                else:
                    created_at = datetime.now()
                
                created_str = created_at.strftime("%Y-%m-%d %H:%M")
                
                lines.append(f"🕒 {created_str}")
                lines.append(f"Действие: {log['action']}")
                lines.append(f"Админ: {log['telegram_id']}")
                
                if log['target_user']:
                    lines.append(f"Пользователь: {log['target_user']}")
                else:
                    lines.append("Пользователь: —")
                
                if log['details']:
                    # Обрезаем детали если они слишком длинные
                    details = log['details']
                    if len(details) > 200:
                        details = details[:200] + "..."
                    lines.append(f"Детали: {details}")
                else:
                    lines.append("Детали: —")
                
                lines.append("")
                lines.append("⸻")
                lines.append("")
            
            if lines[-1] == "" and lines[-2] == "⸻":
                lines = lines[:-2]
            
            text = "\n".join(lines)
        
        await message.answer(text)
        logging.info(f"Admin audit log viewed by admin {message.from_user.id}")
        
    except Exception as e:
        logging.exception(f"Error in cmd_admin_audit: {e}")
        await message.answer("Ошибка при получении audit log. Проверь логи.")


@router.message(Command("reissue_key"))
async def cmd_reissue_key(message: Message):
    """Перевыпустить VPN-ключ для пользователя (только для админа)"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        logging.warning(f"Unauthorized reissue_key attempt by user {message.from_user.id}")
        await message.answer("Нет доступа")
        return
    
    try:
        # Парсим команду: /reissue_key <telegram_id>
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("Использование: /reissue_key <telegram_id>")
            return
        
        try:
            target_telegram_id = int(parts[1])
        except ValueError:
            await message.answer("Неверный формат telegram_id. Используйте число.")
            return
        
        admin_telegram_id = message.from_user.id
        
        # Атомарно перевыпускаем ключ
        result = await database.reissue_vpn_key_atomic(target_telegram_id, admin_telegram_id)
        new_vpn_key, old_vpn_key = result
        
        if new_vpn_key is None:
            await message.answer(f"❌ Не удалось перевыпустить ключ для пользователя {target_telegram_id}.\nВозможные причины:\n- Нет активной подписки\n- Ошибка создания VPN-ключа")
            return
        
        # Уведомляем пользователя
        try:
            user_text = get_reissue_notification_text(new_vpn_key)
            keyboard = get_reissue_notification_keyboard()
            await message.bot.send_message(target_telegram_id, user_text, reply_markup=keyboard, parse_mode="HTML")
            logging.info(f"Reissue notification sent to user {target_telegram_id}")
        except Exception as e:
            logging.error(f"Error sending reissue notification to user {target_telegram_id}: {e}")
            await message.answer(f"✅ Ключ перевыпущен, но не удалось отправить уведомление пользователю: {e}")
            return
        
        await message.answer(
            f"✅ VPN-ключ успешно перевыпущен для пользователя {target_telegram_id}\n\n"
            f"Старый ключ: <code>{old_vpn_key[:20]}...</code>\n"
            f"Новый ключ: <code>{new_vpn_key}</code>",
            parse_mode="HTML"
        )
        logging.info(f"VPN key reissued for user {target_telegram_id} by admin {admin_telegram_id}")
        
    except Exception as e:
        logging.exception(f"Error in cmd_reissue_key: {e}")
        await message.answer("Ошибка при перевыпуске ключа. Проверь логи.")


@router.callback_query(F.data.startswith("reject_payment:"))
async def reject_payment(callback: CallbackQuery):
    """Админ отклонил платеж"""
    await callback.answer()  # ОБЯЗАТЕЛЬНО
    
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        logging.warning(f"Unauthorized reject attempt by user {callback.from_user.id}")
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        payment_id = int(callback.data.split(":")[1])
        
        logging.info(f"REJECT pressed by admin {callback.from_user.id}, payment_id={payment_id}")
        
        # Получить платеж из БД
        payment = await database.get_payment(payment_id)
        
        if not payment:
            logging.warning(f"Payment {payment_id} not found for reject")
            await callback.answer("Платеж не найден", show_alert=True)
            return
        
        if payment["status"] != "pending":
            logging.warning(
                f"Attempt to reject already processed payment {payment_id}, status={payment['status']}"
            )
            await callback.answer("Платеж уже обработан", show_alert=True)
            # Удаляем кнопки даже если платеж уже обработан
            await safe_edit_reply_markup(callback.message, reply_markup=None)
            return
        
        telegram_id = payment["telegram_id"]
        admin_telegram_id = callback.from_user.id
        
        # Обновляем статус платежа на rejected (аудит записывается внутри функции)
        await database.update_payment_status(payment_id, "rejected", admin_telegram_id)
        logging.info(f"Payment {payment_id} rejected for user {telegram_id}")
        
        # Уведомляем пользователя
        user = await database.get_user(telegram_id)
        language = user.get("language", "ru") if user else "ru"
        
        text = localization.get_text(language, "payment_rejected")
        
        try:
            await callback.bot.send_message(telegram_id, text)
            logging.info(f"Rejection message sent to user {telegram_id} for payment {payment_id}")
        except Exception as e:
            logging.error(f"Error sending rejection message to user {telegram_id}: {e}")
        
        await callback.message.edit_text(f"❌ Платеж {payment_id} отклонен")
        # Удаляем inline-кнопки после обработки
        await safe_edit_reply_markup(callback.message, reply_markup=None)
        
    except Exception as e:
        logging.exception(f"Error in reject_payment callback for payment_id={payment_id if 'payment_id' in locals() else 'unknown'}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.callback_query(F.data == "admin:credit_balance")
async def callback_admin_credit_balance_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса выдачи средств - запрос поиска пользователя"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    text = "💰 Выдать средства\n\nВведите Telegram ID или username пользователя:"
    await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard())
    await state.set_state(AdminCreditBalance.waiting_for_user_search)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:credit_balance:"))
async def callback_admin_credit_balance_user(callback: CallbackQuery, state: FSMContext):
    """Начало процесса выдачи средств для конкретного пользователя"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split(":")[2])
        await state.update_data(target_user_id=user_id)
        
        text = f"💰 Выдать средства\n\nПользователь: {user_id}\n\nВведите сумму в рублях:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"admin:user")]
        ])
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        await state.set_state(AdminCreditBalance.waiting_for_amount)
        await callback.answer()
    except Exception as e:
        logging.exception(f"Error in callback_admin_credit_balance_user: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)


@router.message(AdminCreditBalance.waiting_for_user_search)
async def process_admin_credit_balance_user_search(message: Message, state: FSMContext):
    """Обработка поиска пользователя для выдачи средств"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        await message.answer("Недостаточно прав доступа")
        await state.clear()
        return
    
    try:
        user_input = message.text.strip()
        
        # Определяем, является ли ввод числом (ID) или строкой (username)
        try:
            target_user_id = int(user_input)
            user = await database.find_user_by_id_or_username(telegram_id=target_user_id)
        except ValueError:
            username = user_input.lstrip('@').lower()
            user = await database.find_user_by_id_or_username(username=username)
        
        if not user:
            await message.answer("Пользователь не найден.\nПроверьте Telegram ID или username.")
            await state.clear()
            return
        
        target_user_id = user["telegram_id"]
        await state.update_data(target_user_id=target_user_id)
        
        text = f"💰 Выдать средства\n\nПользователь: {target_user_id}\n\nВведите сумму в рублях:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin:main")]
        ])
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(AdminCreditBalance.waiting_for_amount)
        
    except Exception as e:
        logging.exception(f"Error in process_admin_credit_balance_user_search: {e}")
        await message.answer("Ошибка при поиске пользователя. Проверьте логи.")
        await state.clear()


@router.message(AdminCreditBalance.waiting_for_amount)
async def process_admin_credit_balance_amount(message: Message, state: FSMContext):
    """Обработка ввода суммы для выдачи средств"""
    if message.from_user.id != config.ADMIN_TELEGRAM_ID:
        await message.answer("Недостаточно прав доступа")
        await state.clear()
        return
    
    try:
        amount = float(message.text.strip().replace(",", "."))
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительным числом.\n\nВведите сумму в рублях:")
            return
        
        data = await state.get_data()
        target_user_id = data.get("target_user_id")
        
        if not target_user_id:
            await message.answer("Ошибка: пользователь не найден. Начните заново.")
            await state.clear()
            return
        
        # Сохраняем сумму и показываем подтверждение
        await state.update_data(amount=amount)
        
        user = await database.get_user(target_user_id)
        current_balance = await database.get_user_balance(target_user_id) if user else 0.0
        new_balance = current_balance + amount
        
        text = (
            f"💰 Подтверждение выдачи средств\n\n"
            f"👤 Пользователь: {target_user_id}\n"
            f"💳 Текущий баланс: {current_balance:.2f} ₽\n"
            f"➕ Сумма к выдаче: {amount:.2f} ₽\n"
            f"💵 Новый баланс: {new_balance:.2f} ₽\n\n"
            f"Подтвердите операцию:"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="admin:credit_balance_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin:credit_balance_cancel")
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(AdminCreditBalance.waiting_for_confirmation)
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы.\n\nВведите число (например: 500 или 100.50):")
    except Exception as e:
        logging.exception(f"Error in process_admin_credit_balance_amount: {e}")
        await message.answer("Ошибка при обработке суммы. Проверьте логи.")
        await state.clear()


@router.callback_query(F.data == "admin:credit_balance_confirm")
async def callback_admin_credit_balance_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение выдачи средств"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    try:
        data = await state.get_data()
        target_user_id = data.get("target_user_id")
        amount = data.get("amount")
        
        if not target_user_id or not amount:
            await callback.answer("Ошибка: данные не найдены", show_alert=True)
            await state.clear()
            return
        
        # Начисляем баланс
        success = await database.increase_balance(
            telegram_id=target_user_id,
            amount=amount,
            source="admin",
            description=f"Выдача средств администратором {callback.from_user.id}"
        )
        
        if success:
            # Логируем операцию
            await database._log_audit_event_atomic_standalone(
                "admin_credit_balance",
                callback.from_user.id,
                target_user_id,
                f"Admin credited balance: {amount:.2f} RUB"
            )
            
            # Отправляем уведомление пользователю
            try:
                new_balance = await database.get_user_balance(target_user_id)
                notification_text = f"💰 Администратор начислил вам {amount:.2f} ₽ на баланс.\n\nТекущий баланс: {new_balance:.2f} ₽"
                await bot.send_message(chat_id=target_user_id, text=notification_text)
            except Exception as e:
                logger.warning(f"Failed to send balance credit notification to user {target_user_id}: {e}")
            
            new_balance = await database.get_user_balance(target_user_id)
            text = (
                f"✅ Средства успешно начислены\n\n"
                f"👤 Пользователь: {target_user_id}\n"
                f"➕ Сумма: {amount:.2f} ₽\n"
                f"💵 Новый баланс: {new_balance:.2f} ₽"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:main")]
            ])
            
            await safe_edit_text(callback.message, text, reply_markup=keyboard)
            await state.clear()
            await callback.answer("✅ Средства начислены", show_alert=True)
        else:
            await callback.answer("❌ Ошибка при начислении средств", show_alert=True)
            await state.clear()
            
    except Exception as e:
        logging.exception(f"Error in callback_admin_credit_balance_confirm: {e}")
        await callback.answer("Ошибка. Проверь логи.", show_alert=True)
        await state.clear()


@router.callback_query(F.data == "admin:credit_balance_cancel")
async def callback_admin_credit_balance_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена выдачи средств"""
    if callback.from_user.id != config.ADMIN_TELEGRAM_ID:
        await callback.answer("Недостаточно прав доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "❌ Операция отменена",
        reply_markup=get_admin_back_keyboard()
    )
    await state.clear()
    await callback.answer()





