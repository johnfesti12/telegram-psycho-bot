from flask import Flask, request, jsonify
import os
import sys
from datetime import datetime
import logging
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# Глобальная переменная для бота
bot = None

@app.route('/webhook/yookassa', methods=['POST', 'GET'])
def yookassa_webhook():
    """Endpoint для вебхуков от ЮKassa"""
    try:
        if request.method == 'GET':
            logger.info("✅ Проверка доступности вебхука от ЮKassa")
            return jsonify({
                "status": "ready", 
                "service": "yookassa-webhook",
                "timestamp": datetime.now().isoformat()
            }), 200
            
        # Обработка POST запросов (вебхуков)
        webhook_data = request.json
        logger.info(f"🔔 Получен вебхук от ЮKassa: {webhook_data.get('event')}")
        
        if bot and hasattr(bot, 'payment_handler'):
            # Запускаем асинхронную обработку вебхука
            success = asyncio.run(bot.payment_handler.process_webhook(webhook_data))
            logger.info(f"📊 Вебхук обработан: {success}")
            return jsonify({"success": success}), 200
        else:
            logger.error("❌ Бот не инициализирован в вебхук-сервере")
            # Сохраняем вебхук для последующей обработки
            return jsonify({"error": "Bot not initialized", "received": True}), 202
            
    except Exception as e:
        logger.error(f"❌ Ошибка в вебхуке: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервера"""
    bot_status = "initialized" if bot else "not_initialized"
    db_status = "connected" if bot and hasattr(bot, 'async_db') and bot.async_db.pool else "disconnected"
    
    return jsonify({
        "status": "healthy", 
        "service": "yookassa-webhook",
        "timestamp": datetime.now().isoformat(),
        "bot_initialized": bot is not None,
        "bot_status": bot_status,
        "database": db_status
    })

@app.route('/')
def home():
    return jsonify({
        "message": "Yookassa Webhook Server", 
        "status": "active",
        "database": "PostgreSQL",
        "endpoints": {
            "webhook": "/webhook/yookassa [GET, POST]",
            "health": "/health [GET]"
        }
    })

async def init_bot_async():
    """Асинхронная инициализация бота для вебхук-сервера"""
    global bot
    try:
        from bot_deepseek import DeepSeekPsychoBot
        bot = DeepSeekPsychoBot()
        
        # Инициализируем PostgreSQL
        if hasattr(bot, 'async_db'):
            await bot.async_db.init_pool()
            logger.info("✅ PostgreSQL инициализирована в вебхук-сервере")
        
        logger.info("✅ Бот инициализирован в вебхук-сервере")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        bot = None
        return False

def init_bot():
    """Синхронная обертка для инициализации бота"""
    return asyncio.run(init_bot_async())

if __name__ == '__main__':
    # Инициализируем бота при запуске
    init_bot()
    
    # Запускаем сервер
    port = int(os.getenv('PORT', 5000))
    host = '0.0.0.0'
    
    logger.info(f"🚀 Запуск вебхук-сервера на {host}:{port}")
    logger.info(f"📊 База данных: PostgreSQL")
    app.run(host=host, port=port, debug=False)