from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

class BotInterface:
    def __init__(self, subscription_manager):
        self.sub_manager = subscription_manager
    
    def get_main_menu(self, user_id, username="", first_name=""):
        """Главное меню бота"""
        try:
            # НЕ вызываем can_send_message здесь - только получаем текущий статус
            cursor = self.sub_manager.conn.cursor()
            
            # Получаем информацию о подписке напрямую
            cursor.execute("SELECT subscription_type, expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                sub_type, expiry_date = result
                # Проверяем не истекла ли подписка                
                if expiry_date and datetime.now() > datetime.fromisoformat(expiry_date):
                    sub_type = 'free'
            else:
                sub_type = 'free'
            
            # Получаем статистику сообщений за сегодня
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT message_count FROM message_stats WHERE user_id = ? AND date = ?", 
                (user_id, today)
            )
            result = cursor.fetchone()
            messages_today = result[0] if result else 0
            
            # Текст статуса
            if sub_type == 'premium':
                status_icon = "💎"
                status_text = f"Premium подписка"
                limit_text = f"∞ сообщ."
            else:
                status_icon = "🆓"
                status_text = "Бесплатный тариф"
                daily_limit = 5
                limit_text = f"{messages_today}/{daily_limit} сообщ."

            # Основной текст меню
            text = f"""👋 Привет, {first_name}!

    Я - твой личный AI-психолог. 

    <b>Твой статус:</b>
    {status_icon} {status_text} · {limit_text}

    Здесь ты можешь:
    • Получить поддержку в сложный момент
    • Найти практические техники для работы с эмоциями  
    • Изучить психологические подходы из проверенных книг
    • Разобраться в себе шаг за шагом

    <code>Отправляя сообщение, вы принимаете условия:</code>
    📄 <a href="https://psychologybot.netlify.app/offer.html">Публичной оферты</a>
    🔒 <a href="https://psychologybot.netlify.app/privacy.html">Политики конфиденциальности</a>

    Я здесь, чтобы помочь тебе стать лучшей версией себя! 💫

    <b>Выберите раздел:</b>"""
        
            keyboard = [
                [InlineKeyboardButton("💬 Консультация AI", callback_data="consult_ai")],                
                [InlineKeyboardButton("💎 Управление подпиской", callback_data="subscription")],
                [InlineKeyboardButton("📊 Моя статистика", callback_data="stats")],
                [InlineKeyboardButton("🆘 Обратная связь", callback_data="help")]
            ]
        
            return text, InlineKeyboardMarkup(keyboard)
        
        except Exception as e:
            print(f"❌ Ошибка в get_main_menu: {e}")
            # Заглушка при ошибке
            error_text = f"""👋 Привет, {first_name}!

    Я - твой личный AI-психолог. 

    ❌ <b>Временные технические неполадки</b>
    Мы уже работаем над решением!⚠️

    <b>Выберите раздел:</b>"""
            
            keyboard = [
                [InlineKeyboardButton("💬 Консультация AI", callback_data="consult_ai")],            
                [InlineKeyboardButton("💎 Управление подпиской", callback_data="subscription")],
                [InlineKeyboardButton("📊 Моя статистика", callback_data="stats")]
            ]
        
        return error_text, InlineKeyboardMarkup(keyboard)
    
    def get_payment_menu(self, user_id, tariff_type):
        """Меню оплаты для конкретного тарифа"""
        tariff_plans = {
            'premium_month': {
                'name': 'Premium (1 месяц)',
                'price': 139.00,
                'days': 30,
                'savings': ''
            },
            'premium_year': {
                'name': 'Premium (1 год)', 
                'price': 990.00,
                'days': 365,
                'savings': '💰 SALE'
            }
        }
        
        tariff = tariff_plans.get(tariff_type, tariff_plans['premium_month'])
        
        text = f"""💎 <b>Оформление {tariff['name']}</b>

<b>Тариф:</b> {tariff['name']}
<b>Стоимость:</b> {tariff['price']}₽
<b>Срок:</b> {tariff['days']} дней
{tariff['savings']}

🎁 <b>Что входит:</b>
• ♾️ Безлимитное общение с AI-психологом
• 🚀 Приоритетная обработка запросов  
• 📚 Полный доступ к психологической библиотеке
• 🎯 Расширенные функции и техники

💳 <b>Способы оплаты:</b>
• Банковская карта (Visa, MasterCard, МИР)
• ЮMoney
• Сбербанк Онлайн
• Тинькофф
• QIWI

🔐 <b>Безопасность:</b>
Все платежи защищены ЮKassa"""

        keyboard = [
            [InlineKeyboardButton("💳 Оплатить картой", callback_data=f"pay_{tariff_type}")],
            [InlineKeyboardButton("📋 Другие способы оплаты", callback_data=f"pay_methods_{tariff_type}")],
            [InlineKeyboardButton("🔙 Назад к тарифам", callback_data="subscription")]
        ]
    
        return text, InlineKeyboardMarkup(keyboard)

    def get_payment_methods_menu(self, user_id, tariff_type):
        """Меню с альтернативными способами оплаты"""
        tariff_plans = {
            'premium_month': {'name': 'Premium (1 месяц)', 'price': 139},
            'premium_year': {'name': 'Premium (1 год)', 'price': 990}
        }
        
        tariff = tariff_plans.get(tariff_type)
        
        text = f"""💎 <b>Альтернативные способы оплаты</b>

<b>Тариф:</b> {tariff['name']}
<b>Сумма:</b> {tariff['price']}₽

📱 <b>Доступные способы:</b>

• **ЮMoney** (кошелек или карта)
• **Сбербанк Онлайн** (по номеру телефона)  
• **Тинькофф** (интернет-банк)• 
• **Мобильные операторы** (МТС)


💡 <b>После оплаты:</b>
1. Сохраните чек/скриншот оплаты
2. Отправьте его @danilskopov
3. Мы активируем подписку в течение часа

Или используйте оплату картой для мгновенной активации!"""

        keyboard = [
            [InlineKeyboardButton("💳 Оплатить картой (мгновенно)", callback_data=f"pay_{tariff_type}")],
            [InlineKeyboardButton("📞 Связаться для оплаты", url="https://t.me/danil_skopov")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"payment_{tariff_type}")]
        ]
    
        return text, InlineKeyboardMarkup(keyboard)

    def get_payment_success_menu(self, user_id, tariff_type, payment_id):
        """Меню после создания платежа"""
        tariff_plans = {
            'premium_month': {'name': 'Premium (1 месяц)', 'price': 139},
            'premium_year': {'name': 'Premium (1 год)', 'price': 990}
        }
        
        tariff = tariff_plans.get(tariff_type)
        
        text = f"""💎 <b>Платеж создан!</b>

<b>Тариф:</b> {tariff['name']}
<b>Сумма:</b> {tariff['price']}₽
<b>ID платежа:</b> <code>{payment_id}</code>

⬇️ <b>Для оплаты нажмите кнопку ниже</b>

После успешной оплаты подписка активируется автоматически в течение 1-2 минут.

💡 <b>Если возникли проблемы:</b>
• Нажмите "Проверить статус" через 5 минут
• Или напишите @danil_skopov с ID платежа"""

        keyboard = [
            [InlineKeyboardButton("💳 Перейти к оплате", callback_data=f"process_payment_{payment_id}")],
            [InlineKeyboardButton("🔄 Проверить статус", callback_data=f"check_payment_{payment_id}")],
            [InlineKeyboardButton("📞 Поддержка", url="https://t.me/danil_skopov")],
            [InlineKeyboardButton("🔙 Назад к тарифам", callback_data="subscription")]
        ]
    
        return text, InlineKeyboardMarkup(keyboard)

    def get_payment_status_menu(self, user_id, payment_id, status):
        """Меню статуса платежа"""
        status_texts = {
            'pending': "⏳ Ожидает оплаты",
            'waiting_for_capture': "⏳ Ожидает подтверждения", 
            'succeeded': "✅ Оплачен",
            'canceled': "❌ Отменен",
            'failed': "❌ Не удался"
        }
        
        status_text = status_texts.get(status, status)
        
        text = f"""📊 <b>Статус платежа</b>

<b>ID платежа:</b> <code>{payment_id}</code>
<b>Статус:</b> {status_text}

💡 <b>Что делать:</b>
• Если статус "Ожидает оплаты" - завершите оплату
• Если статус "Ожидает подтверждения" - ждите 1-2 минуты
• Если статус "Оплачен" - подписка активирована!
• При проблемах - обратитесь в поддержку"""

        keyboard = []
        
        if status in ['pending', 'waiting_for_capture']:
            keyboard.append([InlineKeyboardButton("🔄 Обновить статус", callback_data=f"check_payment_{payment_id}")])
        
        keyboard.extend([
            [InlineKeyboardButton("💳 Попробовать снова", callback_data="subscription")],
            [InlineKeyboardButton("📞 Поддержка", url="https://t.me/danilskopov")],
            [InlineKeyboardButton("🔙 В главное меню", callback_data="back_main")]
        ])
    
        return text, InlineKeyboardMarkup(keyboard)

    def get_payment_history_menu(self, user_id):
        """История платежей пользователя"""
        try:
            # Получаем историю платежей из базы
            payments = getattr(self.sub_manager, 'get_payment_history', lambda x: [])(user_id)
            
            if not payments:
                text = """📊 <b>История платежей</b>

У вас еще не было платежей.

💎 <b>Хотите оформить подписку?</b>
Премиум доступ откроет безлимитное общение с AI-психологом!"""
                
                keyboard = [
                    [InlineKeyboardButton("💎 Выбрать тариф", callback_data="subscription")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
                ]
            else:
                text = "📊 <b>История платежей</b>\n\n"
                
                for i, payment in enumerate(payments[-5:], 1):  # Последние 5 платежей
                    status_icons = {
                        'succeeded': '✅',
                        'pending': '⏳', 
                        'canceled': '❌',
                        'failed': '❌'
                    }
                    
                    status_icon = status_icons.get(payment['status'], '📄')
                    text += f"{status_icon} {payment['tariff_type']} - {payment['amount']}₽ - {payment['status']}\n"
                
                text += "\n💡 Для подробной информации обратитесь в поддержку"
                
                keyboard = [
                    [InlineKeyboardButton("💎 Новый платеж", callback_data="subscription")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
                ]
            
            return text, InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            print(f"❌ Ошибка получения истории платежей: {e}")
            
            text = """📊 <b>История платежей</b>

❌ Не удалось загрузить историю платежей.

💡 Попробуйте позже или обратитесь в поддержку."""
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            
            return text, InlineKeyboardMarkup(keyboard)

    def _get_subscription_text(self, sub_type, days_left):
        if sub_type == 'trial':
            return f"Пробный период ({days_left} дней осталось)"
        elif sub_type == 'premium':
            return "PREMIUM подписка"
        else:
            return "Бесплатный тариф"
    
    def get_stats_message(self, user_id):
        """Сообщение со статистикой БЕЗ проверки лимитов"""
        try:
            # Получаем данные напрямую из БД
            cursor = self.sub_manager.conn.cursor()
            
            # Получаем информацию о подписке
            cursor.execute("SELECT subscription_type, expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                sub_type, expiry_date = result
                # Проверяем не истекла ли подписка                
                if expiry_date and datetime.now() > datetime.fromisoformat(expiry_date):
                    sub_type = 'free'
            else:
                sub_type = 'free'
            
            # Получаем статистику сообщений
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT message_count FROM message_stats WHERE user_id = ? AND date = ?", 
                (user_id, today)
            )
            result = cursor.fetchone()
            messages_today = result[0] if result else 0
            
            # Формируем текст
            if sub_type == 'premium':
                sub_info = "Подписка: 💎 Premium"
                # Вычисляем дни подписки
                if expiry_date:
                    days_left = max(0, (datetime.fromisoformat(expiry_date) - datetime.now()).days)
                    limit_info = f"📅 Дней осталось: {days_left}"
                else:
                    limit_info = "📅 Срок: бессрочно"
                rec_text = "🎉 Полный доступ активирован!"
            else:
                daily_limit = 5
                sub_info = f"Подписка: 🆓 {sub_type.capitalize()} тариф"
                limit_info = f"📨 Сообщений сегодня: {messages_today}/{daily_limit}"
                rec_text = "💡 Перейдите на Premium для безлимитного общения!"
        
            text = f"""📊 <b>Ваша статистика</b>

    {sub_info}
    {limit_info}
        
    🆔 Твой ID: <code>{user_id}</code>

    {rec_text}"""
        
            return text, self.get_back_to_menu_button()
        
        except Exception as e:
            print(f"❌ Ошибка в get_stats_message: {e}")
            return "❌ Ошибка загрузки статистики", self.get_back_to_menu_button()
    
    def get_back_to_menu_button(self):
        """Кнопка для возврата в главное меню"""
        keyboard = [
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_help_message(self, user_id):
        """Сообщение обратной связи с кнопкой возврата"""
        help_text = """🆘 <b>Обратная связь</b>

🤝 <b>Нужна помощь или есть вопросы?</b>

📧 <b>Связь с разработчиком:</b>
• Telegram: @danilskopov
• Email: danil.skopov@gmail.com

💬 <b>По вопросам:</b>
• Технические проблемы с ботом
• Оплата и активация Premium подписки  
• Предложения по улучшению бота
• Сотрудничество

📋 <b>Перед обращением:</b>
1. Проверьте команду /myid - укажите ваш ID
2. Опишите проблему максимально подробно
3. Приложите скриншот если есть ошибка

<b>Мы всегда рады помочь! ❤️</b>"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_main")]
        ])
        
        return help_text, keyboard

    def get_subscription_menu(self, user_id):
        """Меню подписок"""
        try:
            # Получаем данные напрямую из БД
            cursor = self.sub_manager.conn.cursor()
            
            # Получаем информацию о подписке
            cursor.execute("SELECT subscription_type, expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                sub_type, expiry_date = result
                # Проверяем не истекла ли подписка                
                if expiry_date and datetime.now() > datetime.fromisoformat(expiry_date):
                    sub_type = 'free'
            else:
                sub_type = 'free'
            
            # Формируем текст статуса
            if sub_type == 'premium':
                if expiry_date:
                    days_left = max(0, (datetime.fromisoformat(expiry_date) - datetime.now()).days)
                    status_text = f"💎 Premium подписка ({days_left} дней)"
                else:
                    status_text = "💎 Premium подписка"
            else:
                status_text = "🆓 Бесплатный тариф"
        
            keyboard = [
                [InlineKeyboardButton("💎 Premium - 139₽/месяц", callback_data="pay_premium_month")],
                [InlineKeyboardButton("💎 Premium Год - 990₽/год", callback_data="pay_premium_year")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_main")]
            ]
        
            text = f"""💳 <b>Управление подпиской</b>

    <b>Текущий статус:</b> {status_text}

    📊 <b>Доступные тарифы:</b>

    💎 <b>Premium (1 месяц)</b> - 139₽
    • ♾️ Безлимитные сообщения
    • 🚀 Приоритетная обработка
    

    💎 <b>Premium (1 год)</b> - 990₽
    • Всё то же + экономия 20%
    • Год психологической поддержки

    💡 <b>После оплаты подписка активируется автоматически!</b>"""
        
            return text, InlineKeyboardMarkup(keyboard)
        
        except Exception as e:
            print(f"❌ Ошибка в get_subscription_menu: {e}")
            error_text = """💳 <b>Управление подпиской</b>

    ❌ Не удалось загрузить статус подписки

    💎 <b>Premium (1 месяц)</b> - 139₽
    • Безлимитные сообщения

    💎 <b>Premium (1 год)</b> - 990₽  
    • Экономия 20%"""
        
            keyboard = [
                [InlineKeyboardButton("💎 Premium - 139₽/месяц", callback_data="pay_premium_month")],
                [InlineKeyboardButton("💎 Premium Год - 990₽/год", callback_data="pay_premium_year")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_main")]
            ]
        
            return error_text, InlineKeyboardMarkup(keyboard)

    def get_consultation_menu(self, user_id):
        """Меню консультации"""
        try:
            # Получаем данные напрямую из БД
            cursor = self.sub_manager.conn.cursor()
            
            cursor.execute("SELECT subscription_type FROM subscriptions WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            sub_type = result[0] if result else 'free'
            
            # Получаем статистику сообщений
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT message_count FROM message_stats WHERE user_id = ? AND date = ?", 
                (user_id, today)
            )
            result = cursor.fetchone()
            messages_today = result[0] if result else 0
            
            if sub_type == 'premium':
                status_info = "💎 Premium - безлимитные сообщения"
                advice = "Просто напишите ваш вопрос, и я помогу вам!"
            else:
                daily_limit = 5
                status_info = f"🆓 {sub_type.capitalize()} - {messages_today}/{daily_limit} сообщений сегодня"
                advice = "💡 Перейдите на Premium для безлимитного общения!"
            
            text = f"""💬 <b>Консультация с AI-психологом</b>

    {status_info}

    🤖 <b>Я готов помочь вам с:</b>
    • Эмоциональными трудностями
    • Отношениями и коммуникацией  
    • Стрессом и тревогой
    • Самооценкой и мотивацией
    • Поиском психологических техник

    📝 <b>Как это работает:</b>
    1. Опишите вашу ситуацию или вопрос
    2. Я проанализирую её на основе психологических знаний
    3. Предложу практические техники и советы

    {advice}

    <b>Просто напишите ваш вопрос в чат!</b> ✍️"""
            
            keyboard = [
                [InlineKeyboardButton("💎 Premium подписка", callback_data="subscription")],
                [InlineKeyboardButton("📊 Моя статистика", callback_data="stats")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_main")]
            ]
            
            return text, InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            print(f"❌ Ошибка в get_consultation_menu: {e}")
            return "❌ Ошибка загрузки меню", self.get_back_to_menu_button()        