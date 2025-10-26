import os
import signal
import sys

# Обработка graceful shutdown
def signal_handler(sig, frame):
    print('🛑 Получен сигнал завершения...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


import logging
import requests
import time
from dotenv import load_dotenv
from database import SubscriptionManager
from interface import BotInterface
from knowledge_base import PsychologyKnowledgeBase
from payment_handler import PaymentHandler
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токены
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

class DeepSeekPsychoBot:    
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        self.sub_manager = SubscriptionManager()
        self.interface = BotInterface(self.sub_manager)
        self.knowledge_base = PsychologyKnowledgeBase(self.sub_manager)
        self.payment_handler = PaymentHandler(self)
        print("🤖 Улучшенный DeepSeek Бот с библиотекой инициализирован!")

    def send_message(self, chat_id, text, reply_markup=None):
        """Отправка сообщения в Telegram"""
        print(f"🔵 DEBUG: send_message вызван с reply_markup типа: {type(reply_markup)}")
    
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        if reply_markup:
            print(f"🔵 DEBUG: reply_markup = {reply_markup}")
            data["reply_markup"] = reply_markup.to_json()          
      
        try:
            response = requests.post(url, json=data)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Ошибка отправки: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False

    def send_menu_message(self, chat_id, user_id, username="", first_name=""):
        """Отправка главного меню пользователю"""
        text, keyboard = self.interface.get_main_menu(user_id, username, first_name)
        return self.send_message(chat_id, text, keyboard)

    def edit_message(self, chat_id, message_id, text, keyboard=None):
        """Редактирование сообщения"""
        url = f"{self.base_url}/editMessageText"
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }

        if keyboard:
            data["reply_markup"] = keyboard.to_json()

        try:
            response = requests.post(url, json=data)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            return False

    def get_deepseek_response(self, user_id, user_message, book_context, chat_history=None):
        """Получение ответа от DeepSeek"""
        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }

            messages = []   

            # ОБЫЧНЫЙ ПРОМПТ
            system_prompt = """Ты - практичный психологический помощник, который ОБЯЗАТЕЛЬНО использует информацию из предоставленных психологических книг.

ИНСТРУКЦИЯ:
1. ОСНОВЫВАЙ ответ на информации из книг выше 
2. Давай ответ простым и понятным языком, человеку, который не понимает ничего в психологии
3. Не придумывай методы, которых нет в книгах
4. Цитируй конкретные техники и подходы из литературы, но не указывай конкретные источники
5. Поддержи если сильно необходимо и добавь 1 эмодзи
6. Старайся не уходить от темы, помоги до конца разобраться в ситуации
7. Если пользователь запутался или не понимает, дай подробный ответ на заданную тему, но не более 9-10 предложений
8. Если пользователь говорит, что у него получилось и ему помогло заканчивай диалог кратким советом на будущее
9. Помни контекст предыдущих сообщений
10.Продолжай диалог естественно

Формат ответа:
💭Краткий анализ на основе книг, без указания источника и без слов "Из книги"

💡Конкретная техника/совет из книг понятным языком"""

            messages.append({"role": "system", "content": system_prompt})

            if book_context and book_context.strip():
                messages.append({
                    "role": "system", 
                    "content": f"ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ИЗ ПСИХОЛОГИЧЕСКИХ КНИГ:\n{book_context}\n\nИспользуй эту информацию в ответе если она релевантна запросу пользователя."
                })
                print(f"🔵 DEBUG: Добавлен контекст из книг ({len(book_context)} символов)")

            # ДОБАВЛЯЕМ ИСТОРИЮ ДИАЛОГА
            if chat_history:
                for role, content in chat_history:
                    messages.append({"role": role, "content": content})
                    print(f"🔵 DEBUG: Добавлена история - {role}: {content[:50]}...")
                print(f"🔵 DEBUG: Всего в истории: {len(chat_history)} сообщений")

            # ДОБАВЛЯЕМ ТЕКУЩИЙ ЗАПРОС
            messages.append({"role": "user", "content": user_message})
            print(f"🔵 DEBUG: Всего сообщений в промпте: {len(messages)}")
    

            data = {                
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7,
                "stream": False        
            }

            response = requests.post(
                self.deepseek_url,
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content']

                # СОХРАНЯЕМ ОТВЕТ В ИСТОРИЮ (если есть sub_manager)
                if hasattr(self, 'sub_manager'):
                    self.sub_manager.save_message(user_id, "assistant", ai_response)
                return ai_response
            
            else:
                logger.error(f"Ошибка DeepSeek API: {response.text}")
                return "Извини, произошла ошибка при обработке запроса."
        except Exception as e:
            logger.error(f"Ошибка DeepSeek: {e}")
            return "Извини, я сейчас не могу ответить. Попробуй позже."

    def handle_callback(self, update):
        """Обработка нажатий на кнопки меню"""
        callback_query = update.get("callback_query", {})
        if not callback_query:
            return
        
        user_id = callback_query.get("from", {}).get("id")
        can_send, messages_count, daily_limit, sub_type, days_left = self.sub_manager.can_send_message(user_id, is_menu_action=True)

        message = callback_query.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_id = callback_query.get("from", {}).get("id")
        user_name = callback_query.get("from", {}).get("first_name", "Пользователь")
        data = callback_query.get("data")

        print(f"🔄 Обработка callback: {data} от {user_name}")        

        if data == "back_main":
            text, keyboard = self.interface.get_main_menu(user_id, "", user_name)
            self.edit_message(chat_id, message.get("message_id"), text, keyboard)

        elif data == "subscription":
            text, keyboard = self.interface.get_subscription_menu(user_id)
            self.edit_message(chat_id, message.get("message_id"), text, keyboard)

        elif data == "stats":
            text, keyboard = self.interface.get_stats_message(user_id)
            self.edit_message(chat_id, message.get("message_id"), text, keyboard)

        elif data == "consult_ai":
            self.edit_message(chat_id, message.get("message_id"), "💬 <b>Режим консультации</b>\n\nНапишите ваш вопрос, и я постараюсь помочь!")

        elif data == "help":
            text, keyboard = self.interface.get_help_message(user_id)
            self.edit_message(chat_id, message.get("message_id"),  text, keyboard)

        elif data == "test_payment":
            # Создаем демо-платеж который сразу активируется
            payment_id = f"test_{int(datetime.now().timestamp())}"
            
            # Сразу активируем премиум
            if self.sub_manager.add_premium_user(user_id, 30):
                self.send_message(chat_id, 
                    "🧪 <b>Тестовый платеж завершен!</b>\n\n"
                    "🎉 Premium подписка активирована на 30 дней!\n"
                    "Теперь вам доступно безлимитное общение с AI-психологом."
                )
            else:
                self.send_message(chat_id, "❌ Ошибка активации тестовой подписки")

        elif data.startswith("sub_"):
            if data == "sub_premium":
                self.edit_message(chat_id, message.get("message_id"), 
                    "💎 <b>Premium подписка</b>\n\n"
                    "Для активации Premium подписки:\n"
                    "1. Переведите 139₽ на карту \n"
                    "2. Отправьте скриншот оплаты @danilskopov\n"
                    "3. Мы активируем ваш Premium доступ в течение часа")
            else:
                self.edit_message(chat_id, message.get("message_id"), 
                    "🆓 <b>Бесплатный тариф активирован</b>\n\n"
                    "Вы можете использовать до 5 сообщений в день.\n"
                    "Для расширения лимитов рассмотрите Premium подписку.")
        
        elif data.startswith("pay_"):
            tariff_type = data.replace("pay_", "")
            
            # Создаем платеж в ЮKassa
            payment, error = self.payment_handler.create_payment(user_id, tariff_type)
            
            if payment:
                payment_url = self.payment_handler.get_payment_url(payment)
                
                if payment_url:
                    payment_text = f"""💎 <b>Оплата Premium подписки</b>

        <b>Тариф:</b> {self.payment_handler.tariff_plans[tariff_type]['name']}
        <b>Стоимость:</b> {self.payment_handler.tariff_plans[tariff_type]['price']}₽
        <b>Срок:</b> {self.payment_handler.tariff_plans[tariff_type]['days']} дней

        Для оплаты перейдите по ссылке ниже ⤵️

        После успешной оплаты подписка активируется автоматически в течение 1-2 минут.

        <code>ID платежа: {payment.id}</code>"""
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("💳 Перейти к оплате", url=payment_url)],
                        [InlineKeyboardButton("🔄 Проверить статус", callback_data=f"check_payment_{payment.id}")],
                        [InlineKeyboardButton("🔙 Назад к тарифам", callback_data="subscription")]
                    ])
                    
                    self.edit_message(chat_id, message.get("message_id"), payment_text, keyboard)
                else:
                    self.edit_message(chat_id, message.get("message_id"), 
                                    "❌ Ошибка создания ссылки для оплаты")
            else:
                self.edit_message(chat_id, message.get("message_id"), 
                                f"❌ Ошибка создания платежа: {error}")

        # Добавьте обработку проверки статуса платежа
        elif data.startswith("check_payment_"):
            payment_id = data.replace("check_payment_", "")
            
            print(f"🔍 Пользователь проверяет статус платежа: {payment_id}")
            
            # Проверяем статус (метод теперь сам активирует подписку если нужно)
            status = self.payment_handler.check_payment_status(payment_id)
            
            status_messages = {
                'pending': "⏳ Платеж ожидает оплаты\n\nПопробуйте проверить статус через 2-3 минуты",
                'waiting_for_capture': "⏳ Платеж обрабатывается банком\n\nОбычно это занимает 1-2 минуты",
                'succeeded': "✅ <b>Платеж успешно завершен!</b>\n\n🎉 Ваш Premium доступ активирован! Теперь вам доступно безлимитное общение с AI-психологом!",
                'canceled': "❌ Платеж отменен\n\nВы можете попробовать оплатить снова",
                'not_found': "❌ Платеж не найден\n\nОбратитесь в поддержку: @danilskopov",
                'error': "❌ Ошибка проверки статуса\n\nПопробуйте позже или обратитесь в поддержку"
            }
            
            message = status_messages.get(status, f"Статус: {status}")
            
            # Добавляем кнопки в зависимости от статуса
            keyboard = []
            if status in ['pending', 'waiting_for_capture']:
                keyboard.append([InlineKeyboardButton("🔄 Проверить снова", callback_data=f"check_payment_{payment_id}")])
            
            keyboard.extend([
                [InlineKeyboardButton("💎 Управление подпиской", callback_data="subscription")],
                [InlineKeyboardButton("📞 Поддержка", url="https://t.me/danil_skopov")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="back_main")]
            ])
            
            self.send_message(chat_id, message, InlineKeyboardMarkup(keyboard))    

    def process_updates(self):
        """Основной цикл обработки сообщений"""
        last_update_id = 0
        print("🔄 Начинаю опрос сервера Telegram...")
        print(f"🔑 DeepSeek API: {'✅ Настроен' if DEEPSEEK_API_KEY else '❌ Не настроен'}")
        print(f"📚 Библиотека: {self.knowledge_base.get_library_info()}")

        # Команды которые НЕ считаются за сообщения
        NON_MESSAGE_COMMANDS = [
            '/start', '/menu', '/mystatus', '/myid', '/premium', '/help',
            '/psychologists', '/mystats', '/buy_premium', '/buy_premium_annual'
        ]

        while True:
            try:
                # Получаем обновления
                url = f"{self.base_url}/getUpdates"
                params = {
                    "offset": last_update_id + 1,
                    "timeout": 25,
                    "allowed_updates": ["message", "callback_query"]
                }

                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        updates = data.get("result", [])

                        for update in updates:
                            last_update_id = update["update_id"]

                            if "message" in update:
                                message = update["message"]
                                chat_id = message["chat"]["id"]
                                user_id = message["from"]["id"]
                                text = message.get("text", "")
                                user_name = message["chat"].get("first_name", "Пользователь")
                                username = message["from"].get("username", "")

                                print(f"📨 Сообщение от {user_name} (ID: {user_id}): {text}")

                                
                                # Проверяем тип команды
                                if text in NON_MESSAGE_COMMANDS:
                                    print(f"🔵 DEBUG: Это меню команда: {text}")
                                else:
                                    print(f"🔵 DEBUG: Это реальное сообщение: {text}")

                                if text == "/start" or text == "/menu":

                                    can_send, messages_count, daily_limit, sub_type, days_left = self.sub_manager.can_send_message(user_id, is_menu_action=True)

                                    menu_text, keyboard = self.interface.get_main_menu(user_id, username, user_name)

                                    # Отправляем меню вместо простого текста
                                    success = self.send_menu_message(chat_id, user_id, username, user_name)
                                    if success:
                                        print(f"✅ Отправлено меню пользователю {user_name}")
                                    else:
                                        print(f"❌ Ошибка отправки меню пользователю {user_name}")

                                elif text and text != "/start" and text != "/menu":
                                    
                                    # СПИСОК АДМИНОВ - ДОБАВЬТЕ В НАЧАЛО ЭТОГО БЛОКА
                                    ADMIN_IDS = [0000000]  # Замените на ваш ID 309524694
                                    
                                    # Обработка админ-команд (не считаются за сообщения)
                                    if text.startswith("/admin") or text.startswith("/add_premium") or text.startswith("/remove_premium") or text.startswith("/debug") or text.startswith("/reset_counter") or text.startswith("/setup_webhook") or text.startswith("/webhook_status") or text.startswith("/payment_info"):
                                        if user_id not in ADMIN_IDS:
                                            self.send_message(chat_id, "❌ У вас нет прав админа")
                                            continue

                                        parts = text.split()
                                        command = parts[0] if parts else ""

                                        # ОБРАБОТКА АДМИН КОМАНД ДО ПРОВЕРКИ ЛИМИТОВ
                                        if command == "/admin_users":
                                            # Получаем список всех пользователей
                                            users_list = self.sub_manager.get_all_users_info()
                                            users_count = self.sub_manager.get_users_count_by_type()

                                            if not users_list:
                                                self.send_message(chat_id, "📭 В базе нет пользователей")
                                                continue

                                            # Разбиваем на части (Telegram ограничение 4096 символов)
                                            total_users = len(users_list)
                                            premium_count = users_count.get('premium', 0)
                                            free_count = users_count.get('free', 0)
                                            trial_count = users_count.get('trial', 0)

                                            header = f"""📊 <b>Список пользователей</b>

                                👥 Всего: {total_users} пользователей
                                💎 Премиум: {premium_count}
                                🆓 Пробных: {trial_count}
                                🆓 Бесплатных: {free_count}

                                """

                                            # Формируем список пользователей
                                            user_lines = []
                                            for i, user in enumerate(users_list, 1):
                                                username_display = f"@{user['username']}" if user['username'] and user['username'] != "N/A" else "без username"
                                                user_line = f"{i}. <code>{user['user_id']}</code> - {username_display} - {user['subscription_info']}"
                                                user_lines.append(user_line)

                                            # Разбиваем на сообщения по 20 пользователей в каждом
                                            chunk_size = 20
                                            total_pages = (len(user_lines) + chunk_size - 1) // chunk_size
                                            
                                            for i in range(0, len(user_lines), chunk_size):
                                                chunk = user_lines[i:i + chunk_size]
                                                current_page = (i // chunk_size) + 1
                                                
                                                # Для первого сообщения добавляем заголовок
                                                if i == 0:
                                                    message_text = header + "\n".join(chunk)
                                                else:
                                                    message_text = "\n".join(chunk)

                                                # Добавляем пагинацию если больше одной страницы
                                                if total_pages > 1:
                                                    message_text += f"\n\n📄 Страница {current_page}/{total_pages}"

                                                # Отправляем сообщение
                                                success = self.send_message(chat_id, message_text)
                                                
                                                if not success:
                                                    self.send_message(chat_id, "❌ Ошибка отправки списка пользователей")
                                                    break
                                                    
                                                # Задержка между сообщениями
                                                if i + chunk_size < len(user_lines):
                                                    time.sleep(1.5)
                                            continue  # Важно: продолжаем цикл, чтобы не проверять лимиты

                                        elif command == "/reset_counter":
                                            #Обнуление счетчика сообщений у пользователя
                                            if len(parts) < 2:
                                                self.send_message(chat_id, "❌ Использование: /reset_counter <user_id> [date=today]")
                                                continue
                                            
                                            try:
                                                target_id = int(parts[1])
                                                date = parts[2] if len(parts) > 2 else None
                                                
                                                if self.sub_manager.reset_message_count(target_id, date):
                                                    if date:
                                                        self.send_message(chat_id, f"✅ Счетчик пользователя {target_id} обнулен за {date}")
                                                    else:
                                                        self.send_message(chat_id, f"✅ Счетчик пользователя {target_id} обнулен за сегодня")
                                                else:
                                                    self.send_message(chat_id, f"❌ Ошибка обнуления счетчика пользователя {target_id}")
                                                    
                                            except ValueError:
                                                self.send_message(chat_id, "❌ Неверный формат user_id")
                                            continue

                                        elif command == "/admin_user_info":
                                            # Детальная информация о пользователе
                                            if len(parts) < 2:
                                                self.send_message(chat_id, "❌ Использование: /admin_user_info <user_id>")
                                                continue
                                            
                                            try:
                                                target_id = int(parts[1])
                                                user_info = self.sub_manager.get_detailed_user_info(target_id)
                                                self.send_message(chat_id, user_info)
                                                
                                            except ValueError:
                                                self.send_message(chat_id, "❌ Неверный формат user_id. Используйте: /admin_user_info <user_id>")
                                            except Exception as e:
                                                self.send_message(chat_id, f"❌ Ошибка при получении информации: {e}")
                                            continue  # Важно: продолжаем цикл

                                        elif command == "/add_premium":
                                            if len(parts) < 2:
                                                self.send_message(chat_id, "❌ Использование: /add_premium <user_id> [days=30]")
                                                continue
                                            
                                            try:
                                                target_id = int(parts[1])
                                                days = int(parts[2]) if len(parts) > 2 else 30
                                                
                                                # ИСПОЛЬЗУЕМ ПРАВИЛЬНЫЙ МЕТОД
                                                if self.sub_manager.add_premium_user(target_id, days):
                                                    self.send_message(chat_id, f"✅ Пользователю {target_id} добавлен премиум на {days} дней")
                                                else:
                                                    self.send_message(chat_id, f"❌ Ошибка добавления премиума пользователю {target_id}")

                                            except ValueError:
                                                self.send_message(chat_id, "❌ Неверный формат user_id или days")
                                            except Exception as e:
                                                self.send_message(chat_id, f"❌ Ошибка: {e}")
                                            continue  # Важно: продолжаем цикл

                                        elif command == "/remove_premium":
                                            if len(parts) < 2:
                                                self.send_message(chat_id, "❌ Использование: /remove_premium <user_id>")
                                                continue
                                            
                                            try:
                                                target_user_id = int(parts[1])
                                                print(f"🔵 DEBUG: Вызов remove_premium для {target_user_id}")
                                                
                                                if self.sub_manager.remove_premium(target_user_id):
                                                    self.send_message(chat_id, f"✅ Пользователь {target_user_id} исключен из премиума")
                                                else:
                                                    self.send_message(chat_id, f"❌ Ошибка исключения пользователя {target_user_id} из премиума")

                                            except ValueError:
                                                self.send_message(chat_id, "❌ Неверный формат user_id")
                                            continue  # Важно: продолжаем цикл

                                        elif command == "/force_remove_premium":
                                            if len(parts) < 2:
                                                self.send_message(chat_id, "❌ Использование: /force_remove_premium <user_id>")
                                                continue
                                            
                                            try:
                                                target_user_id = int(parts[1])
                                                
                                                # Принудительно обновляем обе таблицы напрямую
                                                cursor = self.sub_manager.conn.cursor()
                                                
                                                # 1. subscriptions
                                                cursor.execute(
                                                    "UPDATE subscriptions SET subscription_type = 'free', expiry_date = NULL WHERE user_id = ?",
                                                    (target_user_id,)
                                                )
                                                sub_updated = cursor.rowcount
                                                
                                                # 2. users
                                                cursor.execute(
                                                    "UPDATE users SET subscription_type = 'free', subscription_end = NULL WHERE user_id = ?",
                                                    (target_user_id,)
                                                )
                                                users_updated = cursor.rowcount
                                                
                                                self.sub_manager.conn.commit()
                                                
                                                self.send_message(chat_id, 
                                                    f"🔧 <b>Принудительное обновление завершено!</b>\n\n"
                                                    f"🆔 User ID: {target_user_id}\n"
                                                    f"📊 Обновлено записей: {sub_updated + users_updated}"
                                                )
                                                
                                            except ValueError:
                                                self.send_message(chat_id, "❌ Неверный формат user_id")
                                            except Exception as e:
                                                self.send_message(chat_id, f"❌ Ошибка принудительного обновления: {e}")
                                            continue  # Важно: продолжаем цикл

                                        elif command == "/payment_info":
                                            """Информация о платеже"""
                                            if len(parts) < 2:
                                                self.send_message(chat_id, "❌ Использование: /payment_info <payment_id>")
                                                continue
                                            
                                            payment_id = parts[1]
                                            
                                            try:
                                                cursor = self.sub_manager.conn.cursor()
                                                cursor.execute("""
                                                    SELECT user_id, tariff_type, status, amount, created_at, yookassa_payment_id 
                                                    FROM payments 
                                                    WHERE payment_id = ? OR yookassa_payment_id = ?
                                                """, (payment_id, payment_id))
                                                
                                                payment = cursor.fetchone()
                                                
                                                if payment:
                                                    user_id, tariff_type, status, amount, created_at, yookassa_id = payment
                                                    text = f"""💳 <b>Информация о платеже</b>

                                        🆔 <b>Payment ID:</b> <code>{payment_id}</code>
                                        👤 <b>User ID:</b> <code>{user_id}</code>
                                        💎 <b>Тариф:</b> {tariff_type}
                                        💰 <b>Сумма:</b> {amount}₽
                                        📊 <b>Статус:</b> {status}
                                        🕒 <b>Создан:</b> {created_at}
                                        🔗 <b>ЮKassa ID:</b> {yookassa_id or 'N/A'}"""
                                                else:
                                                    text = f"❌ Платеж {payment_id} не найден"
                                                
                                                self.send_message(chat_id, text)
                                                
                                            except Exception as e:
                                                self.send_message(chat_id, f"❌ Ошибка: {e}")

                                        elif command == "/setup_webhook":
                                            if user_id not in ADMIN_IDS:
                                                self.send_message(chat_id, "❌ У вас нет прав админа")
                                                continue
                                            
                                            self.send_message(chat_id, "🔧 Настраиваю вебхуки в ЮKassa...")
                                            success = self.payment_handler.setup_webhook()
                                            if success:
                                                self.send_message(chat_id, 
                                                    "✅ Вебхуки успешно настроены!\n\n"
                                                    "🔗 URL: https://yookassa-webhook-gstx.onrender.com/webhook/yookassa\n"
                                                    "🎯 Событие: payment.succeeded\n\n"
                                                    "Теперь оплаты будут активироваться автоматически!"
                                                )
                                            else:
                                                self.send_message(chat_id, 
                                                    "❌ Ошибка настройки вебхуков\n\n"
                                                    "Проверьте:\n"
                                                    "1. Ключи API ЮKassa в .env\n"
                                                    "2. Что сервер доступен по ссылке\n"
                                                    "3. Логи для деталей ошибки"
                                                )
                                            continue

                                        elif command == "/webhook_status":
                                            if user_id not in ADMIN_IDS:
                                                self.send_message(chat_id, "❌ У вас нет прав админа")
                                                continue
                                            
                                            # Проверяем статус вебхук-сервера
                                            try:
                                                # Используем тот же requests что и в других методах
                                                response = requests.get("https://yookassa-webhook-gstx.onrender.com/health", timeout=10)
                                                if response.status_code == 200:
                                                    data = response.json()
                                                    status = "✅ Активен"
                                                    additional_info = f"Время: {data.get('timestamp', 'N/A')}"
                                                else:
                                                    status = "❌ Ошибка"
                                                    additional_info = f"Код: {response.status_code}"
                                                
                                                self.send_message(chat_id, 
                                                    f"🌐 Статус вебхук-сервера: {status}\n"
                                                    f"🔗 URL: https://yookassa-webhook-gstx.onrender.com/webhook/yookassa\n"
                                                    f"📊 {additional_info}"
                                                )
                                            except Exception as e:
                                                self.send_message(chat_id, f"❌ Ошибка проверки статуса: {e}")
                                            continue

                                        elif command == "/debug_user":
                                            if len(parts) < 2:
                                                self.send_message(chat_id, "❌ Использование: /debug_user <user_id>")
                                                continue
                                            
                                            try:
                                                target_id = int(parts[1])
                                                cursor = self.sub_manager.conn.cursor()
                                                
                                                # Проверяем subscriptions
                                                cursor.execute("SELECT subscription_type, expiry_date FROM subscriptions WHERE user_id = ?", (target_id,))
                                                sub_data = cursor.fetchone()
                                                
                                                # Проверяем users
                                                cursor.execute("SELECT subscription_type, subscription_end, username, first_name FROM users WHERE user_id = ?", (target_id,))
                                                user_data = cursor.fetchone()
                                                
                                                # Проверяем message_stats за сегодня
                                                cursor.execute("SELECT message_count FROM message_stats WHERE user_id = ? AND date = date('now')", (target_id,))
                                                stats_data = cursor.fetchone()
                                                
                                                debug_text = f"""🔍 <b>Отладка пользователя {target_id}</b>

                                📋 <b>Таблица subscriptions:</b>
                                Тип: {sub_data[0] if sub_data else 'N/A'}
                                Истекает: {sub_data[1] if sub_data else 'N/A'}

                                👤 <b>Таблица users:</b>
                                Тип: {user_data[0] if user_data else 'N/A'}
                                Истекает: {user_data[1] if user_data else 'N/A'}
                                Username: {user_data[2] if user_data else 'N/A'}
                                Имя: {user_data[3] if user_data else 'N/A'}

                                📊 <b>Статистика за сегодня:</b>
                                Сообщений: {stats_data[0] if stats_data else '0'}"""

                                                self.send_message(chat_id, debug_text)
                                                
                                            except ValueError:
                                                self.send_message(chat_id, "❌ Неверный формат user_id")
                                            except Exception as e:
                                                self.send_message(chat_id, f"❌ Ошибка отладки: {e}")
                                            continue  # Важно: продолжаем цикл

                                    # ТЕПЕРЬ ПРОВЕРЯЕМ ЛИМИТЫ ТОЛЬКО ДЛЯ ОБЫЧНЫХ СООБЩЕНИЙ
                                    # Проверяем является ли команда "меню действием"
                                    is_menu_action = (text in NON_MESSAGE_COMMANDS or 
                                                    text.startswith('/debug') or 
                                                    text.startswith('/sync') or 
                                                    text.startswith('/check') or 
                                                    text.startswith('/find_user'))

                                    # Проверяем лимиты подписки (передаем флаг is_menu_action)
                                    can_send, messages_count, daily_limit, sub_type, days_left = self.sub_manager.can_send_message(user_id, is_menu_action)

                                    # Кризисные ситуации обрабатываем всегда
                                    crisis_words = ['суицид', 'самоубийство', 'умру', 'покончить с собой', 'надоело жить']
                                    if any(word in text.lower() for word in crisis_words):
                                        crisis_text = """🚨 <b>Мне очень важно, чтобы ты был в безопасности!</b>

    Пожалуйста, немедленно свяжись со специалистами:

    📞 <b>Телефон доверия</b>: 8-800-2000-122 (круглосуточно, бесплатно)
    🏥 <b>Экстренная помощь</b>: 112 или 103

    <b>Ты не один, помощь всегда рядом!</b>"""
                                        self.send_message(chat_id, crisis_text)
                                        print(f"🚨 Кризисное сообщение от {user_name}")
                                        continue
                                                                        
                                    # Обработка обычных команд (не считаются за сообщения)
                                    elif text in NON_MESSAGE_COMMANDS:
                                        
                                        can_send, messages_count, daily_limit, sub_type, days_left = self.sub_manager.can_send_message(user_id, is_menu_action=True)

                                        if text == "/mystatus":
                                            text, keyboard = self.interface.get_stats_message(user_id)
                                            self.send_message(chat_id, text, keyboard)                                           
                                            
                                        elif text == "/premium":
                                            text, keyboard = self.interface.get_subscription_menu(user_id)
                                            self.send_message(chat_id, text, keyboard)

                                        elif text == "/help":
                                            text, keyboard = self.interface.get_help_message(user_id)
                                            self.send_message(chat_id, text, keyboard)

                                        elif text == "/myid":
                                            user_info = f"""📋 <b>Ваши данные:</b>

    🆔 <b>User ID:</b> <code>{user_id}</code>
    👤 <b>Имя:</b> {user_name}
    🔗 <b>Username:</b> @{username if username else 'не установлен'}

    💡 <b>Ваш User ID может понадобиться:</b>
    • Для активации Premium подписки
    • При обращении в техническую поддержку
    • Для идентификации в системе

    <b>Сохраните ваш User ID!</b> 📝"""
                
                                            self.send_message(chat_id, user_info)

                                        elif text == "/buy_premium":
                                            tariff_info = self.sub_manager.get_user_tariff_info(user_id)
                                            
                                            if tariff_info['sub_type'].startswith('premium'):
                                                self.send_message(chat_id, "✅ У вас уже активирован премиум тариф!")
                                            else:
                                                payment_text = f"""💎 <b>Оформление Premium подписки</b>

    Тариф: {self.sub_manager.tariff_plans['premium']['name']}
    Стоимость: {self.sub_manager.tariff_plans['premium']['price']}₽
    Срок: {self.sub_manager.tariff_plans['premium']['duration_days']} дней

    <b>Способы оплаты:</b>
    1. 💳 Карта: 2200 1234 5678 9010
    2. 📱 ЮMoney: 4100 1234 5678 9010
    3. 🤝 Crypto: BTC, USDT

    После оплаты отправьте скриншот @danilskopov
    Активация в течение 1 часа ⏱️"""
                                                
                                                self.send_message(chat_id, payment_text)

                                        elif text == "/buy_premium_annual":
                                            tariff_info = self.sub_manager.get_user_tariff_info(user_id)
                                            
                                            if tariff_info['sub_type'] == 'premium_annual':
                                                self.send_message(chat_id, "✅ У вас уже активирован годовой премиум!")
                                            else:
                                                payment_text = f"""💎 <b>Оформление Годовой Premium подписки</b>

    Тариф: {self.sub_manager.tariff_plans['premium_annual']['name']}
    Стоимость: {self.sub_manager.tariff_plans['premium_annual']['price']}₽
    Срок: {self.sub_manager.tariff_plans['premium_annual']['duration_days']} дней
    Экономия: 20% 💰

    <b>Способы оплата:</b>
    1. 💳 Карта: 2200 1234 5678 9010
    2. 📱 ЮMoney: 4100 1234 5678 9010
    3. 🤝 Crypto: BTC, USDT

    После оплаты отправьте скриншот @danilskopov
    Активация в течение 1 часа ⏱️"""
                                                
                                                self.send_message(chat_id, payment_text)

                                        elif text == "/psychologists":
                                            psychologists = self.sub_manager.get_available_psychologists(user_id)
                                            
                                            if psychologists is None:
                                                self.send_message(chat_id, "❌ Выбор психолога доступен только для премиум пользователей\n\nИспользуйте /premium чтобы узнать больше")
                                            else:
                                                psych_text = "🤝 <b>Доступные психологи</b>\n\n"
                                                for psych in psychologists:
                                                    psych_text += f"<b>{psych['name']}</b>\n"
                                                    psych_text += f"Специализация: {psych['specialization']}\n"
                                                    psych_text += f"Опыт: {psych['experience']}\n\n"
                                                
                                                psych_text += "💡 <b>Чтобы выбрать психолога:</b>\nНапишите 'Хочу психолога [имя]' в чат"
                                                self.send_message(chat_id, psych_text)

                                        elif text == "/mystats":
                                            stats = self.sub_manager.get_detailed_stats(user_id)
                                            
                                            if 'error' in stats:
                                                self.send_message(chat_id, f"❌ {stats['error']}")
                                            else:
                                                stats_text = f"""📊 <b>Ваша статистика</b>

    💬 Всего сообщений: {stats['total_messages']}
    📈 Активных дней: {len(stats['daily_activity'])}
    🔥 Использовано премиум-функций: {stats['premium_features_used']}

    <b>Последняя активность:</b>"""
                                                
                                                for day in stats['daily_activity'][:5]:  # Последние 5 дней
                                                    stats_text += f"\n• {day['date']}: {day['message_count']} сообщ."
                                                
                                                self.send_message(chat_id, stats_text)

                                        continue

                                    # Проверяем лимит для реальных сообщений
                                    if not can_send and not is_menu_action:
                                        limit_text = f"""❌ <b>Лимит сообщений исчерпан</b>

    Вы использовали {messages_count-1}/{daily_limit} сообщений сегодня.

    💎 Перейдите на Premium подписку для безлимитного общения!"""
                                        self.send_message(chat_id, limit_text)
                                        print(f"📊 Лимит исчерпан для {user_name}")
                                    else:
                                        # Обработка реальных сообщений пользователя (считаются за сообщения)
                                        if not is_menu_action:
                                            # Показываем действие "печатает"
                                            requests.post(
                                                f"{self.base_url}/sendChatAction",
                                                data={"chat_id": chat_id, "action": "typing"}
                                            )

                                            chat_history = self.sub_manager.get_chat_history(user_id, limit=4)
                                            print(f"🔵 DEBUG: История диалога - {len(chat_history)} сообщений")

                                            # Получаем контекст из книг
                                            book_context = self.knowledge_base.get_context_for_ai(text)

                                            # СОХРАНЯЕМ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ В ИСТОРИЮ (только реальные сообщения)
                                            self.sub_manager.save_message(user_id, "user", text)

                                            # Генерируем ответ DeepSeek
                                            print(f"🤖 Генерирую ответ с анализом книг для {user_name}...")                                      
                                            deepseek_response = self.get_deepseek_response(user_id, text, book_context, chat_history)

                                            # СОЗДАЕМ ОДНО СООБЩЕНИЕ
                                            final_response = f"{deepseek_response}"

                                            # Добавляем информацию о лимитах для бесплатных пользователей
                                            if sub_type != 'premium':
                                                final_response += f"\n\n---\n📊 <i>Сообщений сегодня: {messages_count}/{daily_limit}</i>"

                                            # ОТПРАВЛЯЕМ ОДНО СООБЩЕНИЕ
                                            self.send_message(chat_id, final_response)
                                            print(f"✅ Ответ отправлен пользователю {user_name} ({messages_count}/{daily_limit})")

                            elif "callback_query" in update:
                                # Обработка нажатий на кнопки меню (НЕ считаются за сообщения)
                                self.handle_callback(update)

                # Небольшая пауза между запросами
                time.sleep(1)

            except KeyboardInterrupt:
                print("\n\n🛑 Бот остановлен пользователем")
                break
            except requests.exceptions.Timeout:
                # Таймаут - это нормально, продолжаем работу
                continue
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                print(f"⚠️  Ошибка: {e}. Продолжаю работу...")
                time.sleep(5)

              

def main():
    # Проверяем токены
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "ваш_telegram_токен":
        print("❌ ОШИБКА: Замени TELEGRAM_TOKEN в файле .env на реальный токен!")
        return

    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "ваш_новый_ключ_deepseek":
        print("❌ ОШИБКА: Замени DEEPSEEK_API_KEY в файле .env на реальный ключ!")
        return

    print("=" * 50)
    print("🤖 DEEPSEEK ПСИХОЛОГИЧЕСКИЙ БОТ ЗАПУЩЕН")
    print("=" * 50)
    print("✅ Токены проверены")
    print("✅ DeepSeek API настроен")
    print("🚀 Запускаю бота...")
    print("=" * 50)

    # Бесконечный цикл с перезапуском при ошибках
    restart_count = 0
    while restart_count < 10:
        try:
            bot = DeepSeekPsychoBot()
            bot.process_updates()
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен пользователем")
            break
        except Exception as e:
            restart_count += 1
            print(f"❌ Критическая ошибка (перезапуск #{restart_count}): {e}")
            print("🔄 Перезапуск через 10 секунд...")
            time.sleep(10)

    print("🔴 Бот остановлен")

if __name__ == '__main__':    
    main()