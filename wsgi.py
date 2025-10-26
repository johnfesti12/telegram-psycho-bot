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
        time.sleep(5)  # Даем время всему запуститься
        
        print("1️⃣ Checking environment...")
        print(f"   TELEGRAM_TOKEN: {'✅' if os.getenv('TELEGRAM_TOKEN') else '❌'}")
        print(f"   DEEPSEEK_API_KEY: {'✅' if os.getenv('DEEPSEEK_API_KEY') else '❌'}")
        
        print("2️⃣ Importing modules...")
        try:
            from bot_deepseek import DeepSeekPsychoBot
            print("   ✅ bot_deepseek imported")
        except ImportError as e:
            print(f"   ❌ Import error: {e}")
            return
        
        print("3️⃣ Creating bot instance...")
        try:
            bot = DeepSeekPsychoBot()
            print("   ✅ Bot instance created")
        except Exception as e:
            print(f"   ❌ Bot creation error: {e}")
            traceback.print_exc()
            return
        
        print("4️⃣ Starting message processing...")
        try:
            bot.process_updates()
        except Exception as e:
            print(f"   ❌ Process updates error: {e}")
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
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
