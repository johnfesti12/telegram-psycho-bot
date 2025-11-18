import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_deepseek_chat_api():
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ DEEPSEEK_API_KEY не найден в .env файле")
        return
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Привет! Ответь просто 'Тест пройден'"}
        ],
        "max_tokens": 10
    }
    
    try:
        print("🔗 Тестирую DeepSeek Chat API...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ Chat API работает! Ответ: {content}")
            return True
        else:
            print(f"❌ API ошибка: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

if __name__ == "__main__":
    test_deepseek_chat_api()