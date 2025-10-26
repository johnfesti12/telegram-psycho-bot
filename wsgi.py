from flask import Flask, jsonify
import threading
import os
import time
import traceback

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "psychology-bot"})

@app.route('/')
def home():
    return "🤖 Psychology Bot is running..."

def start_bot():
    """Запуск бота"""
    try:
        print("🚀 Starting psychology bot...")
        time.sleep(3)  # Даем время для инициализации
        
        print("🔍 Step 1: Checking environment variables...")
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        
        print(f"   TELEGRAM_TOKEN: {'✅ SET' if telegram_token else '❌ MISSING'}")
        print(f"   DEEPSEEK_API_KEY: {'✅ SET' if deepseek_key else '❌ MISSING'}")
        
        if not telegram_token or not deepseek_key:
            print("❌ CRITICAL: Missing environment variables!")
            return
        
        print("🔍 Step 2: Importing bot module...")
        try:
            from bot_deepseek import DeepSeekPsychoBot
            print("   ✅ Import successful")
        except Exception as e:
            print(f"   ❌ Import failed: {e}")
            traceback.print_exc()
            return
        
        print("🔍 Step 3: Creating bot instance...")
        try:
            bot = DeepSeekPsychoBot()
            print("   ✅ Bot instance created")
        except Exception as e:
            print(f"   ❌ Bot creation failed: {e}")
            traceback.print_exc()
            return
        
        print("🔍 Step 4: Starting message processing...")
        try:
            bot.process_updates()
        except Exception as e:
            print(f"   ❌ Process updates failed: {e}")
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    print("🎯 Server starting...")
    
    # Запускаем бота
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем Flask
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 Flask starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
