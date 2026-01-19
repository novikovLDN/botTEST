from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
import logging
from datetime import datetime, timedelta

import database
import localization
import config
from states import TopUpStates
from utils.messages import (
    safe_edit_text, 
    ensure_db_ready_message, 
    ensure_db_ready_callback
)
from keyboards.user import (
    get_main_menu_keyboard,
    get_language_keyboard,
    get_profile_keyboard
)

logger = logging.getLogger(__name__)

router = Router()

async def check_subscription_expiry(telegram_id: int) -> bool:
    """
    Дополнительная защита: проверка и мгновенное отключение истёкшей подписки
    """
    return await database.check_and_disable_expired_subscription(telegram_id)

async def format_text_with_incident(text: str, language: str) -> str:
    """Добавить баннер инцидента к тексту, если режим активен"""
    incident = await database.get_incident_settings()
    if incident["is_active"]:
        banner = localization.get_text(language, "incident_banner")
        incident_text = incident.get("incident_text")
        if incident_text:
            banner += f"\n{incident_text}"
        return f"{banner}\n\n⸻\n\n{text}"
    return text

@router.message(Command("start"))
async def cmd_start(message: Message):
    # SAFE STARTUP GUARD: Проверка готовности БД
    if not database.DB_READY:
        language = "ru"
        text = localization.get_text(language, "home_welcome_text", default=localization.get_text(language, "welcome"))
        text += "\n\n" + localization.get_text(language, "service_unavailable")
        keyboard = await get_main_menu_keyboard(language, message.from_user.id)
        await message.answer(text, reply_markup=keyboard)
        return

    """Обработчик команды /start"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    
    # Создаем пользователя если его нет
    user = await database.get_user(telegram_id)
    if not user:
        await database.create_user(telegram_id, username, "ru")
    else:
        # Обновляем username если изменился
        await database.update_username(telegram_id, username)
        # Убеждаемся, что у пользователя есть referral_code
        if not user.get("referral_code"):
            referral_code = database.generate_referral_code(telegram_id)
            pool = await database.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET referral_code = $1 WHERE telegram_id = $2",
                    referral_code, telegram_id
                )
    
    # Обработка реферальной ссылки
    command_args = message.text.split(" ", 1) if message.text else []
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.startswith("ref_"):
            referral_code = arg[4:]
            referrer = await database.find_user_by_referral_code(referral_code)
            
            if referrer:
                referrer_user_id = referrer["telegram_id"]
                if referrer_user_id != telegram_id:
                    user = await database.get_user(telegram_id)
                    if user and not user.get("referrer_id") and not user.get("referred_by"):
                        # Защита от циклов
                        referrer_user = await database.get_user(referrer_user_id)
                        if referrer_user:
                            referrer_referrer = referrer_user.get("referrer_id") or referrer_user.get("referred_by")
                            if referrer_referrer != telegram_id:
                                await database.register_referral(referrer_user_id, telegram_id)
    
    # Экран выбора языка
    await message.answer(
        "🌍 Выбери язык:",
        reply_markup=get_language_keyboard()
    )

@router.callback_query(F.data.startswith("toggle_auto_renew:"))
async def callback_toggle_auto_renew(callback: CallbackQuery):
    """Включить/выключить автопродление"""
    if not await ensure_db_ready_callback(callback):
        return
    
    telegram_id = callback.from_user.id
    action = callback.data.split(":")[1]
    
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        auto_renew = (action == "on")
        await conn.execute(
            "UPDATE subscriptions SET auto_renew = $1 WHERE telegram_id = $2",
            auto_renew, telegram_id
        )
    
    user = await database.get_user(telegram_id)
    language = user.get("language", "ru") if user else "ru"
    
    if auto_renew:
        text = localization.get_text(language, "auto_renew_enabled", default="✅ Автопродление включено")
    else:
        text = localization.get_text(language, "auto_renew_disabled", default="⏸ Автопродление отключено")
    
    await callback.answer(text, show_alert=True)
    await show_profile(callback, language)

@router.callback_query(F.data == "change_language")
async def callback_change_language(callback: CallbackQuery):
    """Изменить язык"""
    await safe_edit_text(
        callback.message,
        "🌍 Выбери язык:",
        reply_markup=get_language_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("lang_"))
async def callback_language(callback: CallbackQuery):
    """
    Универсальный обработчик выбора языка
    
    Обрабатывает: lang_ru, lang_en, lang_uz, lang_tj
    - Сохраняет язык в БД
    - Обновляет сообщение с главным меню
    - Вызывает callback.answer() для мгновенного отклика
    """
    # ДИАГНОСТИКА: Логируем, что handler вызван
    logger.info(f"✅ callback_language handler MATCHED: callback_data='{callback.data}'")
    
    # Отвечаем сразу для мгновенного отклика UI
    await callback.answer()
    
    if not await ensure_db_ready_callback(callback):
        return
    
    try:
        # Извлекаем язык из callback_data (lang_ru -> ru)
        language = callback.data.split("_")[1]
        telegram_id = callback.from_user.id
        
        # Сохраняем язык в БД
        await database.update_user_language(telegram_id, language)
        
        # Формируем текст и клавиатуру главного меню
        text = localization.get_text(language, "home_welcome_text", default=localization.get_text(language, "welcome"))
        text = await format_text_with_incident(text, language)
        keyboard = await get_main_menu_keyboard(language, telegram_id)
        
        # Обновляем сообщение
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        logger.info(f"Language changed to {language} for user {telegram_id}")
    except Exception as e:
        logger.error(f"Error in callback_language: {e}", exc_info=True)
        # Пытаемся показать ошибку пользователю
        try:
            await callback.answer("Ошибка при изменении языка", show_alert=True)
        except:
            pass

@router.callback_query(F.data == "menu_main")
async def callback_main_menu(callback: CallbackQuery):
    """
    Обработчик главного меню
    
    - Загружает язык пользователя из БД
    - Показывает главное меню с актуальным языком
    - Вызывает callback.answer() для мгновенного отклика
    """
    # ДИАГНОСТИКА: Логируем, что handler вызван
    logger.info(f"✅ callback_main_menu handler MATCHED: callback_data='{callback.data}'")
    
    # Отвечаем сразу для мгновенного отклика UI
    await callback.answer()
    
    try:
        telegram_id = callback.from_user.id
        language = "ru"
        
        # Загружаем язык пользователя из БД
        if database.DB_READY:
            user = await database.get_user(telegram_id)
            language = user.get("language", "ru") if user else "ru"
        
        # Формируем текст и клавиатуру главного меню
        text = localization.get_text(language, "home_welcome_text", default=localization.get_text(language, "welcome"))
        text = await format_text_with_incident(text, language)
        keyboard = await get_main_menu_keyboard(language, callback.from_user.id)
        
        # Обновляем сообщение
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
        logger.debug(f"Main menu shown for user {telegram_id} (language: {language})")
    except Exception as e:
        logger.error(f"Error in callback_main_menu: {e}", exc_info=True)
        # Пытаемся показать ошибку пользователю
        try:
            await callback.answer("Ошибка при открытии меню", show_alert=True)
        except:
            pass

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Обработчик команды /profile"""
    if not await ensure_db_ready_message(message):
        return
    
    telegram_id = message.from_user.id
    user = await database.get_user(telegram_id)
    
    if not user:
        await database.create_user(telegram_id, message.from_user.username, "ru")
        user = await database.get_user(telegram_id)
    
    language = user.get("language", "ru") if user else "ru"
    await show_profile(message, language)

