from flask import Flask, jsonify
import threading
import os
import time

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
        time.sleep(5)  # Даем время Flask запуститься
        
        # Прямой импорт и запуск
        from bot_deepseek import DeepSeekPsychoBot
        bot = DeepSeekPsychoBot()
        print("✅ Bot instance created")
        
        # Запускаем обработку
        print("🔄 Starting message processing...")
        bot.process_updates()
        
    except Exception as e:
        print(f"❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Сразу запускаем бота
    print("🎯 Initializing bot thread...")
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Потом Flask
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
