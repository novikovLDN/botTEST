from aiogram.fsm.state import State, StatesGroup

class AdminUserSearch(StatesGroup):
    waiting_for_user_id = State()

class AdminReferralSearch(StatesGroup):
    waiting_for_search_query = State()

class BroadcastCreate(StatesGroup):
    waiting_for_title = State()
    waiting_for_test_type = State()
    waiting_for_message = State()
    waiting_for_message_a = State()
    waiting_for_message_b = State()
    waiting_for_type = State()
    waiting_for_segment = State()
    waiting_for_confirm = State()

class IncidentEdit(StatesGroup):
    waiting_for_text = State()

class AdminGrantAccess(StatesGroup):
    waiting_for_days = State()

class AdminDiscountCreate(StatesGroup):
    waiting_for_percent = State()
    waiting_for_expires = State()

class PromoCodeInput(StatesGroup):
    waiting_for_promo = State()

class TopUpStates(StatesGroup):
    waiting_for_amount = State()

class AdminCreditBalance(StatesGroup):
    waiting_for_user_search = State()
    waiting_for_amount = State()
    waiting_for_confirmation = State()

class PurchaseState(StatesGroup):
    """FSM состояния для процесса покупки"""
    choose_tariff = State()           # Выбор тарифа (Basic/Plus)
    choose_period = State()           # Выбор периода (1/3/6/12 месяцев)
    choose_payment_method = State()   # Выбор способа оплаты (баланс/карта)
    processing_payment = State()      # Обработка оплаты (invoice создан или баланс списывается)
