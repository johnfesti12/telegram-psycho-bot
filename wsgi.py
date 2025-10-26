from flask import Flask, jsonify
import threading
import os

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "psychology-bot"})

@app.route('/')
def home():
    return "🤖 Psychology Bot is running..."

def start_bot():
    """Запуск бота в отдельном потоке"""
    try:
        from bot_deepseek import main
        main()
    except Exception as e:
        print(f"❌ Bot error: {e}")

if __name__ == '__main__':
    # Сразу запускаем бота в фоне
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Быстро запускаем web server
    port = int(os.getenv('PORT', 10000))
    print(f"🚀 Starting health server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)