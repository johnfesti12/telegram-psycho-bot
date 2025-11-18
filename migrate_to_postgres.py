import sqlite3
import asyncio
import asyncpg
from config import DATABASE_URL

async def migrate_data():
    print("🚀 Начинаю миграцию данных из SQLite в PostgreSQL...")
    
    # Подключаемся к SQLite
    sqlite_conn = sqlite3.connect('psychology_bot.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # Подключаемся к PostgreSQL
    postgres_conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Миграция таблицы subscriptions
        print("📦 Мигрирую таблицу subscriptions...")
        sqlite_cursor.execute("SELECT * FROM subscriptions")
        subscriptions = sqlite_cursor.fetchall()
        
        for sub in subscriptions:
            user_id, sub_type, expiry_date, created_at = sub
            await postgres_conn.execute('''
                INSERT INTO subscriptions (user_id, subscription_type, expiry_date, created_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET
                subscription_type = EXCLUDED.subscription_type,
                expiry_date = EXCLUDED.expiry_date
            ''', user_id, sub_type, expiry_date, created_at)
        
        # Миграция таблицы users
        print("📦 Мигрирую таблицу users...")
        sqlite_cursor.execute("SELECT * FROM users")
        users = sqlite_cursor.fetchall()
        
        for user in users:
            await postgres_conn.execute('''
                INSERT INTO users (user_id, username, first_name, subscription_type, subscription_end, messages_today, last_message_date, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                subscription_type = EXCLUDED.subscription_type,
                subscription_end = EXCLUDED.subscription_end,
                messages_today = EXCLUDED.messages_today,
                last_message_date = EXCLUDED.last_message_date
            ''', *user)
        
        # Миграция таблицы message_stats
        print("📦 Мигрирую таблицу message_stats...")
        sqlite_cursor.execute("SELECT * FROM message_stats")
        stats = sqlite_cursor.fetchall()
        
        for stat in stats:
            await postgres_conn.execute('''
                INSERT INTO message_stats (user_id, date, message_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, date) DO UPDATE SET
                message_count = EXCLUDED.message_count
            ''', *stat)
        
        # Миграция таблицы chat_history
        print("📦 Мигрирую таблицу chat_history...")
        sqlite_cursor.execute("SELECT user_id, role, content, timestamp FROM chat_history")
        history = sqlite_cursor.fetchall()
        
        for msg in history:
            await postgres_conn.execute('''
                INSERT INTO chat_history (user_id, role, content, timestamp)
                VALUES ($1, $2, $3, $4)
            ''', *msg)
        
        # Миграция таблицы payments
        print("📦 Мигрирую таблицу payments...")
        sqlite_cursor.execute("SELECT * FROM payments")
        payments = sqlite_cursor.fetchall()
        
        for payment in payments:
            await postgres_conn.execute('''
                INSERT INTO payments (id, user_id, payment_id, yookassa_payment_id, tariff_type, amount, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO NOTHING
            ''', *payment)
        
        print("✅ Миграция данных завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        raise
    finally:
        sqlite_conn.close()
        await postgres_conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_data())