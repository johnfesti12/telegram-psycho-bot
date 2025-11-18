import os
import json
import numpy as np
import time
from knowledge_base import PsychologyKnowledgeBase

def api_precompute_embeddings():
    print("🚀 Запуск предобработки с DeepSeek API...")
    
    try:
        kb = PsychologyKnowledgeBase()
        
        print(f"📚 Найдено книг: {len(kb.knowledge_base)}")
        
        all_embeddings = {}
        total_chunks = 0
        
        for book_name, book_data in kb.knowledge_base.items():
            print(f"\n📖 Обрабатываю книгу: {book_name}")
            content = book_data['content']
            
            # Разбиваем на chunks
            chunks = kb.split_into_sentences(content)
            print(f"   📄 Найдено {len(chunks)} предложений")
            
            book_embeddings = []
            
            # Обрабатываем chunks из каждой книги (ограничим для теста)
            for i, chunk in enumerate(chunks[:30]):  # По 30 на книгу чтобы не превысить лимиты
                if len(chunk) > 20:
                    print(f"   📝 Chunk {i+1}/30: {chunk[:60]}...")
                    
                    # Используем API метод
                    embedding = kb.get_embedding(chunk)
                    
                    if embedding is not None:
                        book_embeddings.append({
                            'text': chunk,
                            'embedding': embedding  # DeepSeek возвращает готовый вектор
                        })
                        total_chunks += 1
                    
                    # Пауза чтобы не превысить rate limits
                    time.sleep(0.5)
            
            all_embeddings[book_name] = book_embeddings
            print(f"✅ Книга '{book_name}' обработана: {len(book_embeddings)} эмбеддингов")
        
        # Сохраняем в файл
        with open('precomputed_embeddings.json', 'w', encoding='utf-8') as f:
            # Конвертируем numpy arrays в списки для JSON
            json_ready = {}
            for book_name, embeddings in all_embeddings.items():
                json_ready[book_name] = []
                for item in embeddings:
                    json_ready[book_name].append({
                        'text': item['text'],
                        'embedding': item['embedding']
                    })
            
            json.dump(json_ready, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Готово! Создано {total_chunks} эмбеддингов через API")
        print(f"✅ Файл 'precomputed_embeddings.json' создан!")
        
    except Exception as e:
        print(f"❌ Ошибка при создании эмбеддингов: {e}")
        import traceback
        print(f"🔍 Детали: {traceback.format_exc()}")

if __name__ == "__main__":
    api_precompute_embeddings()