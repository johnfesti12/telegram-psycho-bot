import sqlite3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SubscriptionManager:
    def __init__(self, db_path='psychology_bot.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)  # Добавь эту строку!
        self.create_tables()
        print("✅ Database manager initialized")

    def create_tables(self):
        """Создание таблиц если их нет"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                subscription_type TEXT NOT NULL DEFAULT 'free',
                expiry_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ТАБЛИЦА ДЛЯ ИСТОРИИ ДИАЛОГА
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # ТАБЛИЦА ДЛЯ СТАТИСТИКИ СООБЩЕНИЙ
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_stats (
            user_id INTEGER,
            date TEXT,
            message_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
        ''')
        
        # ОБНОВЛЕННАЯ ТАБЛИЦА ДЛЯ ПЛАТЕЖЕЙ
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            payment_id TEXT UNIQUE,
            yookassa_payment_id TEXT,
            tariff_type TEXT,
            amount REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES subscriptions(user_id)
        )
        ''')
        
        # ТАБЛИЦА USERS (для совместимости)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            subscription_type TEXT DEFAULT 'free',
            subscription_end DATETIME,
            messages_today INTEGER DEFAULT 0,
            last_message_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.conn.commit()
        print("✅ Все таблицы базы данных созданы/проверены")
    
    def init_database(self):
        """Инициализация базы данных подписок"""
        conn = sqlite3.connect('psychology_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_type TEXT DEFAULT 'trial',
                subscription_end DATETIME,
                messages_today INTEGER DEFAULT 0,
                last_message_date DATE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ База данных подписок инициализирована")
    
    def get_user_status(self, user_id, username="", first_name=""):
        """Получение статуса пользователя"""
        conn = sqlite3.connect('psychology_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            # Новый пользователь - пробный период 7 дней
            trial_end = datetime.now() + timedelta(days=7)
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, subscription_type, subscription_end)
                VALUES (?, ?, ?, 'trial', ?)
            ''', (user_id, username, first_name, trial_end))
            conn.commit()
            conn.close()
            return 'trial', trial_end, 0, 7
        
        conn.close()
        
        sub_type = user[3]
        sub_end = datetime.fromisoformat(user[4]) if user[4] else None
        messages_today = user[5] or 0
        
        # Проверяем не истекла ли подписка
        if sub_end and datetime.now() > sub_end:
            sub_type = 'free'
            days_left = 0
        else:
            days_left = (sub_end - datetime.now()).days if sub_end else 0
        
        return sub_type, sub_end, messages_today, days_left
    
    def can_send_message(self, user_id, is_menu_action=None):
        """Упрощенная проверка может ли пользователь отправить сообщение"""
    
        import traceback
        print(f"🔵 DEBUG can_send_message вызван:")
        print(f"   user_id={user_id}, is_menu_action={is_menu_action}")
        print(f"   Вызвано из:")
        for line in traceback.format_stack()[-3:-1]:
            print(f"   {line.strip()}")
        
        # АДМИНЫ ВСЕГДА МОГУТ ОТПРАВЛЯТЬ СООБЩЕНИЯ
        ADMIN_IDS = [309524694] #309524694
        if user_id in ADMIN_IDS:
            print(f"🔵 DEBUG: Админ {user_id} - безлимитный доступ")
            return True, 0, float('inf'), 'premium', 365
        
        try:
            cursor = self.conn.cursor()
            
            # 1. Получаем информацию о подписке
            cursor.execute("SELECT subscription_type, expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                sub_type, expiry_date = result
                # Проверяем не истекла ли подписка                
                if expiry_date and datetime.now() > datetime.fromisoformat(expiry_date):
                    print(f"🔵 DEBUG: Подписка истекла! Понижаем до free")
                    sub_type = 'free'
                    cursor.execute(
                        "UPDATE subscriptions SET subscription_type = 'free' WHERE user_id = ?",
                        (user_id,)
                    )
                    self.conn.commit()
            else:
                print(f"🔵 DEBUG: Подписка не найдена! Создаем free запись")
                sub_type = 'free'
                cursor.execute(
                    "INSERT INTO subscriptions (user_id, subscription_type) VALUES (?, 'free')",
                    (user_id,)
                )
                self.conn.commit()
            
            # 2. Получаем тарифный план           
            daily_limit = 5 if sub_type != 'premium' else float('inf')
            
            # 3. Получаем статистику сообщений за сегодня
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT message_count FROM message_stats WHERE user_id = ? AND date = ?", 
                (user_id, today)
            )
            result = cursor.fetchone()
            messages_today = result[0] if result else 0
            
            print(f"🔵 DEBUG: Текущее состояние - подписка: {sub_type}, сообщений сегодня: {messages_today}, лимит: {daily_limit}")
            
            # 4. ЕСЛИ ЭТО МЕНЮ ДЕЙСТВИЕ - НЕ УВЕЛИЧИВАЕМ СЧЕТЧИК
            if is_menu_action:
                print(f"🔵 DEBUG: Меню действие - не увеличиваем счетчик")
                can_send = True
                messages_display = messages_today  # Показываем текущее количество
            else:
                # РЕАЛЬНОЕ СООБЩЕНИЕ - проверяем лимит и увеличиваем счетчик
                can_send = messages_today < daily_limit if daily_limit != float('inf') else True
                
                if can_send:
                    # Увеличиваем счетчик только для реальных сообщений
                    if result:
                        cursor.execute(
                            "UPDATE message_stats SET message_count = message_count + 1 WHERE user_id = ? AND date = ?",
                            (user_id, today)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO message_stats (user_id, date, message_count) VALUES (?, ?, 1)",
                            (user_id, today)
                        )
                    self.conn.commit()
                    messages_display = messages_today + 1
                    print(f"🔵 DEBUG: Реальное сообщение - увеличили счетчик до {messages_display}")
                else:
                    messages_display = messages_today
                    print(f"🔵 DEBUG: Лимит исчерпан - {messages_today}/{daily_limit}")
            
            # 5. Вычисляем оставшиеся дни
            days_left = 0
            if sub_type == 'premium' and expiry_date:
                days_left = max(0, (datetime.fromisoformat(expiry_date) - datetime.now()).days)
            
            print(f"🔵 DEBUG: Итог - можно отправить: {can_send}, показываем: {messages_display}/{daily_limit}")
            
            return can_send, messages_display, daily_limit, sub_type, days_left
            
        except Exception as e:
            print(f"❌ Ошибка в can_send_message: {e}")
            import traceback
            print(f"❌ Подробности: {traceback.format_exc()}")
            return True, 0, float('inf'), 'premium', 365
    
    def upgrade_subscription(self, user_id, sub_type='premium', days=30):
        """Апгрейд подписки"""
        sub_end = datetime.now() + timedelta(days=days)
        
        conn = sqlite3.connect('psychology_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET subscription_type = ?, subscription_end = ?
            WHERE user_id = ?
        ''', (sub_type, sub_end, user_id))
        
        conn.commit()
        conn.close()
        return True
    
    def debug_user_status(self, user_id):
        """Отладочная информация о пользователе"""
        try:
            cursor = self.conn.cursor()
        
            # Проверяем подписку
            cursor.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
            subscription = cursor.fetchone()
        
            # Проверяем статистику сообщений
            cursor.execute("SELECT * FROM message_stats WHERE user_id = ? AND date = date('now')", (user_id,))
            stats = cursor.fetchone()
        
            print(f"🔍 DEBUG USER {user_id}:")
            print(f"   📋 Подписка: {subscription}")
            print(f"   📊 Статистика: {stats}")
        
            return subscription, stats
        
        except Exception as e:
            print(f"❌ Ошибка отладки: {e}")
            return None, None
        
    def save_message(self, user_id, role, content):
        """Сохранить сообщение в историю"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения истории: {e}")
            return False

    def get_chat_history(self, user_id, limit=6):
        """Получить историю диалога (последние N сообщений)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
            "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
            )
            history = cursor.fetchall()
        # Возвращаем в правильном порядке (от старых к новым)
            return list(reversed(history))
        except Exception as e:
            print(f"❌ Ошибка получения истории: {e}")
            return []

    def clear_chat_history(self, user_id):

        """Очистить историю диалога"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка очистки истории: {e}")
            return False    
        
    def remove_premium(self, user_id):
        """Исключить пользователя из премиума"""
        try:
            cursor = self.conn.cursor()
            print(f"🔵 DEBUG: Удаляем премиум у пользователя {user_id}")
            
            # ОБНОВЛЯЕМ ОБЕ ТАБЛИЦЫ АТОМАРНО
            cursor.execute(
                "UPDATE subscriptions SET subscription_type = 'free', expiry_date = NULL WHERE user_id = ?",
                (user_id,)
            )
            sub_updated = cursor.rowcount
            print(f"🔵 DEBUG: Обновлено записей в subscriptions: {sub_updated}")
            
            cursor.execute(
                "UPDATE users SET subscription_type = 'free', subscription_end = NULL WHERE user_id = ?",
                (user_id,)
            )
            users_updated = cursor.rowcount
            print(f"🔵 DEBUG: Обновлено записей в users: {users_updated}")
            
            self.conn.commit()
            
            # ПРОВЕРЯЕМ РЕЗУЛЬТАТ
            cursor.execute("SELECT subscription_type FROM subscriptions WHERE user_id = ?", (user_id,))
            final_sub = cursor.fetchone()
            cursor.execute("SELECT subscription_type FROM users WHERE user_id = ?", (user_id,))
            final_user = cursor.fetchone()
            
            print(f"🔵 DEBUG: Итог - subscriptions: {final_sub}, users: {final_user}")
            
            if sub_updated > 0 or users_updated > 0:
                print(f"✅ Пользователь {user_id} исключен из премиума")
                return True
            else:
                print(f"⚠️ Пользователь {user_id} не найден или уже не премиум")
                return False
            
        except Exception as e:
            print(f"❌ Ошибка исключения из премиума: {e}")
            import traceback
            print(f"❌ Подробности: {traceback.format_exc()}")
            return False

    def add_premium_user(self, user_id, days=30):
        """Добавить или обновить пользователя в премиум"""
        try:
            cursor = self.conn.cursor()
            expiry_date = datetime.now() + timedelta(days=days)
            
            # ПРОВЕРЯЕМ СУЩЕСТВУЕТ ЛИ ПОЛЬЗОВАТЕЛЬ
            cursor.execute("SELECT user_id FROM subscriptions WHERE user_id = ?", (user_id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # ОБНОВЛЯЕМ существующую запись
                cursor.execute(
                    "UPDATE subscriptions SET subscription_type = ?, expiry_date = ? WHERE user_id = ?",
                    ('premium', expiry_date, user_id)
                )
                print(f"✅ Обновлен премиум для пользователя {user_id} на {days} дней")
            else:
                # СОЗДАЕМ новую запись
                cursor.execute(
                    "INSERT INTO subscriptions (user_id, subscription_type, expiry_date) VALUES (?, ?, ?)",
                    (user_id, 'premium', expiry_date)
                )
                print(f"✅ Создан премиум для пользователя {user_id} на {days} дней")
            
            # Также обновляем таблицу users для совместимости
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            existing_in_users = cursor.fetchone()
            
            if existing_in_users:
                cursor.execute(
                    "UPDATE users SET subscription_type = ?, subscription_end = ? WHERE user_id = ?",
                    ('premium', expiry_date, user_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO users (user_id, subscription_type, subscription_end) VALUES (?, ?, ?)",
                    (user_id, 'premium', expiry_date)
                )
            
            self.conn.commit()
            print(f"✅ Пользователь {user_id} установлен в premium на {days} дней")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка установки premium: {e}")
            import traceback
            print(f"🔍 Детали: {traceback.format_exc()}")
            return False              

    def get_all_users_info(self):        
        """Получить информацию о всех пользователях (из таблицы subscriptions)"""
        try:
            cursor = self.conn.cursor()

            cursor.execute('''
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

            users = cursor.fetchall()
            result = []

            for user in users:
                user_id, username, sub_type, expiry_date = user

                # Формируем информацию о подписке
                if sub_type == 'premium':
                    if expiry_date:
                        try:
                            # Безопасное преобразование даты
                            expiry_date_obj = datetime.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
                            days_left = max(0, (expiry_date_obj - datetime.now()).days)
                            sub_info = f"💎 Premium ({days_left}д)"
                        except:
                            sub_info = f"💎 Premium (ошибка даты)"
                    else:
                        sub_info = "💎 Premium (∞)"
                
                elif sub_type == 'trial':
                    if expiry_date:
                        try:
                            expiry_date_obj = datetime.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
                            days_left = max(0, (expiry_date_obj - datetime.now()).days)
                            sub_info = f"🆓 Trial ({days_left}д)"
                        except:
                            sub_info = f"🆓 Trial (ошибка даты)"
                    else:
                        sub_info = "🆓 Trial"
                
                else:  # free
                    # Для free пользователей получаем статистику сообщений
                    today = datetime.now().strftime('%Y-%m-%d')
                    cursor.execute(
                        "SELECT message_count FROM message_stats WHERE user_id = ? AND date = ?", 
                        (user_id, today)
                    )
                    stats_result = cursor.fetchone()
                    messages_today = stats_result[0] if stats_result else 0
                    remaining_messages = max(0, 5 - messages_today)
                    sub_info = f"🆓 Free ({remaining_messages} ост.)"

                result.append({
                    'user_id': user_id,
                    'username': username or "N/A",
                    'subscription_info': sub_info
                })

            return result

        except Exception as e:
            print(f"❌ Ошибка получения списка пользователей: {e}")
            import traceback
            print(f"❌ Подробности: {traceback.format_exc()}")
            return []
    
    def get_detailed_user_info(self, user_id):
        """Получить детальную информацию о пользователе для админа"""
        try:
            cursor = self.conn.cursor()
        
            # Получаем основную информацию из subscriptions (основной источник)
            cursor.execute('''
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
                WHERE s.user_id = ?
            ''', (user_id,))
            user_data = cursor.fetchone()
        
            if not user_data:
                return "❌ Пользователь не найден"
        
            sub_type, expiry_date, username, first_name, created_at, messages_today, last_message_date = user_data
        
            # Получаем статистику сообщений за сегодня
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT message_count FROM message_stats WHERE user_id = ? AND date = ?", 
                (user_id, today)
            )
            stats_result = cursor.fetchone()
            messages_today_count = stats_result[0] if stats_result else 0
        
            # Получаем общее количество сообщений
            cursor.execute("SELECT COUNT(*) FROM chat_history WHERE user_id = ?", (user_id,))
            total_messages = cursor.fetchone()[0]
        
            # Получаем количество активных дней
            cursor.execute("SELECT COUNT(DISTINCT date) FROM message_stats WHERE user_id = ?", (user_id,))
            active_days = cursor.fetchone()[0]
        
            # Форматируем информацию о подписке (используем данные из subscriptions!)
            if sub_type == 'premium':
                if expiry_date:
                    try:
                        # Безопасное преобразование даты
                        expiry_date_obj = datetime.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
                        days_left = max(0, (expiry_date_obj - datetime.now()).days)
                        sub_info = f"💎 Premium (осталось {days_left} дней)"
                    except:
                        sub_info = f"💎 Premium (ошибка даты: {expiry_date})"
                else:
                    sub_info = "💎 Premium (бессрочно)"
            elif sub_type == 'trial':
                if expiry_date:
                    try:
                        expiry_date_obj = datetime.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
                        days_left = max(0, (expiry_date_obj - datetime.now()).days)
                        sub_info = f"🆓 Trial (осталось {days_left} дней)"
                    except:
                        sub_info = f"🆓 Trial (ошибка даты: {expiry_date})"
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
                    if isinstance(date_value, str):
                        date_obj = datetime.fromisoformat(date_value)
                    else:
                        date_obj = date_value
                    return date_obj.strftime('%d.%m.%Y %H:%M')
                except:
                    return str(date_value)
        
            def safe_date_only(date_value, default="N/A"):
                if not date_value:
                    return default
                try:
                    if isinstance(date_value, str):
                        date_obj = datetime.fromisoformat(date_value)
                    else:
                        date_obj = date_value
                    return date_obj.strftime('%d.%m.%Y')
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
            print(f"❌ Ошибка получения информации о пользователе: {e}")
            import traceback
            print(f"❌ Подробности: {traceback.format_exc()}")
            return f"❌ Ошибка получения информации: {e}"
        
    def get_users_count_by_type(self):
        """Получить количество пользователей по типам подписки"""
        try:
            cursor = self.conn.cursor()

            cursor.execute('''
                SELECT 
                    subscription_type,
                    COUNT(*) as count
                FROM subscriptions 
                GROUP BY subscription_type
            ''')

            # Инициализируем все возможные типы
            result = {
                'premium': 0,
                'trial': 0, 
                'free': 0
            }
            
            # Обновляем реальными значениями из БД
            for row in cursor.fetchall():
                sub_type = row[0]
                if sub_type in result:
                    result[sub_type] = row[1]

            return result

        except Exception as e:
            print(f"❌ Ошибка получения статистики по типам подписок: {e}")
            return {'premium': 0, 'trial': 0, 'free': 0}

    def reset_message_count(self, user_id, date=None):
        """Обнулить счетчик сообщений пользователя"""
        try:
            cursor = self.conn.cursor()
            
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute(
                "DELETE FROM message_stats WHERE user_id = ? AND date = ?",
                (user_id, date)
            )
            
            # Также обнуляем в таблице users (если используется)
            cursor.execute(
                "UPDATE users SET messages_today = 0, last_message_date = ? WHERE user_id = ?",
                (date, user_id)
            )
            
            self.conn.commit()
            print(f"✅ Счетчик сообщений пользователя {user_id} обнулен за {date}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обнуления счетчика: {e}")
            return False  

    def get_or_create_user(self, user_id, username="", first_name=""):
        """Создать или обновить пользователя в таблице users"""
        try:
            cursor = self.conn.cursor()
            
            # Проверяем существование пользователя
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                # Новый пользователь - создаем запись
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, subscription_type)
                    VALUES (?, ?, ?, 'free')
                ''', (user_id, username, first_name))
                
                # Также создаем запись в subscriptions для совместимости
                cursor.execute('''
                    INSERT INTO subscriptions (user_id, subscription_type)
                    VALUES (?, 'free')
                ''', (user_id,))
                
                self.conn.commit()
                print(f"✅ Создан новый пользователь: {user_id}")
                return True
            else:
                # Обновляем username если изменился
                if username or first_name:
                    cursor.execute('''
                        UPDATE users SET username = ?, first_name = ? WHERE user_id = ?
                    ''', (username, first_name, user_id))
                    self.conn.commit()
                    print(f"✅ Обновлен пользователь: {user_id}")
                return True
                
        except Exception as e:
            print(f"❌ Ошибка создания/обновления пользователя: {e}")

            return False
