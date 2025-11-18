import os
import logging
import asyncio
from datetime import datetime, timedelta
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification
import uuid

logger = logging.getLogger(__name__)

class PaymentHandler:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        # Убираем зависимость от sub_manager, используем async_db
        print("✅ PaymentHandler инициализирован с PostgreSQL")

        # Настройка ЮKassa
        shop_id = os.getenv('YOOKASSA_SHOP_ID')
        secret_key = os.getenv('YOOKASSA_SECRET_KEY')
        
        if not shop_id or not secret_key:
            print("❌ ВНИМАНИЕ: YOOKASSA_SHOP_ID или YOOKASSA_SECRET_KEY не установлены!")
            print("   Для тестирования используйте команды /add_premium")
            return
        
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

    async def create_payment(self, user_id, tariff_type):
        """Создание платежа в ЮKassa"""
        try:
            if tariff_type not in self.tariff_plans:
                return None, "❌ Неверный тип тарифа"
            
            tariff = self.tariff_plans[tariff_type]
            
            # ID платежа для отслеживания
            payment_id = str(uuid.uuid4())

            # Для тестового режима используем демо-данные
            if not os.getenv('YOOKASSA_SHOP_ID'):
                print("🔵 DEBUG: Режим тестирования - создаем демо-платеж")
                return await self._create_demo_payment(user_id, tariff_type, payment_id)
            
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
                "description": f"{tariff['name']} для пользователя {user_id}",
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
            
            # Сохраняем информацию о платеже в PostgreSQL
            await self._save_payment_info(
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

    async def _create_demo_payment(self, user_id, tariff_type, payment_id):
        """Создание демо-платежа для тестирования"""
        tariff = self.tariff_plans[tariff_type]
        
        # Сохраняем демо-платеж в PostgreSQL
        await self._save_payment_info(
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

    async def _save_payment_info(self, user_id, payment_id, tariff_type, amount, status, yookassa_payment_id=None):
        """Сохранение информации о платеже в PostgreSQL"""
        try:
            await self.bot.async_db.save_payment(
                user_id=user_id,
                payment_id=payment_id,
                yookassa_payment_id=yookassa_payment_id,
                tariff_type=tariff_type,
                amount=amount,
                status=status
            )
            print(f"💾 Сохранен платеж {payment_id} для пользователя {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения платежа: {e}")

    async def process_webhook(self, webhook_data):
        """Обработка входящих вебхуков от ЮKassa"""
        try:
            print(f"🔔 Вебхук получен: {webhook_data}")
            
            event = webhook_data.get('event')
            payment_object = webhook_data.get('object', {})
            payment_id = payment_object.get('id')
            status = payment_object.get('status')
            
            print(f"📊 Событие: {event}, Платеж: {payment_id}, Статус: {status}")
            
            if event == 'payment.succeeded' and status == 'succeeded':
                # Ищем платеж в нашей БД по ID ЮKassa
                payment_info = await self._get_payment_by_yookassa_id(payment_id)
                
                if payment_info:
                    user_id = payment_info['user_id']
                    tariff_type = payment_info['tariff_type']
                    days = self.tariff_plans[tariff_type]['days']
                    
                    print(f"🎯 Найден платеж для пользователя {user_id}, тариф: {tariff_type}")
                    
                    # Активируем подписку
                    success = await self.activate_premium_subscription(user_id, days)
                    if success:
                        await self.send_payment_success_message(user_id, tariff_type, days)
                        await self._update_payment_status(payment_info['payment_id'], 'succeeded')
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
                payment_info = await self._get_payment_by_yookassa_id(payment_id)
                if payment_info:
                    await self._update_payment_status(payment_info['payment_id'], 'canceled')
            
            return False
            
        except Exception as e:
            print(f"❌ Ошибка обработки вебхука: {e}")
            import traceback
            print(f"❌ Подробности: {traceback.format_exc()}")
            return False
        
    async def _get_payment_by_yookassa_id(self, yookassa_payment_id):
        """Поиск платежа по ID ЮKassa в PostgreSQL"""
        try:
            payment = await self.bot.async_db.get_payment_by_id(yookassa_payment_id)
            if payment:
                return {
                    'user_id': payment['user_id'],
                    'payment_id': payment['payment_id'],
                    'tariff_type': payment['tariff_type'],
                    'status': payment['status']
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска платежа: {e}")
            return None

    async def _update_payment_status(self, payment_id, status):
        """Обновление статуса платежа в PostgreSQL"""
        try:
            await self.bot.async_db.update_payment_status(payment_id, status)
            print(f"📝 Обновлен статус платежа {payment_id} на {status}")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа: {e}")

    async def activate_premium_subscription(self, user_id, days):
        """Активация премиум подписки после успешной оплаты"""
        try:
            return await self.bot.async_db.add_premium_user(user_id, days)
        except Exception as e:
            logger.error(f"Ошибка активации подписки: {e}")
            return False

    async def send_payment_success_message(self, user_id, tariff_type, days):
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

    async def check_payment_status(self, payment_id):
        """Проверка статуса платежа с активацией подписки"""
        try:
            print(f"🔍 Проверка статуса платежа: {payment_id}")
            
            # Сначала проверяем в нашей БД
            payment_info = await self._get_payment_by_yookassa_id(payment_id)
            
            if not payment_info:
                print(f"❌ Платеж {payment_id} не найден в БД")
                return 'not_found'
            
            user_id, tariff_type, current_status = payment_info['user_id'], payment_info['tariff_type'], payment_info['status']
            
            # Если уже активирован - возвращаем статус
            if current_status == 'succeeded':
                return 'succeeded'
            
            # Проверяем статус в ЮKassa
            if not os.getenv('YOOKASSA_SHOP_ID'):
                print("🔵 Демо-режим: имитируем успешный платеж")
                # В демо-режиме активируем подписку
                days = self.tariff_plans[tariff_type]['days']
                if await self.activate_premium_subscription(user_id, days):
                    await self.send_payment_success_message(user_id, tariff_type, days)
                    await self._update_payment_status(payment_id, 'succeeded')
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
                    if await self.activate_premium_subscription(user_id, days):
                        await self.send_payment_success_message(user_id, tariff_type, days)
                        await self._update_payment_status(payment_id, 'succeeded')
                        print(f"✅ Подписка активирована для пользователя {user_id}")
                
                return status
                
            except Exception as e:
                print(f"❌ Ошибка API ЮKassa: {e}")
                return 'error'
                
        except Exception as e:
            print(f"❌ Ошибка проверки статуса: {e}")
            return 'error'

    def get_payment_url(self, payment):
        """Получение URL для оплаты"""
        if hasattr(payment, 'confirmation') and hasattr(payment.confirmation, 'confirmation_url'):
            return payment.confirmation.confirmation_url
        return None