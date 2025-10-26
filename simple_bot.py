from flask import Flask, jsonify
import os
import threading
import time
import traceback

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/')
def home():
    return "🤖 Bot is running"

def start_bot():
    """Запуск бота с максимальной отладкой"""
    try:
        print("🎯 BOT INITIALIZATION STARTED")
        
        print("🔍 STEP 1: Basic imports...")
        import sys
        print(f"   Python path: {sys.path}")
        
        print("🔍 STEP 2: Checking environment...")
        time.sleep(1)
        
        # Проверка переменных
        print("🔍 STEP 3: Reading environment variables...")
        TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
        DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
        
        print(f"🔑 TELEGRAM_TOKEN: {'✅' if TELEGRAM_TOKEN else '❌'}")
        print(f"🔑 DEEPSEEK_API_KEY: {'✅' if DEEPSEEK_API_KEY else '❌'}")
        
        if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
            print("❌ MISSING ENV VARIABLES")
            return
        
        print("📦 STEP 4: Importing bot...")
        from bot_deepseek import DeepSeekPsychoBot
        
        print("🔧 STEP 5: Creating bot instance...")
        bot = DeepSeekPsychoBot()
        print("✅ BOT INSTANCE CREATED")
        
        print("🚀 STEP 6: Starting message processing...")
        bot.process_updates()
        
    except Exception as e:
        print(f"❌ BOT ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Сразу запускаем бота в фоне
    print("🎯 STARTING BOT THREAD...")
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Быстро запускаем Flask
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 STARTING FLASK ON PORT {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
