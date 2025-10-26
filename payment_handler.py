import os
import logging
import sqlite3
from datetime import datetime, timedelta
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification
import uuid

logger = logging.getLogger(__name__)

class PaymentHandler:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.sub_manager = bot_instance.sub_manager
        
        # Настройка ЮKassa - ИСПРАВЛЕННАЯ ВЕРСИЯ
        shop_id = os.getenv('YOOKASSA_SHOP_ID')
        secret_key = os.getenv('YOOKASSA_SECRET_KEY')
        
        if not shop_id or not secret_key:
            print("❌ ВНИМАНИЕ: YOOKASSA_SHOP_ID или YOOKASSA_SECRET_KEY не установлены!")
            print("   Для тестирования используйте команды /add_premium")
            return
        
        # ПРАВИЛЬНАЯ НАСТРОЙКА КОНФИГУРАЦИИ
        try:
            Configuration.configure(shop_id, secret_key)
            print("✅ ЮKassa Configuration настроен корректно")
        except Exception as e:
            print(f"❌ Ошибка настройки ЮKassa: {e}")
            return
        
        self.tariff_plans = {
            'premium_month': {
                'name': 'Premium (1 месяц)',
                'price': 139.00,
                'days': 30,
                'description': '💎 Безлимитное общение с AI-психологом'
            },
            'premium_year': {
                'name': 'Premium (1 год)',
                'price': 990.00,
                'days': 365,
                'description': '💎 Безлимитное общение + экономия 20%'
            }
        }
        
        print("✅ PaymentHandler инициализирован")

    def create_payment(self, user_id, tariff_type):
        """Создание платежа в ЮKassa"""
        try:
                if tariff_type not in self.tariff_plans:
                    return None, "❌ Неверный тип тарифа"
                
                tariff = self.tariff_plans[tariff_type]
                
                # ID платежа для отслеживания
                payment_id = str(uuid.uuid4())

                bot_username = "@your_sweet_PsychoBot"
                
                # Описание платежа
                description = f"{tariff['name']} для пользователя {user_id}"
                
                # Для тестового режима используем демо-данные
                if not os.getenv('YOOKASSA_SHOP_ID'):
                    print("🔵 DEBUG: Режим тестирования - создаем демо-платеж")
                    return self._create_demo_payment(user_id, tariff_type, payment_id)
                
                # Создаем реальный платеж в ЮKassa
                payment = Payment.create({
                    "amount": {
                        "value": f"{tariff['price']:.2f}",
                        "currency": "RUB"
                    },
                    "confirmation": {
                        "type": "redirect",
                        "return_url": f"https://t.me/your_sweet_PsychoBot"
                    },
                    "capture": True,
                    "description": description,
                    "metadata": {
                        "user_id": user_id,
                        "tariff_type": tariff_type,
                        "days": tariff['days'],
                        "bot_payment_id": payment_id
                    },
                    "receipt": {
                        "customer": {
                            "email": f"user{user_id}@telegram.org"
                        },
                        "items": [
                            {
                                "description": tariff['description'],
                                "quantity": "1",
                                "amount": {
                                    "value": f"{tariff['price']:.2f}",
                                    "currency": "RUB"
                                },
                                "vat_code": "1",
                                "payment_mode": "full_payment",
                                "payment_subject": "service"
                            }
                        ]
                    }
                })
                
                # Сохраняем информацию о платеже
                self._save_payment_info(
                    user_id=user_id,
                    payment_id=payment.id,
                    tariff_type=tariff_type,
                    amount=tariff['price'],
                    status=payment.status,
                    yookassa_payment_id=payment.id
                )
                
                print(f"✅ Создан платеж {payment.id} для пользователя {user_id}")
                return payment, None



            
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return None, f"❌ Ошибка создания платежа: {e}"

    def _create_demo_payment(self, user_id, tariff_type, payment_id):
        """Создание демо-платежа для тестирования"""
        tariff = self.tariff_plans[tariff_type]
        
        # Сохраняем демо-платеж
        self._save_payment_info(
            user_id=user_id,
            payment_id=payment_id,
            tariff_type=tariff_type,
            amount=tariff['price'],
            status='pending',
            yookassa_payment_id=f"demo_{payment_id}"
        )
        
        # Имитируем объект платежа
        class DemoPayment:
            def __init__(self):
                self.id = payment_id
                self.status = 'pending'
                self.confirmation = type('obj', (object,), {
                    'confirmation_url': f"https://yookassa.ru/demo/payment/{payment_id}"
                })
        
        print(f"🔵 DEBUG: Создан демо-платеж {payment_id}")
        return DemoPayment(), None

    def _save_payment_info(self, user_id, payment_id, tariff_type, amount, status, yookassa_payment_id=None):
        """Сохранение информации о платеже в БД"""
        try:
            cursor = self.sub_manager.conn.cursor()
            cursor.execute('''
                INSERT INTO payments 
                (user_id, payment_id, tariff_type, amount, status, yookassa_payment_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, payment_id, tariff_type, amount, status, yookassa_payment_id, datetime.now()))
            
            self.sub_manager.conn.commit()
            print(f"💾 Сохранен платеж {payment_id} для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения платежа: {e}")
            # Если ошибка с таблицей, пересоздадим её
            if "no such table" in str(e) or "no such column" in str(e):
                print("🔄 Пересоздаю таблицу payments...")
                self.sub_manager.create_tables()
                # Повторяем попытку
                cursor.execute('''
                    INSERT INTO payments 
                    (user_id, payment_id, tariff_type, amount, status, yookassa_payment_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, payment_id, tariff_type, amount, status, yookassa_payment_id, datetime.now()))
                self.sub_manager.conn.commit()

    def process_webhook(self, webhook_data):
        """Обработка входящих вебхуков от ЮKassa"""
        try:
            print(f"🔔 Вебхук получен: {webhook_data}")
            
            # Проверяем тип события
            event = webhook_data.get('event')
            payment_object = webhook_data.get('object', {})
            payment_id = payment_object.get('id')
            status = payment_object.get('status')
            
            print(f"📊 Событие: {event}, Платеж: {payment_id}, Статус: {status}")
            
            if event == 'payment.succeeded' and status == 'succeeded':
                # Ищем платеж в нашей БД по ID ЮKassa
                payment_info = self._get_payment_by_yookassa_id(payment_id)
                
                if payment_info:
                    user_id = payment_info['user_id']
                    tariff_type = payment_info['tariff_type']
                    days = self.tariff_plans[tariff_type]['days']
                    
                    print(f"🎯 Найден платеж для пользователя {user_id}, тариф: {tariff_type}")
                    
                    # Активируем подписку
                    success = self.activate_premium_subscription(user_id, days)
                    if success:
                        self.send_payment_success_message(user_id, tariff_type, days)
                        self._update_payment_status(payment_info['payment_id'], 'succeeded')
                        print(f"✅ Автоматически активирована подписка для пользователя {user_id}")
                        return True
                    else:
                        print(f"❌ Ошибка активации подписки для {user_id}")
                else:
                    print(f"⚠️ Платеж {payment_id} не найден в базе данных")
                    
            elif event == 'payment.waiting_for_capture':
                print(f"⏳ Платеж {payment_id} ожидает подтверждения")
                
            elif event == 'payment.canceled':
                print(f"❌ Платеж {payment_id} отменен")
                payment_info = self._get_payment_by_yookassa_id(payment_id)
                if payment_info:
                    self._update_payment_status(payment_info['payment_id'], 'canceled')
            
            return False
            
        except Exception as e:
            print(f"❌ Ошибка обработки вебхука: {e}")
            import traceback
            print(f"❌ Подробности: {traceback.format_exc()}")
            return False
        
    def _get_payment_by_yookassa_id(self, yookassa_payment_id):
        """Поиск платежа по ID ЮKassa"""
        try:
            cursor = self.sub_manager.conn.cursor()
            cursor.execute('''
                SELECT user_id, payment_id, tariff_type, status 
                FROM payments 
                WHERE yookassa_payment_id = ? OR payment_id = ?
            ''', (yookassa_payment_id, yookassa_payment_id))
            
            result = cursor.fetchone()
            if result:
                return {
                    'user_id': result[0],
                    'payment_id': result[1],
                    'tariff_type': result[2],
                    'status': result[3]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска платежа: {e}")
            return None

    def _update_payment_status(self, payment_id, status):
        """Обновление статуса платежа в БД"""
        try:
            cursor = self.sub_manager.conn.cursor()
            cursor.execute('''
                UPDATE payments SET status = ?, updated_at = ? 
                WHERE payment_id = ? OR yookassa_payment_id = ?
            ''', (status, datetime.now(), payment_id, payment_id))
            self.sub_manager.conn.commit()
            print(f"📝 Обновлен статус платежа {payment_id} на {status}")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа: {e}")

    def activate_premium_subscription(self, user_id, days):
        """Активация премиум подписки после успешной оплаты"""
        try:
            return self.sub_manager.add_premium_user(user_id, days)
        except Exception as e:
            logger.error(f"Ошибка активации подписки: {e}")
            return False

    def send_payment_success_message(self, user_id, tariff_type, days):
        """Отправка сообщения об успешной оплате"""
        try:
            tariff = self.tariff_plans.get(tariff_type, {})
            message = f"""🎉 <b>Оплата прошла успешно!</b>

💎 <b>Ваш Premium доступ активирован!</b>

📅 Срок действия: {days} дней
💰 Тариф: {tariff.get('name', 'Premium')}
💬 Сообщений: ♾️ безлимитно

Теперь вам доступно:
• ♾️ Безлимитное общение с AI
• 🚀 Приоритетная обработка запросов  
• 📚 Полный доступ к библиотеке
• 🎯 Расширенные функции

Спасибо за доверие! ❤️

Для начала общения просто напишите сообщение."""
            
            self.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения об успехе: {e}")

    def send_payment_failed_message(self, user_id, status):
        """Отправка сообщения о неудачной оплате"""
        try:
            if status == 'canceled':
                message = """❌ <b>Платеж отменен</b>

Если это произошло по ошибке, попробуйте оплатить снова.

Для помощи обращайтесь: @danil_skopov"""
            else:
                message = """⏳ <b>Платеж ожидает подтверждения</b>

Обычно это занимает несколько минут. Мы уведомим вас, когда платеж будет подтвержден."""
            
            self.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения о неудаче: {e}")

    def check_payment_status(self, payment_id):
        """Проверка статуса платежа с активацией подписки"""
        try:
            print(f"🔍 Проверка статуса платежа: {payment_id}")
            
            # Сначала проверяем в нашей БД
            cursor = self.sub_manager.conn.cursor()
            cursor.execute("""
                SELECT user_id, tariff_type, status 
                FROM payments 
                WHERE payment_id = ? OR yookassa_payment_id = ?
            """, (payment_id, payment_id))
            
            payment_info = cursor.fetchone()
            
            if not payment_info:
                print(f"❌ Платеж {payment_id} не найден в БД")
                return 'not_found'
            
            user_id, tariff_type, current_status = payment_info
            
            # Если уже активирован - возвращаем статус
            if current_status == 'succeeded':
                return 'succeeded'
            
            # Проверяем статус в ЮKassa
            if not os.getenv('YOOKASSA_SHOP_ID'):
                print("🔵 Демо-режим: имитируем успешный платеж")
                # В демо-режиме активируем подписку
                days = self.tariff_plans[tariff_type]['days']
                if self.activate_premium_subscription(user_id, days):
                    self.send_payment_success_message(user_id, tariff_type, days)
                    self._update_payment_status(payment_id, 'succeeded')
                    return 'succeeded'
                return 'pending'
            
            # Реальная проверка через API ЮKassa
            try:
                payment = Payment.find_one(payment_id)
                status = payment.status
                
                print(f"🔍 Статус от ЮKassa: {status}")
                
                if status == 'succeeded':
                    # Активируем подписку
                    days = self.tariff_plans[tariff_type]['days']
                    if self.activate_premium_subscription(user_id, days):
                        self.send_payment_success_message(user_id, tariff_type, days)
                        self._update_payment_status(payment_id, 'succeeded')
                        print(f"✅ Подписка активирована для пользователя {user_id}")
                
                return status
                
            except Exception as e:
                print(f"❌ Ошибка API ЮKassa: {e}")
                return 'error'
                
        except Exception as e:
            print(f"❌ Ошибка проверки статуса: {e}")
            return 'error'
    
    def check_and_activate_payments(self):
        """Проверить и активировать оплаченные платежи"""
        try:
            cursor = self.sub_manager.conn.cursor()
            
            # Ищем pending платежи
            cursor.execute("""
                SELECT payment_id, user_id, tariff_type, yookassa_payment_id 
                FROM payments 
                WHERE status = 'pending'
            """)
            pending_payments = cursor.fetchall()
            
            activated_count = 0
            
            for payment_id, user_id, tariff_type, yookassa_id in pending_payments:
                # Проверяем статус в ЮKassa
                status, payment = self.check_payment_status(yookassa_id or payment_id)
                
                if status == 'succeeded':
                    # Активируем подписку
                    days = self.tariff_plans[tariff_type]['days']
                    if self.activate_premium_subscription(user_id, days):
                        self.send_payment_success_message(user_id, tariff_type, days)
                        self._update_payment_status(payment_id, 'succeeded')
                        activated_count += 1
                        print(f"✅ Активирована подписка для пользователя {user_id}")
                
                elif status in ['canceled', 'failed']:
                    self._update_payment_status(payment_id, status)
            
            if activated_count > 0:
                print(f"🎉 Активировано {activated_count} подписок")
                
            return activated_count
            
        except Exception as e:
            print(f"❌ Ошибка проверки платежей: {e}")
            return 0

    def setup_webhook(self):
        """Настройка вебхуков в ЮKassa"""
        try:
            print("🔧 Начинаю настройку вебхуков...")
            
            # Проверяем настройки API
            shop_id = os.getenv('YOOKASSA_SHOP_ID')
            secret_key = os.getenv('YOOKASSA_SECRET_KEY')
            
            print(f"🔑 Shop ID: {'✅ Установлен' if shop_id else '❌ Отсутствует'}")
            print(f"🔑 Secret Key: {'✅ Установлен' if secret_key else '❌ Отсутствует'}")
            
            if not shop_id or not secret_key:
                print("❌ Ключи API ЮKassa не настроены в .env")
                return False
            
            # Проверяем доступность вебхук-сервера
            try:
                import requests
                response = requests.get("https://yookassa-webhook-gstx.onrender.com/health", timeout=10)
                print(f"🌐 Проверка сервера: код {response.status_code}")
                if response.status_code != 200:
                    print("❌ Вебхук-сервер недоступен")
                    return False
            except Exception as e:
                print(f"❌ Ошибка проверки сервера: {e}")
                return False
            
            # URL вашего вебхука на Render
            webhook_url = "https://yookassa-webhook-gstx.onrender.com/webhook/yookassa"
            print(f"🔗 Webhook URL: {webhook_url}")
            
            # Импортируем Webhook только после проверки конфигурации
            from yookassa import Webhook
            
            try:
                # Получаем список текущих вебхуков
                print("📋 Получаю список текущих вебхуков...")
                webhooks = Webhook.list()
                print(f"📋 Найдено вебхуков: {len(webhooks.items)}")
                
                # Удаляем старые вебхуки на тот же URL
                for webhook in webhooks.items:
                    if webhook.url == webhook_url:
                        try:
                            print(f"🗑️ Удаляю старый вебхук: {webhook.id}")
                            Webhook.remove(webhook.id)
                            print(f"✅ Вебхук удален: {webhook.id}")
                        except Exception as e:
                            print(f"⚠️ Не удалось удалить вебхук {webhook.id}: {e}")
            except Exception as e:
                print(f"⚠️ Ошибка при работе со списком вебхуков: {e}")
                # Продолжаем попытку добавить вебхук даже если список не получен
            
            # Добавляем вебхук для успешных платежей
            try:
                print("➕ Добавляю новый вебхук...")
                webhook = Webhook.add({
                    "event": "payment.succeeded",
                    "url": webhook_url
                })
                
                print("✅ Вебхук успешно добавлен!")
                print(f"🔗 URL: {webhook.url}")
                print(f"🎯 Событие: {webhook.event}")
                print(f"🆔 ID: {webhook.id}")
                
                return True
                
            except Exception as e:
                print(f"❌ Ошибка добавления вебхука: {e}")
                import traceback
                print(f"🔍 Детали ошибки: {traceback.format_exc()}")
                return False
            
        except Exception as e:
            print(f"❌ Критическая ошибка настройки вебхука: {e}")
            import traceback
            print(f"🔍 Детали: {traceback.format_exc()}")
            return False

    def get_payment_url(self, payment):
        """Получение URL для оплаты"""
        if hasattr(payment, 'confirmation') and hasattr(payment.confirmation, 'confirmation_url'):
            return payment.confirmation.confirmation_url
        return None