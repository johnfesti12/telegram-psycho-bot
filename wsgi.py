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
        time.sleep(3)
        
        print("📦 Importing bot module...")
        from bot_deepseek import DeepSeekPsychoBot
        
        print("🔧 Creating bot instance...")
        bot = DeepSeekPsychoBot()
        print("✅ Bot instance created successfully")
        
        print("🔄 Starting message processing...")
        bot.process_updates()
        
    except Exception as e:
        print(f"❌ CRITICAL BOT ERROR: {e}")
        print("🔍 Full traceback:")
        traceback.print_exc()

if __name__ == '__main__':
    print("🎯 Initializing bot thread...")
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
