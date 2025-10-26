from flask import Flask, request, jsonify
import os
import sys
from datetime import datetime
import logging

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
            success = bot.payment_handler.process_webhook(webhook_data)
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
    return jsonify({
        "status": "healthy", 
        "service": "yookassa-webhook",
        "timestamp": datetime.now().isoformat(),
        "bot_initialized": bot is not None
    })

@app.route('/')
def home():
    return jsonify({
        "message": "Yookassa Webhook Server", 
        "status": "active",
        "endpoints": {
            "webhook": "/webhook/yookassa [GET, POST]",
            "health": "/health [GET]"
        }
    })

def init_bot():
    """Инициализация бота для вебхук-сервера"""
    global bot
    try:
        from bot_deepseek import DeepSeekPsychoBot
        bot = DeepSeekPsychoBot()
        logger.info("✅ Бот инициализирован в вебхук-сервере")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        bot = None

if __name__ == '__main__':
    # Инициализируем бота при запуске
    init_bot()
    
    # Запускаем сервер
    port = int(os.getenv('PORT', 5000))
    host = '0.0.0.0'
    
    logger.info(f"🚀 Запуск вебхук-сервера на {host}:{port}")
    app.run(host=host, port=port, debug=False)