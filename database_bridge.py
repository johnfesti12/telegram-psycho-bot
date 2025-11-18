import asyncio
import sqlite3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DatabaseBridge:
    """Асинхронный мост для SQLite с PostgreSQL-совместимым интерфейсом"""
    
    def __init__(self, db_path='psychology_bot.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        print("✅ Database Bridge initialized (SQLite)")
    
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_stats (
                user_id INTEGER,
                date TEXT,
                message_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        ''')
        
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
                updated_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_type TEXT DEFAULT 'free',
                subscription_end TIMESTAMP,
                messages_today INTEGER DEFAULT 0,
                last_message_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        print("✅ Все таблицы созданы/проверены")

    async def init_pool(self):
        """Имитация инициализации пула для совместимости"""
        print("✅ SQLite database ready")
        return True

    async def can_send_message(self, user_id, is_menu_action=None):
        """Асинхронная проверка лимитов сообщений"""
        def sync_can_send():
            cursor = self.conn.cursor()
            
            # АДМИНЫ ВСЕГДА МОГУТ ОТПРАВЛЯТЬ СООБЩЕНИЯ
            ADMIN_IDS = [309524694]
            if user_id in ADMIN_IDS:
                return True, 0, float('inf'), 'premium', 365
            
            # Получаем информацию о подписке
            cursor.execute("SELECT subscription_type, expiry_date FROM subscriptions WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                sub_type, expiry_date = result
                # Проверяем не истекла ли подписка                
                if expiry_date and datetime.now() > datetime.fromisoformat(expiry_date):
                    sub_type = 'free'
                    cursor.execute(
                        "UPDATE subscriptions SET subscription_type = 'free' WHERE user_id = ?",
                        (user_id,)
                    )
            else:
                sub_type = 'free'
                cursor.execute(
                    "INSERT INTO subscriptions (user_id, subscription_type) VALUES (?, 'free')",
                    (user_id,)
                )
            
            # Получаем тарифный план           
            daily_limit = 5 if sub_type != 'premium' else float('inf')
            
            # Получаем статистику сообщений за сегодня
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "SELECT message_count FROM message_stats WHERE user_id = ? AND date = ?", 
                (user_id, today)
            )
            result = cursor.fetchone()
            messages_today = result[0] if result else 0
            
            # ЕСЛИ ЭТО МЕНЮ ДЕЙСТВИЕ - НЕ УВЕЛИЧИВАЕМ СЧЕТЧИК
            if is_menu_action:
                can_send = True
                messages_display = messages_today
            else:
                # РЕАЛЬНОЕ СООБЩЕНИЕ - проверяем лимит и увеличиваем счетчик
                can_send = messages_today < daily_limit if daily_limit != float('inf') else True
                
                if can_send and not is_menu_action:
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
                    messages_display = messages_today + 1
                else:
                    messages_display = messages_today
            
            # Вычисляем оставшиеся дни
            days_left = 0
            if sub_type == 'premium' and expiry_date:
                days_left = max(0, (datetime.fromisoformat(expiry_date) - datetime.now()).days)
            
            self.conn.commit()
            return can_send, messages_display, daily_limit, sub_type, days_left
        
        # Запускаем синхронный код в отдельном потоке
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_can_send)
    
    async def save_message(self, user_id, role, content):
        """Асинхронное сохранение сообщения"""
        def sync_save():
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )
            self.conn.commit()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_save)
    
    async def get_chat_history(self, user_id, limit=6):
        """Асинхронное получение истории"""
        def sync_get_history():
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            )
            history = cursor.fetchall()
            return list(reversed(history))
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_get_history)
    
    async def add_premium_user(self, user_id, days=30):
        """Асинхронное добавление премиума"""
        def sync_add_premium():
            cursor = self.conn.cursor()
            expiry_date = datetime.now() + timedelta(days=days)
            
            # Проверяем существование пользователя
            cursor.execute("SELECT user_id FROM subscriptions WHERE user_id = ?", (user_id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # Обновляем существующую запись
                cursor.execute(
                    "UPDATE subscriptions SET subscription_type = ?, expiry_date = ? WHERE user_id = ?",
                    ('premium', expiry_date, user_id)
                )
            else:
                # Создаем новую запись
                cursor.execute(
                    "INSERT INTO subscriptions (user_id, subscription_type, expiry_date) VALUES (?, ?, ?)",
                    (user_id, 'premium', expiry_date)
                )
            
            self.conn.commit()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_add_premium)

    async def save_payment(self, user_id, payment_id, yookassa_payment_id, tariff_type, amount, status):
        """Сохранение информации о платеже"""
        def sync_save_payment():
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO payments 
                (user_id, payment_id, yookassa_payment_id, tariff_type, amount, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, payment_id, yookassa_payment_id, tariff_type, amount, status, datetime.now()))
            self.conn.commit()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_save_payment)

    async def update_payment_status(self, payment_id, status):
        """Обновление статуса платежа"""
        def sync_update_status():
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE payments SET status = ?, updated_at = ? 
                WHERE payment_id = ? OR yookassa_payment_id = ?
            ''', (status, datetime.now(), payment_id, payment_id))
            self.conn.commit()
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_update_status)

    async def get_payment_by_id(self, payment_id):
        """Получение информации о платеже"""
        def sync_get_payment():
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM payments 
                WHERE payment_id = ? OR yookassa_payment_id = ?
            ''', (payment_id, payment_id))
            result = cursor.fetchone()
            if result:
                return dict(result)
            return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_get_payment)

# Глобальный экземпляр
db_bridge = DatabaseBridge()