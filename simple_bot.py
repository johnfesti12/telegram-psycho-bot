from flask import Flask, jsonify
import os
import time
import traceback

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/')
def home():
    return "🤖 Bot is running"

# Запускаем бота при старте
def initialize_bot():
    print("🎯 BOT INITIALIZATION STARTED")
    
    print("🔍 STEP 1: Basic imports...")
    import sys
    print(f"   Python path: {sys.path}")
    
    print("🔍 STEP 2: Checking environment...")
    time.sleep(1)
    
    # Проверка переменных
    print("🔍 STEP 3: Reading environment variables...")
    try:
        TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
        DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
        
        print(f"🔑 TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:10]}..." if TELEGRAM_TOKEN else "❌ MISSING")
        print(f"🔑 DEEPSEEK_API_KEY: {DEEPSEEK_API_KEY[:10]}..." if DEEPSEEK_API_KEY else "❌ MISSING")
        
        if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
            print("❌ MISSING ENV VARIABLES")
            return False
        
        print("📦 STEP 4: Importing bot...")
        from bot_deepseek import DeepSeekPsychoBot
        
        print("🔧 STEP 5: Creating bot instance...")
        bot = DeepSeekPsychoBot()
        print("✅ BOT INSTANCE CREATED")
        
        return bot
        
    except Exception as e:
        print(f"❌ INIT ERROR: {e}")
        traceback.print_exc()
        return False

# Глобальная переменная
bot_instance = None

@app.before_first_request
def start_bot_processing():
    """Запуск обработки сообщений при первом запросе"""
    global bot_instance
    if bot_instance:
        print("🚀 STARTING MESSAGE PROCESSING...")
        try:
            bot_instance.process_updates()
        except Exception as e:
            print(f"❌ PROCESS ERROR: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    print("🎯 SERVER STARTING...")
    
    # Инициализируем бота сразу
    print("🔧 INITIALIZING BOT...")
    bot_instance = initialize_bot()
    
    if bot_instance:
        print("✅ BOT READY - waiting for first request...")
    else:
        print("❌ BOT INITIALIZATION FAILED")
    
    # Запускаем Flask
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 STARTING FLASK ON PORT {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
