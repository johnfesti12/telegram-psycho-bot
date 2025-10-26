import os
import logging

print("🎯 SIMPLE BOT STARTING...")

# Проверяем переменные
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:10]}..." if TELEGRAM_TOKEN else "❌ TELEGRAM_TOKEN MISSING")
print(f"DEEPSEEK_API_KEY: {DEEPSEEK_API_KEY[:10]}..." if DEEPSEEK_API_KEY else "❌ DEEPSEEK_API_KEY MISSING")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    print("❌ CRITICAL: Missing environment variables!")
    exit(1)

try:
    print("📦 Importing bot...")
    from bot_deepseek import DeepSeekPsychoBot
    
    print("🔧 Creating bot instance...")
    bot = DeepSeekPsychoBot()
    
    print("🚀 Starting bot...")
    bot.process_updates()
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
