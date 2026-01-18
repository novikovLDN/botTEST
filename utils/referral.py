import logging
from aiogram import Bot
import database

logger = logging.getLogger(__name__)

async def send_referral_cashback_notification(
    bot: Bot,
    referrer_id: int,
    referred_id: int,
    purchase_amount: float,
    cashback_amount: float,
    cashback_percent: int,
    paid_referrals_count: int,
    referrals_needed: int,
    action_type: str = "покупку"
) -> bool:
    """
    Отправить уведомление рефереру о начислении кешбэка
    
    Args:
        bot: Экземпляр бота
        referrer_id: Telegram ID реферера
        referred_id: Telegram ID реферала
        purchase_amount: Сумма покупки в рублях
        cashback_amount: Сумма кешбэка в рублях
        cashback_percent: Процент кешбэка
        paid_referrals_count: Количество оплативших рефералов
        referrals_needed: Сколько рефералов нужно до следующего уровня
        action_type: Тип действия ("покупку", "продление", "пополнение")
    
    Returns:
        True если уведомление отправлено, False если ошибка
    """
    try:
        # Получаем информацию о реферале (username)
        referred_user = await database.get_user(referred_id)
        referred_username = referred_user.get("username") if referred_user else None
        referred_display = f"@{referred_username}" if referred_username else f"ID: {referred_id}"
        
        # Формируем текст уведомления
        if referrals_needed > 0:
            progress_text = f"👥 До следующего уровня: осталось пригласить {referrals_needed} друга"
        else:
            progress_text = "🎯 Вы достигли максимального уровня!"
        
        notification_text = (
            f"🎉 Ваш реферал совершил {action_type}!\n\n"
            f"👤 Реферал: {referred_display}\n"
            f"💳 Сумма {action_type}: {purchase_amount:.2f} ₽\n"
            f"💰 Начислен кешбэк: {cashback_amount:.2f} ₽ ({cashback_percent}%)\n\n"
            f"📊 Ваш уровень: {cashback_percent}%\n"
            f"{progress_text}\n\n"
            f"Баланс пополнен автоматически."
        )
        
        # Отправляем уведомление
        await bot.send_message(
            chat_id=referrer_id,
            text=notification_text
        )
        
        logger.info(
            f"Referral cashback notification sent: referrer={referrer_id}, "
            f"referred={referred_id}, amount={cashback_amount:.2f} RUB, percent={cashback_percent}%"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send referral cashback notification: referrer={referrer_id}, error={e}")
        return False
