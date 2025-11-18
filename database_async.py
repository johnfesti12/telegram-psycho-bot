import asyncpg
import asyncio
from datetime import datetime, timedelta
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)

class AsyncSubscriptionManager:
    def __init__(self, db_url=None):
        self.db_url = db_url or DATABASE_URL
        self.pool = None
        print("✅ Async Database manager initialized (PostgreSQL)")

    async def init_pool(self):
        """Инициализация пула соединений PostgreSQL"""
        try:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            await self.create_tables()
            print("✅ PostgreSQL pool initialized and tables created")
        except Exception as e:
            print(f"❌ PostgreSQL connection error: {e}")
            raise

    async def create_tables(self):
        """Создание таблиц в PostgreSQL"""
        async with self.pool.acquire() as conn:
            # Таблица подписок (ОСНОВНАЯ)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id BIGINT PRIMARY KEY,
                    subscription_type TEXT NOT NULL DEFAULT 'free',
                    expiry_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Таблица для истории диалога
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Таблица для статистики сообщений
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS message_stats (
                    user_id BIGINT,
                    date TEXT,
                    message_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
            ''')
            
            # Таблица для платежей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    payment_id TEXT UNIQUE,
                    yookassa_payment_id TEXT,
                    tariff_type TEXT,
                    amount REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP
                )
            ''')
            
            # Таблица users (для совместимости)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    subscription_type TEXT DEFAULT 'free',
                    subscription_end TIMESTAMP,
                    messages_today INTEGER DEFAULT 0,
                    last_message_date DATE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            print("✅ Все таблицы PostgreSQL созданы")

    async def can_send_message(self, user_id, is_menu_action=None):
        """Асинхронная проверка может ли пользователь отправить сообщение"""
        print(f"🔵 ASYNC can_send_message вызван: user_id={user_id}")

        # АДМИНЫ ВСЕГДА МОГУТ ОТПРАВЛЯТЬ СООБЩЕНИЯ
        ADMIN_IDS = [309524694]
        if user_id in ADMIN_IDS:
            print(f"🔵 ASYNC DEBUG: Админ {user_id} - безлимитный доступ")
            return True, 0, float('inf'), 'premium', 365
        
        try:
            async with self.pool.acquire() as conn:
                # 1. Получаем информацию о подписке
                result = await conn.fetchrow(
                    "SELECT subscription_type, expiry_date FROM subscriptions WHERE user_id = $1", 
                    user_id
                )
                
                if result:
                    sub_type = result['subscription_type']
                    expiry_date = result['expiry_date']
                    # Проверяем не истекла ли подписка                
                    if expiry_date and datetime.now() > expiry_date:
                        print(f"🔵 ASYNC DEBUG: Подписка истекла! Понижаем до free")
                        sub_type = 'free'
                        await conn.execute(
                            "UPDATE subscriptions SET subscription_type = 'free' WHERE user_id = $1",
                            user_id
                        )
                else:
                    print(f"🔵 ASYNC DEBUG: Подписка не найдена! Создаем free запись")
                    sub_type = 'free'
                    await conn.execute(
                        "INSERT INTO subscriptions (user_id, subscription_type) VALUES ($1, 'free')",
                        user_id
                    )
                
                # 2. Получаем тарифный план           
                daily_limit = 5 if sub_type != 'premium' else float('inf')
                
                # 3. Получаем статистику сообщений за сегодня
                today = datetime.now().strftime('%Y-%m-%d')
                result = await conn.fetchrow(
                    "SELECT message_count FROM message_stats WHERE user_id = $1 AND date = $2", 
                    user_id, today
                )
                messages_today = result['message_count'] if result else 0
                
                print(f"🔵 ASYNC DEBUG: подписка: {sub_type}, сообщений сегодня: {messages_today}, лимит: {daily_limit}")
                
                # 4. ЕСЛИ ЭТО МЕНЮ ДЕЙСТВИЕ - НЕ УВЕЛИЧИВАЕМ СЧЕТЧИК
                if is_menu_action:
                    print(f"🔵 ASYNC DEBUG: Меню действие - не увеличиваем счетчик")
                    can_send = True
                    messages_display = messages_today
                else:
                    # РЕАЛЬНОЕ СООБЩЕНИЕ - проверяем лимит и увеличиваем счетчик
                    can_send = messages_today < daily_limit if daily_limit != float('inf') else True
                    
                    if can_send:
                        # Увеличиваем счетчик только для реальных сообщений
                        if result:
                            await conn.execute(
                                "UPDATE message_stats SET message_count = message_count + 1 WHERE user_id = $1 AND date = $2",
                                user_id, today
                            )
                        else:
                            await conn.execute(
                                "INSERT INTO message_stats (user_id, date, message_count) VALUES ($1, $2, 1)",
                                user_id, today
                            )
                        messages_display = messages_today + 1
                        print(f"🔵 ASYNC DEBUG: Реальное сообщение - увеличили счетчик до {messages_display}")
                    else:
                        messages_display = messages_today
                        print(f"🔵 ASYNC DEBUG: Лимит исчерпан - {messages_today}/{daily_limit}")
                
                # 5. Вычисляем оставшиеся дни
                days_left = 0
                if sub_type == 'premium' and expiry_date:
                    days_left = max(0, (expiry_date - datetime.now()).days)
                
                print(f"🔵 ASYNC DEBUG: Итог - можно отправить: {can_send}, показываем: {messages_display}/{daily_limit}")
                
                return can_send, messages_display, daily_limit, sub_type, days_left
                
        except Exception as e:
            print(f"❌ ASYNC Ошибка в can_send_message: {e}")
            import traceback
            print(f"❌ ASYNC Подробности: {traceback.format_exc()}")
            return True, 0, float('inf'), 'premium', 365

    async def save_message(self, user_id, role, content):
        """Сохранить сообщение в историю"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO chat_history (user_id, role, content) VALUES ($1, $2, $3)",
                    user_id, role, content
                )
                return True
        except Exception as e:
            print(f"❌ ASYNC Ошибка сохранения истории: {e}")
            return False

    async def get_chat_history(self, user_id, limit=6):
        """Получить историю диалога"""
        try:
            async with self.pool.acquire() as conn:
                history = await conn.fetch(
                    "SELECT role, content FROM chat_history WHERE user_id = $1 ORDER BY timestamp DESC LIMIT $2",
                    user_id, limit
                )
                # Возвращаем в правильном порядке
                return list(reversed(history))
        except Exception as e:
            print(f"❌ ASYNC Ошибка получения истории: {e}")
            return []

    async def clear_chat_history(self, user_id):
        """Очистить историю диалога"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_history WHERE user_id = $1", user_id)
                return True
        except Exception as e:
            print(f"❌ ASYNC Ошибка очистки истории: {e}")
            return False

    async def add_premium_user(self, user_id, days=30):
        """Добавить или обновить пользователя в премиум"""
        try:
            async with self.pool.acquire() as conn:
                expiry_date = datetime.now() + timedelta(days=days)
                
                # ПРОВЕРЯЕМ СУЩЕСТВУЕТ ЛИ ПОЛЬЗОВАТЕЛЬ
                existing_user = await conn.fetchrow(
                    "SELECT user_id FROM subscriptions WHERE user_id = $1", user_id
                )
                
                if existing_user:
                    # ОБНОВЛЯЕМ существующую запись
                    await conn.execute(
                        "UPDATE subscriptions SET subscription_type = $1, expiry_date = $2 WHERE user_id = $3",
                        'premium', expiry_date, user_id
                    )
                    print(f"✅ ASYNC Обновлен премиум для пользователя {user_id} на {days} дней")
                else:
                    # СОЗДАЕМ новую запись
                    await conn.execute(
                        "INSERT INTO subscriptions (user_id, subscription_type, expiry_date) VALUES ($1, $2, $3)",
                        user_id, 'premium', expiry_date
                    )
                    print(f"✅ ASYNC Создан премиум для пользователя {user_id} на {days} дней")
                
                # Также обновляем таблицу users для совместимости
                existing_in_users = await conn.fetchrow(
                    "SELECT user_id FROM users WHERE user_id = $1", user_id
                )
                
                if existing_in_users:
                    await conn.execute(
                        "UPDATE users SET subscription_type = $1, subscription_end = $2 WHERE user_id = $3",
                        'premium', expiry_date, user_id
                    )
                else:
                    await conn.execute(
                        "INSERT INTO users (user_id, subscription_type, subscription_end) VALUES ($1, $2, $3)",
                        user_id, 'premium', expiry_date
                    )
                
                print(f"✅ ASYNC Пользователь {user_id} установлен в premium на {days} дней")
                return True
                
        except Exception as e:
            print(f"❌ ASYNC Ошибка установки premium: {e}")
            import traceback
            print(f"🔍 ASYNC Детали: {traceback.format_exc()}")
            return False

    async def remove_premium(self, user_id):
        """Исключить пользователя из премиума"""
        try:
            async with self.pool.acquire() as conn:
                print(f"🔵 ASYNC DEBUG: Удаляем премиум у пользователя {user_id}")
                
                # ОБНОВЛЯЕМ ОБЕ ТАБЛИЦЫ
                await conn.execute(
                    "UPDATE subscriptions SET subscription_type = 'free', expiry_date = NULL WHERE user_id = $1",
                    user_id
                )
                
                await conn.execute(
                    "UPDATE users SET subscription_type = 'free', subscription_end = NULL WHERE user_id = $1",
                    user_id
                )
                
                print(f"✅ ASYNC Пользователь {user_id} исключен из премиума")
                return True
                
        except Exception as e:
            print(f"❌ ASYNC Ошибка исключения из премиума: {e}")
            return False

    async def get_all_users_info(self):
        """Получить информацию о всех пользователях"""
        try:
            async with self.pool.acquire() as conn:
                users = await conn.fetch('''
                    SELECT 
                        s.user_id, 
                        u.username,
                        s.subscription_type,
                        s.expiry_date
                    FROM subscriptions s
                    LEFT JOIN users u ON s.user_id = u.user_id
                    ORDER BY 
                        CASE 
                            WHEN s.subscription_type = 'premium' THEN 1
                            WHEN s.subscription_type = 'trial' THEN 2
                            ELSE 3
                        END,
                        s.user_id
                ''')

                result = []
                for user in users:
                    user_id, username, sub_type, expiry_date = user['user_id'], user['username'], user['subscription_type'], user['expiry_date']

                    # Формируем информацию о подписке
                    if sub_type == 'premium':
                        if expiry_date:
                            days_left = max(0, (expiry_date - datetime.now()).days)
                            sub_info = f"💎 Premium ({days_left}д)"
                        else:
                            sub_info = "💎 Premium (∞)"
                    
                    elif sub_type == 'trial':
                        if expiry_date:
                            days_left = max(0, (expiry_date - datetime.now()).days)
                            sub_info = f"🆓 Trial ({days_left}д)"
                        else:
                            sub_info = "🆓 Trial"
                    
                    else:  # free
                        # Для free пользователей получаем статистику сообщений
                        today = datetime.now().strftime('%Y-%m-%d')
                        stats_result = await conn.fetchrow(
                            "SELECT message_count FROM message_stats WHERE user_id = $1 AND date = $2", 
                            user_id, today
                        )
                        messages_today = stats_result['message_count'] if stats_result else 0
                        remaining_messages = max(0, 5 - messages_today)
                        sub_info = f"🆓 Free ({remaining_messages} ост.)"

                    result.append({
                        'user_id': user_id,
                        'username': username or "N/A",
                        'subscription_info': sub_info
                    })

                return result

        except Exception as e:
            print(f"❌ ASYNC Ошибка получения списка пользователей: {e}")
            return []

    async def get_detailed_user_info(self, user_id):
        """Получить детальную информацию о пользователе для админа"""
        try:
            async with self.pool.acquire() as conn:
                # Получаем основную информацию из subscriptions
                user_data = await conn.fetchrow('''
                    SELECT 
                        s.subscription_type,
                        s.expiry_date,
                        u.username, 
                        u.first_name,
                        u.created_at,
                        u.messages_today,
                        u.last_message_date
                    FROM subscriptions s
                    LEFT JOIN users u ON s.user_id = u.user_id
                    WHERE s.user_id = $1
                ''', user_id)

                if not user_data:
                    return "❌ Пользователь не найден"

                sub_type, expiry_date, username, first_name, created_at, messages_today, last_message_date = user_data

                # Получаем статистику сообщений за сегодня
                today = datetime.now().strftime('%Y-%m-%d')
                stats_result = await conn.fetchrow(
                    "SELECT message_count FROM message_stats WHERE user_id = $1 AND date = $2", 
                    user_id, today
                )
                messages_today_count = stats_result['message_count'] if stats_result else 0

                # Получаем общее количество сообщений
                total_messages_result = await conn.fetchrow(
                    "SELECT COUNT(*) FROM chat_history WHERE user_id = $1", user_id
                )
                total_messages = total_messages_result['count'] if total_messages_result else 0

                # Получаем количество активных дней
                active_days_result = await conn.fetchrow(
                    "SELECT COUNT(DISTINCT date) FROM message_stats WHERE user_id = $1", user_id
                )
                active_days = active_days_result['count'] if active_days_result else 0

                # Форматируем информацию о подписке
                if sub_type == 'premium':
                    if expiry_date:
                        days_left = max(0, (expiry_date - datetime.now()).days)
                        sub_info = f"💎 Premium (осталось {days_left} дней)"
                    else:
                        sub_info = "💎 Premium (бессрочно)"
                elif sub_type == 'trial':
                    if expiry_date:
                        days_left = max(0, (expiry_date - datetime.now()).days)
                        sub_info = f"🆓 Trial (осталось {days_left} дней)"
                    else:
                        sub_info = "🆓 Trial"
                else:
                    remaining_messages = max(0, 5 - messages_today_count)
                    sub_info = f"🆓 Free ({remaining_messages} сообщений осталось)"

                # Безопасное форматирование дат
                def safe_date_format(date_value, default="N/A"):
                    if not date_value:
                        return default
                    try:
                        return date_value.strftime('%d.%m.%Y %H:%M')
                    except:
                        return str(date_value)

                def safe_date_only(date_value, default="N/A"):
                    if not date_value:
                        return default
                    try:
                        return date_value.strftime('%d.%m.%Y')
                    except:
                        return str(date_value)

                created_str = safe_date_format(created_at, "Неизвестно")
                last_active = safe_date_only(last_message_date, "Никогда")
                sub_end_str = safe_date_only(expiry_date, "Не ограничено")

                # Собираем информацию
                info_text = f"""
👤 <b>Детальная информация о пользователе</b>

🆔 <b>User ID:</b> <code>{user_id}</code>
👤 <b>Имя:</b> {first_name or 'Не указано'}
🔗 <b>Username:</b> @{username or 'не установлен'}

💎 <b>Подписка:</b> {sub_info}
📅 <b>Истекает:</b> {sub_end_str}

📊 <b>Статистика сообщений:</b>
• Сегодня: {messages_today_count}/5
• Всего: {total_messages} сообщений
• Активных дней: {active_days}

📅 <b>Дата регистрации:</b> {created_str}
🕒 <b>Последняя активность:</b> {last_active}
                """
                return info_text

        except Exception as e:
            print(f"❌ ASYNC Ошибка получения информации о пользователе: {e}")
            return f"❌ Ошибка получения информации: {e}"

    async def get_users_count_by_type(self):
        """Получить количество пользователей по типам подписки"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetch('''
                    SELECT 
                        subscription_type,
                        COUNT(*) as count
                    FROM subscriptions 
                    GROUP BY subscription_type
                ''')

                # Инициализируем все возможные типы
                counts = {
                    'premium': 0,
                    'trial': 0, 
                    'free': 0
                }
                
                # Обновляем реальными значениями из БД
                for row in result:
                    sub_type = row['subscription_type']
                    if sub_type in counts:
                        counts[sub_type] = row['count']

                return counts

        except Exception as e:
            print(f"❌ ASYNC Ошибка получения статистики: {e}")
            return {'premium': 0, 'trial': 0, 'free': 0}

    async def reset_message_count(self, user_id, date=None):
        """Обнулить счетчик сообщений пользователя"""
        try:
            async with self.pool.acquire() as conn:
                if date is None:
                    date = datetime.now().strftime('%Y-%m-%d')
                
                await conn.execute(
                    "DELETE FROM message_stats WHERE user_id = $1 AND date = $2",
                    user_id, date
                )
                
                # Также обнуляем в таблице users
                await conn.execute(
                    "UPDATE users SET messages_today = 0, last_message_date = $1 WHERE user_id = $2",
                    date, user_id
                )
                
                print(f"✅ ASYNC Счетчик сообщений пользователя {user_id} обнулен за {date}")
                return True
                
        except Exception as e:
            print(f"❌ ASYNC Ошибка обнуления счетчика: {e}")
            return False

    async def get_or_create_user(self, user_id, username="", first_name=""):
        """Создать или обновить пользователя в таблице users"""
        try:
            async with self.pool.acquire() as conn:
                # Проверяем существование пользователя
                user = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
                
                if not user:
                    # Новый пользователь - создаем запись
                    await conn.execute('''
                        INSERT INTO users (user_id, username, first_name, subscription_type)
                        VALUES ($1, $2, $3, 'free')
                    ''', user_id, username, first_name)
                    
                    # Также создаем запись в subscriptions для совместимости
                    await conn.execute('''
                        INSERT INTO subscriptions (user_id, subscription_type)
                        VALUES ($1, 'free')
                    ''', user_id)
                    
                    print(f"✅ ASYNC Создан новый пользователь: {user_id}")
                    return True
                else:
                    # Обновляем username если изменился
                    if username or first_name:
                        await conn.execute('''
                            UPDATE users SET username = $1, first_name = $2 WHERE user_id = $3
                        ''', username, first_name, user_id)
                        print(f"✅ ASYNC Обновлен пользователь: {user_id}")
                    return True
                    
        except Exception as e:
            print(f"❌ ASYNC Ошибка создания/обновления пользователя: {e}")
            return False

    async def save_payment(self, user_id, payment_id, yookassa_payment_id, tariff_type, amount, status):
        """Сохранение информации о платеже"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO payments (user_id, payment_id, yookassa_payment_id, tariff_type, amount, status)
                    VALUES ($1, $2, $3, $4, $5, $6)
                ''', user_id, payment_id, yookassa_payment_id, tariff_type, amount, status)
                return True
        except Exception as e:
            print(f"❌ Ошибка сохранения платежа: {e}")
            return False

    async def update_payment_status(self, payment_id, status):
        """Обновление статуса платежа"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    UPDATE payments SET status = $1, updated_at = NOW() 
                    WHERE payment_id = $2 OR yookassa_payment_id = $2
                ''', status, payment_id)
                return True
        except Exception as e:
            print(f"❌ Ошибка обновления статуса платежа: {e}")
            return False

    async def get_payment_by_id(self, payment_id):
        """Получение информации о платеже"""
        try:
            async with self.pool.acquire() as conn:
                payment = await conn.fetchrow('''
                    SELECT * FROM payments 
                    WHERE payment_id = $1 OR yookassa_payment_id = $1
                ''', payment_id)
                return dict(payment) if payment else None
        except Exception as e:
            print(f"❌ Ошибка получения платежа: {e}")
            return None

# Глобальный экземпляр асинхронной БД
async_db = AsyncSubscriptionManager()