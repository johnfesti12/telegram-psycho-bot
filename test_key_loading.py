import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('DEEPSEEK_API_KEY')
print(f"API ключ из .env: {'*' * len(api_key) if api_key else 'НЕ НАЙДЕН'}")
print(f"Длина ключа: {len(api_key) if api_key else 0}")

# Проверяем пути
print(f"Текущая директория: {os.getcwd()}")
print(f"Файлы в директории: {[f for f in os.listdir('.') if f.endswith('.env') or f == '.env']}")