@router.callback_query(F.data == "menu_profile")
async def callback_menu_profile(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Профиль'"""
    if not await ensure_db_ready_callback(callback):
        return
    
    # Очищаем состояние при переходе в профиль
    await state.clear()
    
    telegram_id = callback.from_user.id
    user = await database.get_user(telegram_id)
    language = user.get("language", "ru") if user else "ru"
    
    await show_profile(callback, language)

async def show_profile(message_or_query, language: str):
    """Показать профиль пользователя"""
    telegram_id = None
    send_func = None
    
    try:
        if isinstance(message_or_query, Message):
            telegram_id = message_or_query.from_user.id
            send_func = message_or_query.answer
        else:
            telegram_id = message_or_query.from_user.id
            send_func = message_or_query.message.edit_text
    except AttributeError:
        return
    
    if telegram_id:
        await database.check_and_disable_expired_subscription(telegram_id)
    
    try:
        user = await database.get_user(telegram_id)
        if not user:
            await send_func(localization.get_text(language, "error_profile_load"))
            return
        
        username = user.get("username") or f"ID: {telegram_id}"
        balance_rubles = await database.get_user_balance(telegram_id)
        subscription = await database.get_subscription_any(telegram_id)
        
        text = localization.get_text(language, "profile_welcome", username=username, balance=round(balance_rubles, 2))
        
        has_active = False
        has_any = False
        auto_renew = False
        
        if subscription:
            has_any = True
            expires_at = subscription["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            
            if expires_at > datetime.now():
                has_active = True
                text += "\n" + localization.get_text(language, "profile_subscription_active", date=expires_at.strftime("%d.%m.%Y"))
            else:
                text += "\n" + localization.get_text(language, "profile_subscription_inactive")
            
            auto_renew = subscription.get("auto_renew", False)
            
            if has_active:
                if auto_renew:
                    text += "\n" + localization.get_text(language, "profile_auto_renew_enabled", next_billing_date=expires_at.strftime("%d.%m.%Y"))
                else:
                    text += "\n" + localization.get_text(language, "profile_auto_renew_disabled")
        else:
            text += "\n" + localization.get_text(language, "profile_subscription_inactive")

        if has_any:
            text += "\n\n" + localization.get_text(language, "profile_renewal_hint_new")
        if not has_any:
            text += "\n\n" + localization.get_text(language, "profile_buy_hint")
        
        keyboard = get_profile_keyboard(language, has_any, auto_renew)
        await send_func(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_profile: {e}")
        try:
            if isinstance(message_or_query, CallbackQuery):
                await message_or_query.message.answer("Ошибка загрузки профиля.")
            else:
                await message_or_query.answer("Ошибка загрузки профиля.")
        except:
            pass

@router.callback_query(F.data == "activate_trial")
async def callback_activate_trial(callback: CallbackQuery, state: FSMContext):
    """Активация пробного периода на 3 дня"""
    if not await ensure_db_ready_callback(callback):
        return
    
    telegram_id = callback.from_user.id
    user = await database.get_user(telegram_id)
    language = user.get("language", "ru") if user else "ru"
    
    is_eligible = await database.is_eligible_for_trial(telegram_id)
    if not is_eligible:
        error_text = localization.get_text(
            language,
            "trial_not_available",
            default="❌ Пробный период недоступен. Вы уже использовали его ранее или имеете активную подписку."
        )
        await callback.answer(error_text, show_alert=True)
        logger.warning(f"Trial activation attempted by ineligible user: {telegram_id}")
        return
    
    await callback.answer()
    
    try:
        duration = timedelta(days=3)
        now = datetime.now()
        trial_expires_at = now + duration
        
        success = await database.mark_trial_used(telegram_id, trial_expires_at)
        if not success:
            raise Exception("Failed to mark trial as used")
        
        result = await database.grant_access(
            telegram_id=telegram_id,
            duration=duration,
            source="trial",
            admin_telegram_id=None
        )
        
        uuid = result.get("uuid")
        vpn_key = result.get("vless_url")
        subscription_end = result.get("subscription_end")
        
        if not uuid or not vpn_key:
            raise Exception("Failed to create VPN access for trial")
        
        logger.info(
            f"trial_activated: user={telegram_id}, trial_used_at={now.isoformat()}, "
            f"trial_expires_at={trial_expires_at.isoformat()}, subscription_expires_at={subscription_end.isoformat()}, "
            f"uuid={uuid[:8]}..."
        )
        
        success_text = localization.get_text(
            language,
            "trial_activated_text",
            default=(
                "🔒 <b>Пробный доступ активирован</b>\n\n"
                "Вы под защитой на 3 дня.\n\n"
                "🔑 <b>Ваш ключ подключения:</b>\n"
                "<code>{vpn_key}</code>\n\n"
                "Используйте его в приложении VPN.\n\n"
                "⏰ <b>Срок действия:</b> до {expires_date}"
            )
        ).format(
            vpn_key=vpn_key,
            expires_date=subscription_end.strftime("%d.%m.%Y %H:%M")
        )
        
        await callback.message.answer(success_text, parse_mode="HTML")
        
        try:
            await callback.message.answer(f"<code>{vpn_key}</code>", parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to send VPN key with HTML tags: {e}. Sending as plain text.")
            await callback.message.answer(f"🔑 {vpn_key}")
        
        text = localization.get_text(language, "home_welcome_text", default=localization.get_text(language, "welcome"))
        text = await format_text_with_incident(text, language)
        keyboard = await get_main_menu_keyboard(language, telegram_id)
        await safe_edit_text(callback.message, text, reply_markup=keyboard)
        
    except Exception as e:
        logger.exception(f"Error activating trial for user {telegram_id}: {e}")
        error_text = localization.get_text(
            language,
            "trial_activation_error",
            default="❌ Ошибка активации пробного периода. Попробуйте позже или обратитесь в поддержку."
        )
        await callback.message.answer(error_text)

@router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """Возврат в главное меню с экрана выдачи ключа"""
    telegram_id = callback.from_user.id
    user = await database.get_user(telegram_id)
    language = user.get("language", "ru") if user else "ru"
    
    text = localization.get_text(language, "home_welcome_text", default=localization.get_text(language, "welcome"))
    text = await format_text_with_incident(text, language)
    keyboard = await get_main_menu_keyboard(language, telegram_id)
    await safe_edit_text(callback.message, text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "subscription_history")
async def callback_subscription_history(callback: CallbackQuery):
    """История подписок"""
    await callback.answer()
    
    telegram_id = callback.from_user.id
    user = await database.get_user(telegram_id)
    language = user.get("language", "ru") if user else "ru"
    
    history = await database.get_subscription_history(telegram_id, limit=5)
    
    if not history:
        await callback.message.answer(localization.get_text(language, "no_subscription_history", default="История подписок пуста."))
        return

    text = "📜 <b>История подписок:</b>\n\n"
    for item in history:
        start = item['start_date'].strftime('%d.%m.%Y')
        end = item['end_date'].strftime('%d.%m.%Y')
        amount = item.get('amount', 0)
        text += f"📅 {start} - {end} ({amount}₽)\n"

    await callback.message.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "go_profile", StateFilter(default_state))
@router.callback_query(F.data == "go_profile")
async def callback_go_profile(callback: CallbackQuery, state: FSMContext):
    """Переход в профиль с экрана выдачи ключа - работает независимо от FSM состояния"""
    telegram_id = callback.from_user.id
    
    # Немедленная обратная связь пользователю
    await callback.answer()
    
    # Очищаем FSM состояние, если пользователь был в каком-то процессе
    try:
        current_state = await state.get_state()
        if current_state is not None:
            await state.clear()
            logger.debug(f"Cleared FSM state for user {telegram_id}, was: {current_state}")
    except Exception as e:
        logger.debug(f"FSM state clear failed (may be already clear): {e}")
    
    try:
        logger.info(f"Opening profile via go_profile for user {telegram_id}")
        
        user = await database.get_user(telegram_id)
        language = user.get("language", "ru") if user else "ru"
        
        await show_profile(callback, language)
        
        logger.info(f"Profile opened successfully via go_profile for user {telegram_id}")
    except Exception as e:
        logger.exception(f"Error opening profile via go_profile for user {telegram_id}: {e}")
        # Пытаемся отправить сообщение об ошибке
        try:
            user = await database.get_user(telegram_id)
            language = user.get("language", "ru") if user else "ru"
            try:
                error_text = localization.get_text(language, "error_profile_load")
            except KeyError:
                logger.error(f"Missing localization key 'error_profile_load' for language '{language}'")
                error_text = "Ошибка загрузки профиля. Попробуйте позже."
            await callback.message.answer(error_text)
        except Exception as e2:
            logger.exception(f"Error sending error message to user {telegram_id}: {e2}")

@router.callback_query(F.data == "menu_vip_access")
async def callback_vip_access(callback: CallbackQuery):
    """Обработчик кнопки 'VIP-доступ'"""
    telegram_id = callback.from_user.id
    user = await database.get_user(telegram_id)
    language = user.get("language", "ru") if user else "ru"
    
    # Проверяем VIP-статус
    is_vip = await database.is_vip_user(telegram_id)
    
    # Получаем текст VIP-доступа
    text = localization.get_text(language, "vip_access_text")
    
    # Добавляем информацию о статусе, если пользователь VIP
    if is_vip:
        text += "\n\n" + localization.get_text(language, "vip_status_active", default="👑 Ваш VIP-статус активен")
    
    # Клавиатура с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=localization.get_text(language, "contact_manager_button", default="💬 Связаться с менеджером"),
            url="https://t.me/asc_support"
        )],
        [InlineKeyboardButton(
            text=localization.get_text(language, "back"),
            callback_data="menu_profile"
        )]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
